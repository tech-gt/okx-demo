from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List
import logging
import time

from ..core.strategy import Strategy
from ..core.types import Tick, Order, Side, OrderType


@dataclass
class SmaConfig:
    short_window: int = 5
    long_window: int = 20
    quote_per_trade: float = 50.0  # spend in quote currency per trade
    min_cross_diff_pct: float = 0.0  # Minimum percentage difference between SMAs to avoid whipsaw
    cooldown_seconds: int = 0  # Cooldown period after each trade to avoid over-trading


class SmaCrossStrategy(Strategy):
    def __init__(self, inst_ids: List[str], cfg: SmaConfig | None = None) -> None:
        self._inst_ids = inst_ids
        self._cfg = cfg or SmaConfig()
        self._short: Dict[str, Deque[float]] = {i: deque(maxlen=self._cfg.short_window) for i in inst_ids}
        self._long: Dict[str, Deque[float]] = {i: deque(maxlen=self._cfg.long_window) for i in inst_ids}
        self._above: Dict[str, bool] = {i: False for i in inst_ids}
        self._last_trade_ts: Dict[str, float] = {}
        self._logger = logging.getLogger(__name__)

    def on_start(self) -> None:
        self._logger.info("Strategy started (SMA cross)")

    def _avg(self, d: Deque[float]) -> float:
        return sum(d) / len(d) if d else 0.0

    def on_tick(self, tick: Tick) -> Iterable[Order]:
        if tick.inst_id not in self._short:
            return []
        
        self._short[tick.inst_id].append(tick.last)
        self._long[tick.inst_id].append(tick.last)

        s = self._avg(self._short[tick.inst_id])
        l = self._avg(self._long[tick.inst_id])
        
        short_len = len(self._short[tick.inst_id])
        long_len = len(self._long[tick.inst_id])
        
        if short_len < self._cfg.short_window or long_len < self._cfg.long_window:
            self._logger.info(f"{tick.inst_id} Price={tick.last:.6f} Warming up (short={short_len}/{self._cfg.short_window}, long={long_len}/{self._cfg.long_window})")
            return []

        was_above = self._above[tick.inst_id]
        now_above = s > l
        self._above[tick.inst_id] = now_above

        diff_pct = abs(s - l) / l * 100 if l > 0 else 0
        
        self._logger.info(f"{tick.inst_id} Price={tick.last:.2f} SMA(short={self._cfg.short_window})={s:.2f} SMA(long={self._cfg.long_window})={l:.2f} Above={was_above}->{now_above} Diff={diff_pct:.3f}%")

        # Check cooldown period
        now = time.time()
        last_trade = self._last_trade_ts.get(tick.inst_id, 0)
        if now - last_trade < self._cfg.cooldown_seconds:
            remaining = self._cfg.cooldown_seconds - (now - last_trade)
            self._logger.info(f"{tick.inst_id} In cooldown, remaining {remaining:.1f}s, skipping trade")
            return []

        # Cross up: buy; cross down: sell (close by symmetric amount)
        if not was_above and now_above:
            # Check minimum difference to avoid whipsaw
            if diff_pct < self._cfg.min_cross_diff_pct:
                self._logger.info(f"{tick.inst_id} Golden cross diff {diff_pct:.3f}% < min {self._cfg.min_cross_diff_pct:.3f}%, skipping")
                return []
            
            self._logger.info(f"GOLDEN CROSS detected on {tick.inst_id}, generating BUY order")
            self._last_trade_ts[tick.inst_id] = now
            return [
                Order(
                    inst_id=tick.inst_id,
                    side=Side.BUY,
                    order_type=OrderType.MARKET,
                    quantity=0.0,
                    quote_quantity=self._cfg.quote_per_trade,
                )
            ]
        if was_above and not now_above:
            # Check minimum difference to avoid whipsaw
            if diff_pct < self._cfg.min_cross_diff_pct:
                self._logger.info(f"{tick.inst_id} Death cross diff {diff_pct:.3f}% < min {self._cfg.min_cross_diff_pct:.3f}%, skipping")
                return []
            
            self._logger.info(f"DEATH CROSS detected on {tick.inst_id}, generating SELL order")
            self._last_trade_ts[tick.inst_id] = now
            return [
                Order(
                    inst_id=tick.inst_id,
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    quantity=0.0,
                    quote_quantity=self._cfg.quote_per_trade,
                )
            ]
        return []

    def on_end(self) -> List[Order]:
        self._logger.info("Strategy ended")
        return []


