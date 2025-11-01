from __future__ import annotations

import os
import json
import threading
import time
import logging
from typing import Iterator, List, Optional
from queue import Queue, Empty

import websocket

from ..core.datafeed import MarketDataFeed
from ..core.types import Tick


class OkxWsTickerFeed(MarketDataFeed):
    """OKX WebSocket ticker feed for real-time market data.

    Uses OKX public WebSocket v5 API to stream ticker data.
    """

    def __init__(self, inst_ids: List[str]) -> None:
        self._inst_ids = inst_ids
        self._ws_url = os.getenv("OKX_WS_PUBLIC_URL", "wss://ws.okx.com:8443/ws/v5/public")
        self._sim_hdr = os.getenv("OKX_SIMULATED", "1")
        self._queue: Queue[Tick] = Queue()
        self._ws_app: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False
        self._logger = logging.getLogger(__name__)

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        self._logger.info("WS opened, subscribing to tickers")
        subs_msg = {
            "op": "subscribe",
            "args": [{"channel": "tickers", "instId": inst_id} for inst_id in self._inst_ids],
        }
        ws.send(json.dumps(subs_msg))

        # Heartbeat every 25s
        def heartbeat():
            while ws.keep_running and self._running:
                time.sleep(25)
                try:
                    ws.send(json.dumps({"op": "ping"}))
                except Exception:
                    break

        threading.Thread(target=heartbeat, daemon=True).start()

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        try:
            msg = json.loads(message)
        except Exception as e:
            self._logger.error(f"Invalid JSON message: {e}")
            return

        # Subscription confirmation or heartbeat
        event = msg.get("event")
        if event == "subscribe":
            self._logger.info(f"Subscription confirmed: {msg.get('arg')}")
            return
        elif event == "error":
            # Log errors, but don't spam for heartbeat issues
            error_msg = msg.get("msg", "")
            if "ping" in error_msg.lower():
                self._logger.debug(f"Heartbeat error (ignore): {msg}")
            else:
                self._logger.warning(f"WS error: {msg}")
            return
        if msg.get("op") == "pong":
            return

        # Ticker data
        arg = msg.get("arg", {})
        channel = arg.get("channel")
        if channel != "tickers":
            return

        data_list = msg.get("data", [])
        for d in data_list:
            try:
                inst_id = d.get("instId")
                last = float(d.get("last") or 0)
                bid = float(d.get("bidPx")) if d.get("bidPx") else None
                ask = float(d.get("askPx")) if d.get("askPx") else None
                ts = int(d.get("ts") or 0)

                tick = Tick(inst_id=inst_id, ts=ts, last=last, bid=bid, ask=ask)
                self._queue.put(tick)
            except Exception as e:
                self._logger.error(f"Failed to parse tick: {e}")

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        self._logger.error(f"WS error: {error}")

    def _on_close(self, ws: websocket.WebSocketApp, close_status_code: int, close_msg: str) -> None:
        self._logger.info(f"WS closed: {close_status_code}, {close_msg}")

    def _ws_run_forever(self) -> None:
        """Run WebSocket in a separate thread."""
        self._ws_app.run_forever(ping_interval=0)

    def stream(self) -> Iterator[Tick]:
        """Start WebSocket and yield ticks from queue."""
        if self._running:
            raise RuntimeError("Feed already running")

        self._running = True
        headers = [f"x-simulated-trading: {self._sim_hdr}"]

        self._ws_app = websocket.WebSocketApp(
            self._ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            header=headers,
        )

        self._logger.info(f"Connecting to {self._ws_url}, subscribing: {self._inst_ids}")
        self._ws_thread = threading.Thread(target=self._ws_run_forever, daemon=True)
        self._ws_thread.start()

        # Wait a bit for connection
        time.sleep(2)

        try:
            while self._running:
                try:
                    tick = self._queue.get(timeout=1.0)
                    yield tick
                except Empty:
                    continue
        finally:
            self.close()

    def close(self) -> None:
        """Close WebSocket and stop feeding."""
        self._running = False
        if self._ws_app:
            try:
                self._ws_app.close()
            except Exception:
                pass
        if self._ws_thread:
            self._ws_thread.join(timeout=3)
