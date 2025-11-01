from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Iterable

from .types import Tick


class MarketDataFeed(ABC):
    """Abstract market data feed producing ticks."""

    @abstractmethod
    def stream(self) -> Iterator[Tick]:
        """Yield Tick objects indefinitely or until exhausted."""

    @abstractmethod
    def close(self) -> None:
        """Release resources if any."""


