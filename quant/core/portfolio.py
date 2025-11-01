from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .types import PortfolioState, Position, Fill, Side


@dataclass
class Portfolio:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)

    def apply_fill(self, fill: Fill) -> None:
        qty_signed = fill.quantity if fill.side == Side.BUY else -fill.quantity

        pos = self.positions.get(fill.inst_id)
        if pos is None:
            if qty_signed == 0:
                return
            self.positions[fill.inst_id] = Position(
                inst_id=fill.inst_id,
                quantity=qty_signed,
                avg_price=fill.price,
            )
        else:
            new_qty = pos.quantity + qty_signed
            if new_qty == 0:
                self.positions.pop(fill.inst_id, None)
            elif (pos.quantity >= 0 and qty_signed > 0) or (pos.quantity <= 0 and qty_signed < 0):
                # Increase existing direction -> average price update
                total_cost = pos.avg_price * abs(pos.quantity) + fill.price * abs(qty_signed)
                new_avg = total_cost / abs(new_qty)
                pos.quantity = new_qty
                pos.avg_price = new_avg
            else:
                # Reducing or flipping position; keep avg on remaining
                pos.quantity = new_qty

        trade_cost = fill.price * fill.quantity
        sign = 1.0 if fill.side == Side.SELL else -1.0
        self.cash += sign * trade_cost - fill.fee

    def snapshot(self) -> PortfolioState:
        return PortfolioState(cash=self.cash, positions=dict(self.positions))


