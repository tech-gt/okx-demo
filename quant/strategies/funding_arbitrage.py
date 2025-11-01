from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import logging
import time

from ..core.strategy import Strategy
from ..core.types import Tick, Order, Side, OrderType, PortfolioState
from ..core.broker import Broker
from ..utils import get_funding_rate, get_logger


@dataclass
class FundingArbitrageConfig:
    """Configuration for funding rate arbitrage strategy."""
    # Swap instrument ID (e.g., 'BTC-USDT-SWAP')
    swap_inst_id: str
    # Spot instrument ID (e.g., 'BTC-USDT')
    spot_inst_id: str
    # Minimum funding rate to open position (e.g., 0.0001 = 0.01%)
    min_funding_rate: float = 0.0001
    # Maximum funding rate to close position (e.g., 0.00005 = 0.005%)
    max_funding_rate_to_close: float = 0.00005
    # Position size in quote currency (e.g., 1000 USDT)
    position_size_usdt: float = 1000.0
    # Funding rate check interval in seconds (default: 300s = 5min)
    funding_check_interval: float = 300.0
    # Cooldown period after closing position before reopening (seconds)
    cooldown_seconds: float = 60.0


class FundingArbitrageStrategy(Strategy):
    """Funding rate arbitrage strategy.
    
    This strategy implements delta-neutral funding rate arbitrage:
    1. When funding rate is high, open short position in swap and long position in spot
    2. Hold positions to collect funding fees
    3. Close positions when funding rate drops below threshold
    
    The strategy maintains delta-neutral exposure by matching swap and spot positions.
    """
    
    def __init__(self, cfg: FundingArbitrageConfig, broker: Optional[Broker] = None) -> None:
        self._cfg = cfg
        self._broker = broker
        self._logger = get_logger(__name__)
        
        # Track last funding rate check and value
        self._last_funding_check: float = 0.0
        self._last_funding_rate: Optional[float] = None
        
        # Track last close time for cooldown
        self._last_close_time: float = 0.0
        
        # Track prices for position sizing
        self._last_spot_price: Optional[float] = None
        self._last_swap_price: Optional[float] = None
        
    def on_start(self) -> None:
        self._logger.info(
            f"Funding Arbitrage Strategy started - "
            f"Swap: {self._cfg.swap_inst_id}, Spot: {self._cfg.spot_inst_id}, "
            f"Min funding rate: {self._cfg.min_funding_rate*100:.4f}%, "
            f"Position size: {self._cfg.position_size_usdt} USDT"
        )
        
    def _get_funding_rate(self) -> Optional[float]:
        """Get current funding rate, with caching to avoid too frequent API calls."""
        now = time.time()
        if now - self._last_funding_check < self._cfg.funding_check_interval:
            return self._last_funding_rate
        
        rate = get_funding_rate(self._cfg.swap_inst_id)
        self._last_funding_check = now
        self._last_funding_rate = rate
        
        if rate is not None:
            self._logger.info(
                f"Funding rate for {self._cfg.swap_inst_id}: {rate*100:.4f}% "
                f"(annualized: {rate*3*365*100:.2f}%)"
            )
        
        return rate
    
    def _get_portfolio(self) -> Optional[PortfolioState]:
        """Get current portfolio state from broker."""
        if self._broker is None:
            return None
        return self._broker.get_portfolio()
    
    def _has_open_position(self) -> bool:
        """Check if we have an open arbitrage position.
        
        An arbitrage position requires:
        - Spot long position (positive quantity) AND
        - Swap short position (negative quantity)
        
        If user already has spot but no swap, we can still open arbitrage,
        so we check if we have a swap short position as the key indicator.
        """
        portfolio = self._get_portfolio()
        if portfolio is None:
            return False
        
        spot_pos = portfolio.positions.get(self._cfg.spot_inst_id)
        swap_pos = portfolio.positions.get(self._cfg.swap_inst_id)
        
        # Check if we have a swap short position (negative quantity)
        # This is the key indicator of an active arbitrage position
        has_swap_short = swap_pos is not None and swap_pos.quantity < -1e-8
        
        # If we have swap short, we have an arbitrage position
        # (spot might be pre-existing or bought by strategy)
        return has_swap_short
    
    def _get_position_sizes(self) -> Tuple[float, float]:
        """Get current position sizes: (spot_qty, swap_qty)."""
        portfolio = self._get_portfolio()
        if portfolio is None:
            return (0.0, 0.0)
        
        spot_pos = portfolio.positions.get(self._cfg.spot_inst_id)
        swap_pos = portfolio.positions.get(self._cfg.swap_inst_id)
        
        spot_qty = spot_pos.quantity if spot_pos else 0.0
        swap_qty = swap_pos.quantity if swap_pos else 0.0
        
        return (spot_qty, swap_qty)
    
    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size in base currency from USDT amount."""
        if price <= 0:
            return 0.0
        return self._cfg.position_size_usdt / price
    
    def on_tick(self, tick: Tick) -> Iterable[Order]:
        """Handle tick and generate orders for funding rate arbitrage."""
        orders: List[Order] = []
        
        # Update price tracking
        if tick.inst_id == self._cfg.spot_inst_id:
            self._last_spot_price = tick.last
        elif tick.inst_id == self._cfg.swap_inst_id:
            self._last_swap_price = tick.last
        
        # Only process if we have prices for both instruments
        if self._last_spot_price is None or self._last_swap_price is None:
            return []
        
        # Check funding rate (with caching)
        funding_rate = self._get_funding_rate()
        if funding_rate is None:
            self._logger.warning(f"Failed to get funding rate, skipping tick")
            return []
        
        has_position = self._has_open_position()
        
        if not has_position:
            # No position - check if we should open
            # Check cooldown period
            now = time.time()
            if now - self._last_close_time < self._cfg.cooldown_seconds:
                return []
            
            if funding_rate >= self._cfg.min_funding_rate:
                self._logger.info(
                    f"Funding rate {funding_rate*100:.4f}% >= threshold "
                    f"{self._cfg.min_funding_rate*100:.4f}%, opening arbitrage position"
                )
                
                # Calculate target position size
                # Use average of spot and swap prices for better accuracy
                avg_price = (self._last_spot_price + self._last_swap_price) / 2.0
                target_position_qty = self._calculate_position_size(avg_price)
                
                if target_position_qty <= 0:
                    self._logger.error(f"Invalid position quantity: {target_position_qty}")
                    return []
                
                # Check existing spot balance
                spot_qty, swap_qty = self._get_position_sizes()
                available_spot = spot_qty  # Use existing spot position quantity
                
                # Calculate how much spot we need to buy (if any)
                spot_to_buy = max(0.0, target_position_qty - available_spot)
                
                # Calculate swap position size
                # For arbitrage, swap should match total (existing + new) spot
                swap_position_qty = target_position_qty
                
                self._logger.info(
                    f"Target position: {target_position_qty:.6f}"
                )
                self._logger.info(
                    f"Existing spot: {available_spot:.6f}, Need to buy: {spot_to_buy:.6f}"
                )
                self._logger.info(
                    f"Opening arbitrage: Spot long {target_position_qty:.6f} {self._cfg.spot_inst_id} "
                    f"(using {available_spot:.6f} existing + buying {spot_to_buy:.6f}), "
                    f"Swap short {swap_position_qty:.6f} {self._cfg.swap_inst_id}"
                )
                
                # Buy spot only if we need more (use existing if available)
                if spot_to_buy > 1e-8:  # Need to buy some spot
                    orders.append(Order(
                        inst_id=self._cfg.spot_inst_id,
                        side=Side.BUY,
                        order_type=OrderType.MARKET,
                        quantity=spot_to_buy,
                        quote_quantity=None,
                    ))
                    self._logger.info(f"Buying {spot_to_buy:.6f} {self._cfg.spot_inst_id} spot")
                else:
                    self._logger.info(f"Using existing {available_spot:.6f} {self._cfg.spot_inst_id} spot, no need to buy")
                
                # Always open swap short position
                orders.append(Order(
                    inst_id=self._cfg.swap_inst_id,
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    quantity=swap_position_qty,
                    quote_quantity=None,
                ))
                self._logger.info(f"Shorting {swap_position_qty:.6f} {self._cfg.swap_inst_id} swap")
        else:
            # Have position - check if we should close
            if funding_rate <= self._cfg.max_funding_rate_to_close:
                self._logger.info(
                    f"Funding rate {funding_rate*100:.4f}% <= close threshold "
                    f"{self._cfg.max_funding_rate_to_close*100:.4f}%, closing arbitrage position"
                )
                
                spot_qty, swap_qty = self._get_position_sizes()
                
                # Close spot position (sell if we have long)
                if spot_qty > 1e-8:
                    orders.append(Order(
                        inst_id=self._cfg.spot_inst_id,
                        side=Side.SELL,
                        order_type=OrderType.MARKET,
                        quantity=abs(spot_qty),
                        quote_quantity=None,
                    ))
                
                # Close swap position (buy back if we have short)
                if swap_qty < -1e-8:
                    orders.append(Order(
                        inst_id=self._cfg.swap_inst_id,
                        side=Side.BUY,
                        order_type=OrderType.MARKET,
                        quantity=abs(swap_qty),
                        quote_quantity=None,
                    ))
                
                self._last_close_time = time.time()
        
        return orders
    
    def on_end(self) -> List[Order]:
        """Close all positions when strategy ends."""
        orders: List[Order] = []
        
        if self._has_open_position():
            self._logger.info("Closing all positions at strategy end")
            
            spot_qty, swap_qty = self._get_position_sizes()
            
            if spot_qty > 1e-8:
                orders.append(Order(
                    inst_id=self._cfg.spot_inst_id,
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    quantity=abs(spot_qty),
                    quote_quantity=None,
                ))
            
            if swap_qty < -1e-8:
                orders.append(Order(
                    inst_id=self._cfg.swap_inst_id,
                    side=Side.BUY,
                    order_type=OrderType.MARKET,
                    quantity=abs(swap_qty),
                    quote_quantity=None,
                ))
        
        return orders

