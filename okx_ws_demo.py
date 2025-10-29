#!/usr/bin/env python3
import os
import json
import threading
import time

import websocket

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

WS_PUBLIC_URL = os.getenv('OKX_WS_PUBLIC_URL', 'wss://ws.okx.com:8443/ws/v5/public')
INST_ID = os.getenv('OKX_WS_INST_ID', 'BTC-USDT')
SIMULATED_HEADER = os.getenv('OKX_SIMULATED', '1')  # 与 REST 保持一致；公共行情可忽略


def _format_ticker(data: dict) -> str:
    last = data.get('last')
    bid = data.get('bidPx')
    ask = data.get('askPx')
    ts = data.get('ts')
    return f"Ticker {INST_ID} last={last} bid={bid} ask={ask} ts={ts}"


def _format_trade(d: dict) -> str:
    return (
        f"Trade {INST_ID} side={d.get('side')} px={d.get('px')} sz={d.get('sz')} ts={d.get('ts')}"
    )


def run_ws(duration_seconds: int = 15):
    """运行 WebSocket 订阅，默认持续 duration_seconds 秒后退出。"""

    subs_msg = {
        'op': 'subscribe',
        'args': [
            {'channel': 'tickers', 'instId': INST_ID},
            {'channel': 'trades', 'instId': INST_ID},
        ],
    }

    def on_open(ws):
        print('WS 打开，发送订阅:', subs_msg)
        ws.send(json.dumps(subs_msg))

        # 简单心跳：每 25s 发送一次 {op: ping}
        def heartbeat():
            while ws.keep_running:
                time.sleep(25)
                try:
                    ws.send(json.dumps({'op': 'ping'}))
                except Exception:
                    break

        threading.Thread(target=heartbeat, daemon=True).start()

        # 定时关闭
        def closer():
            time.sleep(duration_seconds)
            try:
                print(f'到时自动退出（{duration_seconds}s）')
                ws.close()
            except Exception:
                pass

        threading.Thread(target=closer, daemon=True).start()

    def on_message(ws, message):
        try:
            msg = json.loads(message)
        except Exception:
            print('收到非 JSON 消息:', message[:120])
            return

        # 订阅确认或心跳
        if isinstance(msg, dict) and msg.get('event') in {'subscribe', 'error'}:
            print('事件:', msg)
            return
        if isinstance(msg, dict) and msg.get('op') in {'pong'}:
            return

        # 行情数据
        arg = msg.get('arg', {})
        data_list = msg.get('data', [])
        channel = arg.get('channel')

        if channel == 'tickers':
            for d in data_list:
                print(_format_ticker(d))
        elif channel == 'trades':
            for d in data_list:
                print(_format_trade(d))
        else:
            # 其他消息直接打印
            print('消息:', msg)

    def on_error(ws, error):
        print('WS 错误:', error)

    def on_close(ws, close_status_code, close_msg):
        print('WS 关闭:', close_status_code, close_msg)

    headers = [f"x-simulated-trading: {SIMULATED_HEADER}"]

    ws = websocket.WebSocketApp(
        WS_PUBLIC_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        header=headers,
    )

    print('连接到:', WS_PUBLIC_URL, ' 订阅品种:', INST_ID)
    ws.run_forever(ping_interval=0)  # 使用应用层心跳，不用原生 ping


if __name__ == '__main__':
    # 可通过环境变量调整：OKX_WS_PUBLIC_URL、OKX_WS_INST_ID、OKX_SIMULATED
    # 或简单修改 duration_seconds
    run_ws(duration_seconds=int(os.getenv('OKX_WS_DURATION', '15')))