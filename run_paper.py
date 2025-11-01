#!/usr/bin/env python3
from __future__ import annotations

import os
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from quant.adapters.okx_rest_feed import OkxRestTickerFeed
from quant.adapters.paper_broker import PaperBroker
from quant.core.risk import RiskManager
from quant.engines.paper_loop import PaperEngine
from quant.strategies.sma_cross import SmaCrossStrategy, SmaConfig
from quant.utils import setup_logging, get_okx_cash_balance


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    
    inst_ids = os.getenv("OKX_PAPER_INST_IDS", "BTC-USDT").split(",")
    inst_ids = [i.strip() for i in inst_ids if i.strip()]
    interval = float(os.getenv("OKX_PAPER_INTERVAL", "1.0"))
    duration_ticks_env = os.getenv("OKX_PAPER_TICKS", "200")
    duration_ticks = int(duration_ticks_env) if duration_ticks_env else None
    
    # Enable dry run mode via environment variable
    dry_run = os.getenv("PAPER_DRY_RUN", "false").lower() in ("true", "1", "yes")

    feed = OkxRestTickerFeed(inst_ids=inst_ids, interval_sec=interval)
    
    # Get starting cash: prefer OKX API if PAPER_USE_REAL_BALANCE is set
    starting_cash = float(os.getenv("PAPER_START_CASH", "10000"))
    if os.getenv("PAPER_USE_REAL_BALANCE", "false").lower() in ("true", "1", "yes"):
        currency = os.getenv("PAPER_BALANCE_CURRENCY", "USDT")
        starting_cash = get_okx_cash_balance(currency)
        if starting_cash == 0.0:
            logger.warning(f"Failed to get balance from OKX API, using default: 10000")
            starting_cash = 10000.0
        else:
            logger.info(f"Using real balance from OKX: {starting_cash:.4f} {currency}")
    
    broker = PaperBroker(starting_cash=starting_cash)
    risk = RiskManager(max_notional_per_order=float(os.getenv("PAPER_MAX_NOTIONAL", "200")))

    sma_cfg = SmaConfig(
        short_window=int(os.getenv("SMA_SHORT", "5")),
        long_window=int(os.getenv("SMA_LONG", "20")),
        quote_per_trade=float(os.getenv("SMA_QUOTE_PER_TRADE", "50")),
        min_cross_diff_pct=float(os.getenv("SMA_MIN_CROSS_DIFF_PCT", "0.01")),
        cooldown_seconds=int(os.getenv("SMA_COOLDOWN_SECONDS", "300")),
    )
    strat = SmaCrossStrategy(inst_ids=inst_ids, cfg=sma_cfg)

    # Get max position value from environment (in quote currency)
    max_pos_val_str = os.getenv("MAX_POSITION_VALUE")
    max_position_value = float(max_pos_val_str) if max_pos_val_str else None
    
    engine = PaperEngine(strategy=strat, feed=feed, broker=broker, risk=risk, dry_run=dry_run, 
                         max_position_value=max_position_value)
    
    mode_str = "[DRY RUN]" if dry_run else "[LIVE]"
    if max_position_value:
        logger.info(f"Max position value: {max_position_value} USDT")
    logger.info(f"Starting paper engine {mode_str}: {inst_ids}")
    engine.run(duration_ticks=duration_ticks)


if __name__ == "__main__":
    main()


