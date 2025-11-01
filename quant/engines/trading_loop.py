from __future__ import annotations

from dataclasses import dataclass
from typing import List
import logging

from ..core.strategy import Strategy
from ..core.risk import RiskManager
from ..core.types import Tick, Order
from ..core.broker import Broker


@dataclass
class TradingEngineConfig:
    inst_ids: List[str]
    dry_run: bool = False  # If True, only log but do not submit orders


class TradingEngine:
    def __init__(self, strategy: Strategy, feed, broker: Broker, risk: RiskManager, dry_run: bool = False, 
                 max_position_value: float | None = None) -> None:
        self._strategy = strategy
        self._feed = feed
        self._broker = broker
        self._risk = risk
        self._dry_run = dry_run
        self._max_position_value = max_position_value  # Max total position value in quote currency
        self._logger = logging.getLogger(__name__)

    def run(self, duration_ticks: int | None = None) -> None:
        self._logger.info("Starting strategy...")
        self._strategy.on_start()
        tick_count = 0
        latest_prices: dict[str, float] = {}  # Track latest prices for each instrument
        try:
            for tick in self._feed.stream():
                self._logger.info(f"Tick #{tick_count + 1} {tick.inst_id} Price={tick.last:.4f}")
                latest_prices[tick.inst_id] = tick.last
                
                if hasattr(self._broker, "set_last_price"):
                    # paper broker uses last price for fills
                    self._broker.set_last_price(tick.inst_id, tick.last)  # type: ignore[attr-defined]

                orders: List[Order] = list(self._strategy.on_tick(tick))
                # self._logger.info(f"Strategy generated {len(orders)} order(s)")
                
                for order in orders:
                    ref_price = tick.last
                    if order.quote_quantity:
                        self._logger.info(f"Processing order: {order.side} {order.inst_id} quote_qty={order.quote_quantity}")
                    else:
                        self._logger.info(f"Processing order: {order.side} {order.inst_id} base_qty={order.quantity}")
                    
                    if not self._risk.approve(order, self._broker.get_portfolio(), ref_price):
                        self._logger.warning(f"Order REJECTED: {order}")
                        continue
                    
                    if self._dry_run:
                        self._logger.info(f"[DryRun] Would submit order: {order.side} {order.inst_id} quote_quantity={order.quote_quantity}")
                        self._logger.info(f"[DryRun] Reference price: {ref_price:.4f}")
                        if order.quote_quantity:
                            qty = order.quote_quantity / ref_price
                            notional = order.quote_quantity
                        else:
                            qty = order.quantity
                            notional = qty * ref_price
                        fee = notional * (5.0 / 10_000.0)  # 5bps fee
                        self._logger.info(f"[DryRun] Would fill: quantity={qty:.4f} notional={notional:.4f} fee={fee:.4f}")
                    else:
                        fills = self._broker.submit(order)
                        if fills:
                            self._logger.info(f"Fills: {fills}")
                            portfolio = self._broker.get_portfolio()
                            self._logger.info(f"Cash={portfolio.cash:.4f} Positions={len(portfolio.positions)}")

                # Check position value limit
                if self._max_position_value is not None:
                    portfolio = self._broker.get_portfolio()
                    total_position_value = 0.0
                    for inst_id, pos in portfolio.positions.items():
                        if pos.quantity > 0:  # Only count long positions
                            latest_price = latest_prices.get(inst_id, 0.0)
                            total_position_value += pos.quantity * latest_price
                    
                    if total_position_value >= self._max_position_value:
                        self._logger.info(f"Total position value {total_position_value:.4f} reached limit {self._max_position_value:.4f}, stopping...")
                        break
                
                # tick_count += 1
                # if duration_ticks is not None and tick_count >= duration_ticks:
                #     self._logger.info(f"Reached {duration_ticks} ticks, stopping...")
                #     break
        finally:
            self._logger.info("Stopping strategy...")
            try:
                final_orders = self._strategy.on_end()
                for o in final_orders:
                    if self._dry_run:
                        self._logger.info(f"[DryRun] Would submit final order: {o}")
                    else:
                        self._broker.submit(o)
            except Exception:
                pass
            try:
                self._feed.close()
            except Exception:
                pass
            
            self._logger.info("Final portfolio state:")
            portfolio = self._broker.get_portfolio()
            self._logger.info(f"Cash={portfolio.cash:.4f}")
            for inst_id, pos in portfolio.positions.items():
                self._logger.info(f"{inst_id}: qty={pos.quantity:.4f} avg_price={pos.avg_price:.4f}")

