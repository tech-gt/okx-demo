from __future__ import annotations

import os
import time
from typing import Iterator, List

import requests

from ..core.datafeed import MarketDataFeed
from ..core.types import Tick


class OkxRestTickerFeed(MarketDataFeed):
    """Simple REST polling feed for OKX tickers (for paper/demo)."""

    def __init__(self, inst_ids: List[str], interval_sec: float = 1.0) -> None:
        self._inst_ids = inst_ids
        self._interval = interval_sec
        self._base_url = os.getenv("OKX_BASE_URL", "https://www.okx.com")
        self._sim_hdr = os.getenv("OKX_SIMULATED", "1")
        self._running = True

    def _fetch(self, inst_id: str) -> Tick | None:
        try:
            url = f"{self._base_url}/api/v5/market/ticker"
            resp = requests.get(
                url,
                params={"instId": inst_id},
                headers={"x-simulated-trading": self._sim_hdr},
                timeout=5,
            )
            data = resp.json()
            arr = data.get("data") or []
            if not arr:
                return None
            d0 = arr[0]
            last = float(d0["last"])
            bid = float(d0["bidPx"]) if d0.get("bidPx") else None
            ask = float(d0["askPx"]) if d0.get("askPx") else None
            ts = int(d0.get("ts") or 0)
            return Tick(inst_id=inst_id, ts=ts, last=last, bid=bid, ask=ask)
        except Exception:
            return None

    def stream(self) -> Iterator[Tick]:
        while self._running:
            for inst_id in self._inst_ids:
                tick = self._fetch(inst_id)
                if tick is not None:
                    yield tick
            time.sleep(self._interval)

    def close(self) -> None:
        self._running = False


