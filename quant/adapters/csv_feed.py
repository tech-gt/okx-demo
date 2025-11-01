from __future__ import annotations

import csv
from typing import Iterator

from ..core.datafeed import MarketDataFeed
from ..core.types import Tick


class CsvTickFeed(MarketDataFeed):
    """CSV-based tick feed for backtesting.

    Expected columns: ts,last[,bid,ask]
    """

    def __init__(self, csv_path: str, inst_id: str) -> None:
        self._csv_path = csv_path
        self._inst_id = inst_id

    def stream(self) -> Iterator[Tick]:
        with open(self._csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = int(row["ts"]) if row.get("ts") else 0
                last = float(row["last"]) if row.get("last") else 0.0
                bid = float(row["bid"]) if row.get("bid") else None
                ask = float(row["ask"]) if row.get("ask") else None
                yield Tick(inst_id=self._inst_id, ts=ts, last=last, bid=bid, ask=ask)

    def close(self) -> None:
        pass


