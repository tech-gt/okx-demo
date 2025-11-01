from __future__ import annotations

from dataclasses import dataclass

from .types import Order, PortfolioState
import logging
logger = logging.getLogger(__name__)

@dataclass
class RiskManager:
    max_notional_per_order: float = 1_000.0  # quote currency cap per order

    def approve(self, order: Order, portfolio: PortfolioState, ref_price: float) -> bool:
        logger.info(f"Approving order: {order} with portfolio: {portfolio} and ref_price: {ref_price}")
        if order.quote_quantity is not None:
            notional = order.quote_quantity
        else:
            notional = (order.quantity or 0.0) * ref_price
        if notional <= 0:
            return False
        if notional > self.max_notional_per_order:
            return False
        if notional > portfolio.cash:
            return False
        return True


