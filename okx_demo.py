#!/usr/bin/env python3
import os
import sys
import datetime
import hmac
import hashlib
import base64
import json
from urllib.parse import urlencode

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

API_KEY = os.getenv('OKX_API_KEY')
API_SECRET = os.getenv('OKX_API_SECRET')
API_PASSPHRASE = os.getenv('OKX_API_PASSPHRASE')
BASE_URL = os.getenv('OKX_BASE_URL', 'https://www.okx.com')
SIMULATED_HEADER = os.getenv('OKX_SIMULATED', '1')  # '1' 启用模拟盘


def iso_timestamp():
    return datetime.datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'


def sign_message(timestamp: str, method: str, request_path: str, body_str: str = '') -> str:
    # 预哈希串: timestamp + method + requestPath + body
    message = f"{timestamp}{method.upper()}{request_path}{body_str}"
    mac = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


def okx_request(method: str, path: str, params=None, body=None, timeout: int = 10):
    ts = iso_timestamp()
    query = ''
    if params:
        # 将查询串也纳入签名
        query = '?' + urlencode(params, safe=':/')
    body_str = json.dumps(body, separators=(',', ':')) if body else ''
    prehash_path = f"{path}{query}"
    signature = sign_message(ts, method, prehash_path, body_str)

    headers = {
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': ts,
        'OK-ACCESS-PASSPHRASE': API_PASSPHRASE,
        'Content-Type': 'application/json',
        'x-simulated-trading': SIMULATED_HEADER,
    }

    url = f"{BASE_URL}{path}"
    try:
        if method.upper() == 'GET':
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        elif method.upper() == 'POST':
            # 为确保与签名一致，POST 使用 body 的字符串形式
            resp = requests.post(url, data=body_str, headers=headers, timeout=timeout)
        else:
            raise ValueError(f"Unsupported method: {method}")
    except requests.RequestException as e:
        return {'error': str(e), 'method': method, 'path': path, 'params': params, 'body': body}

    try:
        data = resp.json()
    except ValueError:
        data = {'status_code': resp.status_code, 'text': resp.text}

    data['_http_status'] = resp.status_code
    return data


def get_server_time():
    return okx_request('GET', '/api/v5/public/time')


def get_balance(ccy: str | None = None):
    params = {'ccy': ccy} if ccy else None
    return okx_request('GET', '/api/v5/account/balance', params=params)


def place_spot_market_order(instId: str = 'BTC-USDT', side: str = 'buy', sz: str = '10', tgtCcy: str = 'quote_ccy'):
    body = {
        'instId': instId,
        'tdMode': 'cash',
        'side': side,
        'ordType': 'market',
        'sz': sz,
        'tgtCcy': tgtCcy,
    }
    return okx_request('POST', '/api/v5/trade/order', body=body)


def main():
    print('OKX 模拟盘交易 Demo 开始')
    print('环境: BASE_URL=', BASE_URL, ' x-simulated-trading=', SIMULATED_HEADER)

    t = get_server_time()
    print('服务器时间:', t)

    bal = get_balance('USDT')
    print('USDT 余额查询结果:', bal)

    print('尝试下单: 现货市价买入 BTC-USDT, 花费 10 USDT')
    order = place_spot_market_order('BTC-USDT', 'buy', '10', 'quote_ccy')
    print('下单响应:', order)

    code = order.get('code')
    if code is None:
        print('响应体非标准，可能是网络或签名错误。')
        sys.exit(1)
    elif code != '0':
        print('OKX 返回错误 code=', code, ' msg=', order.get('msg'))
        sys.exit(1)
    else:
        print('下单成功，订单信息:', order.get('data'))


if __name__ == '__main__':
    main()