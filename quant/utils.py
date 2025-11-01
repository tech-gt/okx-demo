from __future__ import annotations

import logging
import os
import sys
import datetime
import hmac
import hashlib
import base64
import json
from typing import List
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


def get_funding_rate(inst_id: str) -> float | None:
    """Get current funding rate for a swap/perp instrument.
    
    Args:
        inst_id: Instrument ID (e.g., 'BTC-USDT-SWAP')
        
    Returns:
        Current funding rate as float (e.g., 0.0001 for 0.01%), or None on error
        
    Example:
        >>> rate = get_funding_rate('BTC-USDT-SWAP')
        >>> if rate and rate > 0.0001:  # > 0.01%
        >>>     print(f"High funding rate: {rate*100:.4f}%")
    """
    result = _okx_request('GET', '/api/v5/public/funding-rate', params={'instId': inst_id})
    
    if result.get('code') != '0':
        logger = get_logger(__name__)
        logger.warning(f"Failed to get funding rate for {inst_id}: {result.get('msg', 'Unknown error')}")
        return None
    
    data_list = result.get('data', [])
    if not data_list:
        return None
    
    try:
        funding_rate_str = data_list[0].get('fundingRate', '0')
        return float(funding_rate_str)
    except (KeyError, ValueError, TypeError) as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to parse funding rate response: {e}")
        return None


def list_swap_instruments(quote_ccy: str = 'USDT') -> List[str]:
    """List all swap instruments for a given quote currency.
    
    Args:
        quote_ccy: Quote currency (e.g., 'USDT', 'USDC')
        
    Returns:
        List of instrument IDs (e.g., ['BTC-USDT-SWAP', 'ETH-USDT-SWAP', ...])
    """
    
    result = _okx_request('GET', '/api/v5/public/instruments', 
                          params={'instType': 'SWAP', 'quoteCcy': quote_ccy})
    
    if result.get('code') != '0':
        logger = get_logger(__name__)
        logger.warning(f"Failed to list swap instruments: {result.get('msg', 'Unknown error')}")
        return []
    
    data_list = result.get('data', [])
    inst_ids = []
    for item in data_list:
        inst_id = item.get('instId')
        if inst_id:
            inst_ids.append(inst_id)
    
    return inst_ids


def get_funding_rates_for_all(quote_ccy: str = 'USDT') -> dict[str, float]:
    """Get funding rates for all swap instruments.
    
    Args:
        quote_ccy: Quote currency (e.g., 'USDT')
        
    Returns:
        Dictionary mapping inst_id to funding rate (e.g., {'BTC-USDT-SWAP': 0.0001, ...})
    """
    inst_ids = list_swap_instruments(quote_ccy)
    rates: dict[str, float] = {}
    
    for inst_id in inst_ids:
        rate = get_funding_rate(inst_id)
        if rate is not None:
            rates[inst_id] = rate
    
    return rates

