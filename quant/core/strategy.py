from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from .types import Tick, Order


class Strategy(ABC):
    """Strategy base class.

    A strategy receives market data updates and outputs orders.
    """

    @abstractmethod
    def on_start(self) -> None:
        """Called once before the event loop starts."""

    @abstractmethod
    def on_tick(self, tick: Tick) -> Iterable[Order]:
        """Handle tick and optionally yield new orders."""

    @abstractmethod
    def on_end(self) -> List[Order]:
        """Called when the loop ends; can return final orders to close positions."""


