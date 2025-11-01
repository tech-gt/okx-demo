from __future__ import annotations

import logging
import time
from typing import List, Optional, Dict

from ..core.broker import Broker
from ..core.portfolio import Portfolio
from ..core.types import Order, Fill, PortfolioState, Side, OrderType
from ..utils import _okx_request, get_logger


class OkxBroker(Broker):
    """Real OKX broker that submits orders via OKX API.
    
    Supports both simulated trading (OKX_SIMULATED=1) and live trading (OKX_SIMULATED=0).
    This broker queries the actual portfolio state from OKX and submits real orders.
    
    Note: For order execution, we poll for order status and fills. In production,
    you might want to use WebSocket order channel to get instant updates.
    """

    def __init__(self, max_fill_wait_seconds: float = 10.0) -> None:
        """
        Args:
            max_fill_wait_seconds: Maximum time to wait for order fills in seconds
        """
        self._logger = get_logger(__name__)
        self._max_fill_wait = max_fill_wait_seconds
        self._logger.info("OkxBroker initialized (check OKX_SIMULATED env for sim/live mode)")

    def submit(self, order: Order) -> List[Fill]:
        """Submit order to OKX and wait for fills."""
        # Convert our Order to OKX API format
        okx_order = self._convert_order(order)
        if okx_order is None:
            self._logger.error(f"Failed to convert order: {order}")
            return []

        # Submit to OKX
        self._logger.info(f"Submitting order to OKX: {okx_order}")
        response = _okx_request('POST', '/api/v5/trade/order', body=okx_order)
        
        if response.get('code') != '0':
            self._logger.error(f"Order submission failed: {response.get('msg', 'Unknown error')}")
            return []

        # Get order ID from response
        order_data = response.get('data', [])
        if not order_data:
            self._logger.error("No order data in response")
            return []

        order_id = order_data[0].get('ordId')
        if not order_id:
            self._logger.error("No order ID in response")
            return []

        self._logger.info(f"Order submitted with OKX order ID: {order_id}")
        
        # Poll for fills
        fills = self._wait_for_fills(order, order_id)
        return fills

    def get_portfolio(self) -> PortfolioState:
        """Query current portfolio state from OKX."""
        # Query account balance (cash)
        balance_resp = _okx_request('GET', '/api/v5/account/balance')
        cash = 0.0
        if balance_resp.get('code') == '0':
            data_list = balance_resp.get('data', [])
            if data_list:
                details = data_list[0].get('details', [])
                for detail in details:
                    # Sum all quote currency balances (typically USDT)
                    if detail.get('ccy') in ['USDT', 'USDC', 'USD']:
                        cash += float(detail.get('availBal', '0'))
        else:
            self._logger.warning(f"Failed to get balance: {balance_resp.get('msg')}")

        # Query positions
        positions: Dict[str, any] = {}
        pos_resp = _okx_request('GET', '/api/v5/account/positions')
        if pos_resp.get('code') == '0':
            data_list = pos_resp.get('data', [])
            for pos_data in data_list:
                inst_id = pos_data.get('instId')
                avg_px = pos_data.get('avgPx', '0')
                pos = pos_data.get('pos', '0')
                
                if inst_id and float(pos) != 0:
                    from ..core.types import Position
                    positions[inst_id] = Position(
                        inst_id=inst_id,
                        quantity=float(pos),
                        avg_price=float(avg_px)
                    )
        else:
            self._logger.warning(f"Failed to get positions: {pos_resp.get('msg')}")

        portfolio = PortfolioState(cash=cash, positions=positions)
        self._logger.debug(f"Current portfolio: cash={cash:.2f}, positions={len(positions)}")
        return portfolio

    def _convert_order(self, order: Order) -> Optional[dict]:
        """Convert internal Order to OKX API format."""
        side = 'buy' if order.side == Side.BUY else 'sell'
        ord_type = 'market' if order.order_type == OrderType.MARKET else 'limit'
        
        if order.order_type == OrderType.LIMIT and order.price is None:
            self._logger.error("Limit order requires price")
            return None

        okx_order = {
            'instId': order.inst_id,
            'tdMode': 'cash',  # Spot trading
            'side': side,
            'ordType': ord_type,
        }

        # OKX uses 'sz' for size
        # For spot market, we can specify quote currency or base currency
        if order.quote_quantity is not None and order.quote_quantity > 0:
            # Specify by quote currency (e.g., spend 50 USDT)
            okx_order['sz'] = str(order.quote_quantity)
            okx_order['tgtCcy'] = 'quote_ccy'
        elif order.quantity > 0:
            # Specify by base currency (e.g., buy 0.1 BTC)
            okx_order['sz'] = str(order.quantity)
            okx_order['tgtCcy'] = 'base_ccy'
        else:
            self._logger.error("Order must have either quantity or quote_quantity")
            return None

        if order.price:
            okx_order['px'] = str(order.price)

        if order.client_order_id:
            okx_order['clOrdId'] = order.client_order_id

        return okx_order

    def _wait_for_fills(self, order: Order, okx_order_id: str) -> List[Fill]:
        """Poll order status until filled or timeout."""
        start_time = time.time()
        fills: List[Fill] = []
        
        while time.time() - start_time < self._max_fill_wait:
            # Query order details
            response = _okx_request('GET', '/api/v5/trade/order', 
                                   params={'instId': order.inst_id, 'ordId': okx_order_id})
            
            if response.get('code') != '0':
                self._logger.warning(f"Failed to query order status: {response.get('msg')}")
                time.sleep(0.5)
                continue

            data_list = response.get('data', [])
            if not data_list:
                time.sleep(0.5)
                continue

            order_info = data_list[0]
            state = order_info.get('state', '')
            filled_sz = float(order_info.get('accFillSz', '0'))
            
            self._logger.debug(f"Order {okx_order_id} state: {state}, filled: {filled_sz}")

            if state in ['filled', 'partially_filled']:
                # Query fills
                fill_response = _okx_request('GET', '/api/v5/trade/fills', 
                                            params={'ordId': okx_order_id})
                self._logger.info(f"Fill response: {fill_response}")
                if fill_response.get('code') == '0':
                    fill_data_list = fill_response.get('data', [])
                    for fill_data in fill_data_list:
                        # Convert OKX fill to our Fill format
                        # OKX fee can be negative (maker rebate) or positive (taker fee)
                        # We take absolute value for consistency
                        okx_fee = float(fill_data.get('fee', '0'))
                        fee_abs = abs(okx_fee)
                        
                        fill = Fill(
                            inst_id=order.inst_id,
                            ts=int(fill_data.get('ts', '0')),
                            side=Side.BUY if fill_data.get('side') == 'buy' else Side.SELL,
                            price=float(fill_data.get('fillPx', '0')),
                            quantity=float(fill_data.get('fillSz', '0')),
                            fee=fee_abs,
                            meta={'okx_order_id': okx_order_id, 'okx_fee_raw': okx_fee}
                        )
                        fills.append(fill)
                
                if state == 'filled':
                    self._logger.info(f"Order {okx_order_id} fully filled: {len(fills)} fill(s)")
                    break
            
            elif state in ['canceled', 'live'] and filled_sz == 0:
                # Order was canceled or not yet executed
                self._logger.warning(f"Order {okx_order_id} ended with state: {state}")
                break

            time.sleep(0.5)

        if not fills:
            self._logger.warning(f"No fills received for order {okx_order_id} within timeout")
        
        return fills

