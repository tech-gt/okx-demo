from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .types import Order, Fill, PortfolioState


class Broker(ABC):
    """Abstract broker that accepts orders and returns fills and portfolio state."""

    @abstractmethod
    def submit(self, order: Order) -> List[Fill]:
        """Submit a single order and return fills (can be empty)."""

    @abstractmethod
    def get_portfolio(self) -> PortfolioState:
        """Return current portfolio state."""


