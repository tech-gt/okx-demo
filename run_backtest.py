#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from quant.adapters.csv_feed import CsvTickFeed
from quant.adapters.paper_broker import PaperBroker
from quant.core.risk import RiskManager
from quant.engines.trading_loop import TradingEngine
from quant.strategies.sma_cross import SmaCrossStrategy, SmaConfig
from quant.utils import setup_logging


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    
    if len(sys.argv) < 3:
        logger.error("Usage: run_backtest.py <csv_path> <inst_id>")
        sys.exit(1)

    csv_path = sys.argv[1]
    inst_id = sys.argv[2]

    feed = CsvTickFeed(csv_path=csv_path, inst_id=inst_id)
    broker = PaperBroker(starting_cash=float(os.getenv("BT_START_CASH", "10000")))
    risk = RiskManager(max_notional_per_order=float(os.getenv("BT_MAX_NOTIONAL", "1e9")))

    sma_cfg = SmaConfig(
        short_window=int(os.getenv("BT_SMA_SHORT", "50")),
        long_window=int(os.getenv("BT_SMA_LONG", "200")),
        quote_per_trade=float(os.getenv("BT_QUOTE_PER_TRADE", "50")),
        min_cross_diff_pct=float(os.getenv("BT_MIN_CROSS_DIFF_PCT", "0.01")),
        cooldown_seconds=int(os.getenv("BT_COOLDOWN_SECONDS", "300")),
    )
    strat = SmaCrossStrategy(inst_ids=[inst_id], cfg=sma_cfg)

    engine = TradingEngine(strategy=strat, feed=feed, broker=broker, risk=risk)
    logger.info(f"Starting backtest for: {inst_id}")
    engine.run(duration_ticks=None)
    logger.info(f"Final portfolio: {broker.get_portfolio()}")


if __name__ == "__main__":
    main()


