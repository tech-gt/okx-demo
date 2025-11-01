from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True)
class Instrument:
    inst_id: str  # e.g. "BTC-USDT"
    inst_type: str = "SPOT"  # SPOT, SWAP, FUTURES, OPTION


@dataclass
class Bar:
    inst_id: str
    ts: int  # epoch ms
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Tick:
    inst_id: str
    ts: int  # epoch ms
    last: float
    bid: Optional[float] = None
    ask: Optional[float] = None


@dataclass
class Order:
    inst_id: str
    side: Side
    order_type: OrderType
    quantity: float  # base quantity for SPOT; for quote-amount, use quote_quantity
    quote_quantity: Optional[float] = None  # if set, use quote currency amount
    price: Optional[float] = None
    client_order_id: Optional[str] = None


@dataclass
class Fill:
    inst_id: str
    ts: int
    side: Side
    price: float
    quantity: float
    fee: float = 0.0
    meta: Optional[Dict[str, str]] = None


@dataclass
class Position:
    inst_id: str
    quantity: float
    avg_price: float


@dataclass
class PortfolioState:
    cash: float  # quote currency, e.g. USDT
    positions: Dict[str, Position]


