#!/usr/bin/env python3
import os
import json
import threading
import time
import datetime
import hmac
import hashlib
import base64

import websocket
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# 环境与密钥
API_KEY = os.getenv('OKX_API_KEY', '')
API_SECRET = os.getenv('OKX_API_SECRET', '')
API_PASSPHRASE = os.getenv('OKX_API_PASSPHRASE', '')
SIMULATED_HEADER = os.getenv('OKX_SIMULATED', '1')
BASE_URL = os.getenv('OKX_BASE_URL', 'https://www.okx.com')

# WebSocket 私有地址
# 纸交易环境建议使用 wspap 域名
WS_PRIVATE_URL = os.getenv('OKX_WS_PRIVATE_URL', 'wss://wspap.okx.com:8443/ws/v5/private')

# 下单参数（用报价币金额下单，便于满足最小单）
INST_ID = os.getenv('OKX_WS_INST_ID', 'BTC-USDT')
QUOTE_SZ = os.getenv('OKX_WS_QUOTE_SZ', '10')  # 花费 10 USDT 买入 BTC


def iso_timestamp():
    return datetime.datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'

def epoch_timestamp():
    # 以秒为单位（带小数），WS 登录需要此格式
    return str(time.time())


def sign_ws_login(timestamp: str) -> str:
    # WS 登录签名: timestamp + 'GET' + '/users/self/verify'
    message = f"{timestamp}GET/users/self/verify"
    mac = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


def okx_request(method: str, path: str, body=None, params=None, timeout: int = 10):
    ts = iso_timestamp()
    query = ''
    if params:
        from urllib.parse import urlencode
        query = '?' + urlencode(params, safe=':/')
    body_str = json.dumps(body, separators=(',', ':')) if body else ''
    prehash_path = f"{path}{query}"

    # REST 签名: timestamp + method + requestPath + body
    message = f"{ts}{method.upper()}{prehash_path}{body_str}"
    mac = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    signature = base64.b64encode(mac.digest()).decode()

    headers = {
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': ts,
        'OK-ACCESS-PASSPHRASE': API_PASSPHRASE,
        'Content-Type': 'application/json',
        'x-simulated-trading': SIMULATED_HEADER,
    }

    url = f"{BASE_URL}{path}"
    if method.upper() == 'POST':
        resp = requests.post(url, data=body_str, headers=headers, timeout=timeout)
    elif method.upper() == 'GET':
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    else:
        raise ValueError('Unsupported method')

    try:
        data = resp.json()
    except ValueError:
        data = {'status_code': resp.status_code, 'text': resp.text}
    data['_http_status'] = resp.status_code
    return data


def place_spot_market_order_quote(instId: str, quote_usdt: str):
    body = {
        'instId': instId,
        'tdMode': 'cash',
        'side': 'buy',
        'ordType': 'market',
        'tgtCcy': 'quote_ccy',
        'sz': quote_usdt,
    }
    return okx_request('POST', '/api/v5/trade/order', body=body)


def run_ws_private(duration_seconds: int = 25):
    """登录私有 WS，订阅订单，并触发一笔下单以产生订单事件。"""

    # 在 on_open 中完成登录
    def on_open(ws):
        ts = epoch_timestamp()
        login_msg = {
            'op': 'login',
            'args': [{
                'apiKey': API_KEY,
                'passphrase': API_PASSPHRASE,
                'timestamp': ts,
                'sign': sign_ws_login(ts),
            }]
        }
        print('WS 打开，登录中...')
        ws.send(json.dumps(login_msg))

        # 心跳
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

    # 标志位：登录成功后再订阅与下单
    state = {
        'logged_in': False,
        'subscribed_orders': False,
        'order_sent': False,
    }

    def on_message(ws, message):
        try:
            msg = json.loads(message)
        except Exception:
            print('收到非 JSON 消息:', message[:120])
            return

        # 登录结果
        if isinstance(msg, dict) and msg.get('event') == 'login':
            if msg.get('code') == '0':
                state['logged_in'] = True
                print('登录成功，开始订阅 orders（SPOT）')
                sub_orders = {
                    'op': 'subscribe',
                    'args': [{'channel': 'orders', 'instType': 'SPOT'}]
                }
                ws.send(json.dumps(sub_orders))
            else:
                print('登录失败:', msg)
            return

        # 订阅事件
        if isinstance(msg, dict) and msg.get('event') == 'subscribe':
            arg = msg.get('arg', {})
            if arg.get('channel') == 'orders':
                state['subscribed_orders'] = True
                print('已订阅 orders，准备触发一笔市价单以产生事件')

                def trigger_order():
                    time.sleep(2)  # 等待订阅稳定
                    order = place_spot_market_order_quote(INST_ID, QUOTE_SZ)
                    print('下单响应:', order)
                    state['order_sent'] = True
                threading.Thread(target=trigger_order, daemon=True).start()
            return

        # 忽略心跳
        if isinstance(msg, dict) and msg.get('op') == 'pong':
            return

        # 处理订单推送
        arg = msg.get('arg', {})
        data_list = msg.get('data', [])
        if arg.get('channel') == 'orders':
            for d in data_list:
                # 常见字段: ordId, state, side, ordType, instId, cTime, fillSz, fillPx, accFillSz
                ord_id = d.get('ordId')
                state_s = d.get('state')
                side = d.get('side')
                inst_id = d.get('instId')
                acc_fill_sz = d.get('accFillSz')
                fill_px = d.get('fillPx')
                print(f"订单更新: ordId={ord_id} instId={inst_id} side={side} state={state_s} accFillSz={acc_fill_sz} fillPx={fill_px}")
        else:
            # 其他消息直接打印
            print('消息:', msg)

    def on_error(ws, error):
        print('WS 错误:', error)

    def on_close(ws, close_status_code, close_msg):
        print('WS 关闭:', close_status_code, close_msg)

    # 在 URL 上追加模拟盘参数，避免环境不匹配
    effective_url = WS_PRIVATE_URL
    if str(SIMULATED_HEADER).lower() in {'1', 'true', 'yes'} and 'x-simulated-trading' not in effective_url:
        effective_url += ('&' if '?' in effective_url else '?') + 'x-simulated-trading=true'

    headers = []  # 仅使用 URL 参数保证环境一致

    ws = websocket.WebSocketApp(
        effective_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        header=headers,
    )

    print('连接到:', effective_url, ' 账户:', API_KEY[:6] + '***', '订阅品种:', INST_ID)
    ws.run_forever(ping_interval=0)


if __name__ == '__main__':
    run_ws_private(duration_seconds=int(os.getenv('OKX_WS_DURATION', '25')))