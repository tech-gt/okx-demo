from __future__ import annotations

import logging
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


def setup_logging(level: int = logging.INFO) -> None:
    """Setup logging with filename and line number format.
    
    Format includes:
    - Timestamp
    - Logger name (filename without extension)
    - Line number
    - Level
    - Message
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s -[%(filename)s:%(lineno)d] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


def _iso_timestamp() -> str:
    """Generate ISO timestamp for OKX API."""
    return datetime.datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'


def _sign_message(timestamp: str, method: str, request_path: str, body_str: str = '') -> str:
    """Sign OKX API request message."""
    message = f"{timestamp}{method.upper()}{request_path}{body_str}"
    api_secret = os.getenv('OKX_API_SECRET', '')
    mac = hmac.new(api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


def _okx_request(method: str, path: str, params=None, body=None, timeout: int = 10) -> dict:
    """Make authenticated OKX API request."""
    ts = _iso_timestamp()
    query = ''
    if params:
        query = '?' + urlencode(params, safe=':/')
    body_str = json.dumps(body, separators=(',', ':')) if body else ''
    prehash_path = f"{path}{query}"
    signature = _sign_message(ts, method, prehash_path, body_str)

    headers = {
        'OK-ACCESS-KEY': os.getenv('OKX_API_KEY', ''),
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': ts,
        'OK-ACCESS-PASSPHRASE': os.getenv('OKX_API_PASSPHRASE', ''),
        'Content-Type': 'application/json',
        'x-simulated-trading': os.getenv('OKX_SIMULATED', '1'),
    }

    base_url = os.getenv('OKX_BASE_URL', 'https://www.okx.com')
    url = f"{base_url}{path}"
    try:
        if method.upper() == 'GET':
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        elif method.upper() == 'POST':
            resp = requests.post(url, data=body_str, headers=headers, timeout=timeout)
        else:
            return {'error': f'Unsupported method: {method}', 'code': '-1'}
    except requests.RequestException as e:
        return {'error': str(e), 'code': '-1'}

    try:
        data = resp.json()
    except ValueError:
        data = {'status_code': resp.status_code, 'text': resp.text, 'code': '-1'}

    data['_http_status'] = resp.status_code
    return data


def get_okx_cash_balance(currency: str = 'USDT') -> float:
    """Get cash balance from OKX account.
    
    Returns the available balance in the specified currency, or 0.0 if API fails.
    This is useful for setting starting cash in paper trading to match your actual balance.
    
    Args:
        currency: Currency code (e.g. 'USDT', 'BTC', 'ETH')
        
    Returns:
        Available balance as float, or 0.0 on error
        
    Example:
        >>> balance = get_okx_cash_balance('USDT')
        >>> broker = PaperBroker(starting_cash=balance)
    """
    result = _okx_request('GET', '/api/v5/account/balance', params={'ccy': currency})
    
    if result.get('code') != '0':
        logger = get_logger(__name__)
        logger.warning(f"Failed to get balance from OKX API: {result.get('msg', 'Unknown error')}")
        return 0.0
    
    data_list = result.get('data', [])
    if not data_list:
        return 0.0
    
    # Parse balance from OKX response
    try:
        details = data_list[0].get('details', [])
        for detail in details:
            if detail.get('ccy') == currency:
                avail = detail.get('availBal', '0')
                return float(avail)
    except (KeyError, ValueError, TypeError) as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to parse balance response: {e}")
    
    return 0.0

