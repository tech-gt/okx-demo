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
from quant.strategies.funding_arbitrage import FundingArbitrageStrategy, FundingArbitrageConfig
from quant.utils import setup_logging, get_okx_cash_balance


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Configuration from environment variables
    swap_inst_id = os.getenv("FUNDING_ARB_SWAP_INST_ID", "BTC-USDT-SWAP")
    spot_inst_id = os.getenv("FUNDING_ARB_SPOT_INST_ID", "BTC-USDT")
    
    # Extract base symbol from swap inst_id (e.g., "BTC-USDT-SWAP" -> "BTC-USDT")
    # But use the provided spot_inst_id if available
    if spot_inst_id == "BTC-USDT" and swap_inst_id != "BTC-USDT-SWAP":
        # Try to infer spot from swap
        if swap_inst_id.endswith("-SWAP"):
            spot_inst_id = swap_inst_id.replace("-SWAP", "")
    
    # Instrument IDs to monitor (both spot and swap)
    inst_ids = [spot_inst_id, swap_inst_id]
    
    logger.info(f"Funding Rate Arbitrage Strategy")
    logger.info(f"Swap instrument: {swap_inst_id}")
    logger.info(f"Spot instrument: {spot_inst_id}")
    logger.info(f"Monitoring instruments: {inst_ids}")
    
    # Enable dry run mode via environment variable
    dry_run = os.getenv("PAPER_DRY_RUN", "false").lower() in ("true", "1", "yes")
    
    # Use WebSocket feed for real-time data (both spot and swap)
    feed = OkxWsTickerFeed(inst_ids=inst_ids)
    
    # Use OKX broker (supports both simulated and live trading)
    broker = OkxBroker(max_fill_wait_seconds=10.0)
    
    # Risk manager
    max_notional = float(os.getenv("PAPER_MAX_NOTIONAL", "2000"))
    risk = RiskManager(max_notional_per_order=max_notional)
    
    # Strategy configuration
    cfg = FundingArbitrageConfig(
        swap_inst_id=swap_inst_id,
        spot_inst_id=spot_inst_id,
        min_funding_rate=float(os.getenv("FUNDING_ARB_MIN_RATE", "0.0001")),  # 0.01% default
        max_funding_rate_to_close=float(os.getenv("FUNDING_ARB_MAX_RATE_TO_CLOSE", "0.00005")),  # 0.005% default
        position_size_usdt=float(os.getenv("FUNDING_ARB_POSITION_SIZE", "1000")),
        funding_check_interval=float(os.getenv("FUNDING_ARB_CHECK_INTERVAL", "300")),  # 5 minutes
        cooldown_seconds=float(os.getenv("FUNDING_ARB_COOLDOWN", "60")),  # 1 minute
    )
    
    # Create strategy with broker reference
    strategy = FundingArbitrageStrategy(cfg, broker=broker)
    
    # Get max position value from environment (in quote currency)
    max_pos_val_str = os.getenv("MAX_POSITION_VALUE")
    max_position_value = float(max_pos_val_str) if max_pos_val_str else None
    
    engine = TradingEngine(
        strategy=strategy, 
        feed=feed, 
        broker=broker, 
        risk=risk, 
        dry_run=dry_run,
        max_position_value=max_position_value
    )
    
    mode_str = "[DRY RUN]" if dry_run else "[LIVE]"
    logger.info(f"Starting funding rate arbitrage engine {mode_str}")
    logger.info(f"Strategy will:")
    logger.info(f"  - Open position when funding rate >= {cfg.min_funding_rate*100:.4f}%")
    logger.info(f"  - Close position when funding rate <= {cfg.max_funding_rate_to_close*100:.4f}%")
    logger.info(f"  - Position size: {cfg.position_size_usdt} USDT")
    logger.info(f"  - Check funding rate every {cfg.funding_check_interval} seconds")
    
    try:
        engine.run(duration_ticks=None)  # Run indefinitely until interrupted
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")
    except Exception as e:
        logger.error(f"Engine error: {e}", exc_info=True)
    finally:
        logger.info("Final portfolio state:")
        portfolio = broker.get_portfolio()
        logger.info(f"Cash: {portfolio.cash:.4f} USDT")
        for inst_id, pos in portfolio.positions.items():
            logger.info(f"{inst_id}: qty={pos.quantity:.6f} avg_price={pos.avg_price:.4f}")


if __name__ == "__main__":
    main()

