from __future__ import annotations

import time
from typing import List, Optional

from ..core.broker import Broker
from ..core.portfolio import Portfolio
from ..core.types import Order, Fill, PortfolioState, Side


class PaperBroker(Broker):
    """Very simple paper broker that fills at provided reference price.

    The engine is expected to pass a reference price when deciding orders; here we
    just consume orders and assume they are filled at the last known price which
    the engine provides.
    """

    def __init__(self, starting_cash: float = 10_000.0, fee_bps: float = 5.0) -> None:
        self._portfolio = Portfolio(cash=starting_cash)
        self._fee_bps = fee_bps
        self._last_price: dict[str, float] = {}

    def set_last_price(self, inst_id: str, price: float) -> None:
        self._last_price[inst_id] = price

    def _ref_price(self, inst_id: str, explicit: Optional[float] = None) -> Optional[float]:
        if explicit is not None:
            return explicit
        return self._last_price.get(inst_id)

    def submit(self, order: Order) -> List[Fill]:
        px = self._ref_price(order.inst_id, order.price)
        if px is None or px <= 0:
            return []

        qty: float
        if order.quote_quantity is not None and order.quote_quantity > 0:
            qty = order.quote_quantity / px
        else:
            qty = max(0.0, float(order.quantity))
        if qty == 0:
            return []

        ts = int(time.time() * 1000)
        fee = (px * qty) * (self._fee_bps / 10_000.0)
        fill = Fill(
            inst_id=order.inst_id,
            ts=ts,
            side=order.side,
            price=px,
            quantity=qty,
            fee=fee,
            meta={"client_order_id": order.client_order_id or ""},
        )
        self._portfolio.apply_fill(fill)
        return [fill]

    def get_portfolio(self) -> PortfolioState:
        return self._portfolio.snapshot()


