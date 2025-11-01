#!/usr/bin/env python3
from __future__ import annotations

import os
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from quant.adapters.okx_ws_feed import OkxWsTickerFeed
from quant.adapters.okx_broker import OkxBroker
from quant.core.risk import RiskManager
from quant.engines.trading_loop import TradingEngine
from quant.strategies.sma_cross import SmaCrossStrategy, SmaConfig
from quant.utils import setup_logging


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Check if we're in simulated trading mode
    simulated = os.getenv("OKX_SIMULATED", "1")
    mode_str = "SIMULATED" if simulated == "1" else "LIVE"
    logger.warning(f"🔴 Running in {mode_str} trading mode - orders will be sent to OKX!")
    
    if simulated != "1":
        confirm = input("⚠️  You are about to trade on LIVE market. Type 'YES' to confirm: ")
        if confirm != "YES":
            logger.info("Aborted by user")
            return
    
    inst_ids = os.getenv("OKX_REAL_INST_IDS", "DOGE-USDT").split(",")
    inst_ids = [i.strip() for i in inst_ids if i.strip()]
    duration_ticks_env = os.getenv("OKX_REAL_TICKS", "50")
    duration_ticks = int(duration_ticks_env) if duration_ticks_env else None
    
    # Enable dry run mode via environment variable
    dry_run = os.getenv("OKX_REAL_DRY_RUN", "false").lower() in ("true", "1", "yes")
    
    if dry_run:
        logger.info("⚠️  DRY RUN mode enabled - no actual orders will be submitted")

    # Use WebSocket feed for real-time data
    feed = OkxWsTickerFeed(inst_ids=inst_ids)
    
    # Use real OKX broker
    broker = OkxBroker(max_fill_wait_seconds=float(os.getenv("OKX_FILL_WAIT", "10")))
    risk = RiskManager(max_notional_per_order=float(os.getenv("OKX_REAL_MAX_NOTIONAL", "200")))

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
    
    engine = TradingEngine(strategy=strat, feed=feed, broker=broker, risk=risk, dry_run=dry_run, 
                         max_position_value=max_position_value)
    
    if max_position_value:
        logger.info(f"Max position value: {max_position_value} USDT")
    
    logger.info(f"Starting real trading engine with WebSocket feed [{mode_str}] {inst_ids}")
    engine.run(duration_ticks=duration_ticks)


if __name__ == "__main__":
    main()

