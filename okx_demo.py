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


def get_all_balances():
    """Get all asset balances in the account."""
    return okx_request('GET', '/api/v5/account/balance')


def get_positions():
    """Get all positions (spot and derivatives)."""
    return okx_request('GET', '/api/v5/account/positions')


def get_funding_rate(inst_id: str):
    """Get funding rate for a swap instrument."""
    return okx_request('GET', '/api/v5/public/funding-rate', params={'instId': inst_id})


def list_swap_instruments(quote_ccy: str = 'USDT'):
    """List all swap instruments."""
    return okx_request('GET', '/api/v5/public/instruments', 
                       params={'instType': 'SWAP', 'quoteCcy': quote_ccy})


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


def analyze_account_for_funding_arbitrage(balances_data, positions_data):
    """Analyze account status and provide funding rate arbitrage recommendations."""
    print("\n" + "=" * 70)
    print("Account Analysis for Funding Rate Arbitrage")
    print("=" * 70)
    
    # Parse balances
    available_usdt = 0.0
    total_usdt = 0.0
    other_assets = []
    
    if balances_data.get('code') == '0':
        data_list = balances_data.get('data', [])
        if data_list:
            details = data_list[0].get('details', [])
            for detail in details:
                ccy = detail.get('ccy', '')
                avail_bal = float(detail.get('availBal', '0'))
                eq = float(detail.get('eq', '0'))
                
                if ccy == 'USDT':
                    available_usdt = avail_bal
                    total_usdt = eq
                elif avail_bal > 0.001 or eq > 0.001:  # Filter out dust
                    other_assets.append({
                        'ccy': ccy,
                        'available': avail_bal,
                        'total': eq
                    })
    
    # Parse positions
    spot_positions = []
    swap_positions = []
    
    if positions_data.get('code') == '0':
        data_list = positions_data.get('data', [])
        for pos in data_list:
            inst_id = pos.get('instId', '')
            pos_size = float(pos.get('pos', '0'))
            avg_px = float(pos.get('avgPx', '0'))
            
            if abs(pos_size) < 1e-8:
                continue
            
            if '-SWAP' in inst_id:
                swap_positions.append({
                    'instId': inst_id,
                    'size': pos_size,
                    'avgPrice': avg_px,
                    'margin': pos.get('margin', '0'),
                    'upl': pos.get('upl', '0'),
                })
            else:
                spot_positions.append({
                    'instId': inst_id,
                    'size': pos_size,
                    'avgPrice': avg_px,
                })
    
    # Display account summary
    print(f"\n【Account Summary】")
    print(f"Available USDT: {available_usdt:,.2f} USDT")
    print(f"Total USDT: {total_usdt:,.2f} USDT")
    
    if other_assets:
        print(f"\nOther Assets:")
        for asset in sorted(other_assets, key=lambda x: x['total'], reverse=True):
            print(f"  {asset['ccy']}: Available={asset['available']:,.6f}, Total={asset['total']:,.6f}")
    
    if spot_positions:
        print(f"\n【Spot Positions】")
        for pos in spot_positions:
            print(f"  {pos['instId']}: {pos['size']:,.6f} @ {pos['avgPrice']:,.2f}")
    
    if swap_positions:
        print(f"\n【Swap Positions】")
        for pos in swap_positions:
            print(f"  {pos['instId']}: {pos['size']:,.6f} @ {pos['avgPrice']:,.2f}, "
                  f"Margin={pos['margin']}, UPL={pos['upl']}")
    
    # Get funding rates for major pairs
    print(f"\n【Funding Rate Analysis】")
    print("Checking funding rates for major pairs...")
    
    major_pairs = ['BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP', 
                   'DOGE-USDT-SWAP', 'XRP-USDT-SWAP', 'MATIC-USDT-SWAP']
    
    funding_opportunities = []
    
    for swap_inst_id in major_pairs:
        fr_resp = get_funding_rate(swap_inst_id)
        if fr_resp.get('code') == '0':
            data_list = fr_resp.get('data', [])
            if data_list:
                funding_rate = float(data_list[0].get('fundingRate', '0'))
                next_funding_time = data_list[0].get('nextFundingTime', '')
                
                # Calculate annualized rate (8h settlement, 3 times per day)
                annualized = funding_rate * 3 * 365 * 100
                
                spot_inst_id = swap_inst_id.replace('-SWAP', '')
                
                funding_opportunities.append({
                    'swap': swap_inst_id,
                    'spot': spot_inst_id,
                    'rate': funding_rate,
                    'rate_pct': funding_rate * 100,
                    'annualized': annualized,
                    'next_time': next_funding_time,
                })
    
    # Sort by funding rate (descending)
    funding_opportunities.sort(key=lambda x: x['rate'], reverse=True)
    
    print(f"\nTop Funding Rate Opportunities:")
    print("-" * 70)
    print(f"{'Pair':<20} {'Rate (per 8h)':<15} {'Annualized':<15} {'Recommendation'}")
    print("-" * 70)
    
    for opp in funding_opportunities:
        rec = ""
        if opp['rate'] >= 0.0001:  # >= 0.01% per 8h
            rec = "✅ High - Good opportunity"
        elif opp['rate'] >= 0.00005:  # >= 0.005% per 8h
            rec = "⚠️  Medium - Consider"
        elif opp['rate'] > 0:
            rec = "ℹ️  Low - Monitor"
        else:
            rec = "❌ Negative - Not suitable"
        
        print(f"{opp['swap']:<20} {opp['rate_pct']:>8.4f}%{'':<6} {opp['annualized']:>8.2f}%{'':<6} {rec}")
    
    # Recommendations
    print(f"\n【Recommendations】")
    print("-" * 70)
    
    if available_usdt < 100:
        print("❌ Insufficient USDT balance for funding rate arbitrage")
        print(f"   Current: {available_usdt:,.2f} USDT")
        print(f"   Recommended: At least 1,000 USDT for meaningful positions")
    elif available_usdt < 1000:
        print(f"⚠️  Limited capital: {available_usdt:,.2f} USDT")
        print(f"   Can only open small positions (recommend 500-1000 USDT per position)")
        
        if funding_opportunities:
            best = funding_opportunities[0]
            if best['rate'] >= 0.0001:
                print(f"\n✅ Best opportunity: {best['swap']}")
                print(f"   Funding rate: {best['rate_pct']:.4f}% per 8h ({best['annualized']:.2f}% annualized)")
                print(f"   Suggested position size: {min(available_usdt * 0.5, 1000):,.0f} USDT")
                print(f"   Run: python3 run_funding_arbitrage.py")
    else:
        print(f"✅ Sufficient capital: {available_usdt:,.2f} USDT")
        print(f"   Can open multiple positions (recommend 1,000-5,000 USDT per position)")
        
        if funding_opportunities:
            good_opps = [o for o in funding_opportunities if o['rate'] >= 0.0001]
            if good_opps:
                print(f"\n✅ {len(good_opps)} good opportunities found:")
                for opp in good_opps[:3]:  # Top 3
                    print(f"   - {opp['swap']}: {opp['rate_pct']:.4f}% per 8h ({opp['annualized']:.2f}% annualized)")
            
            best = funding_opportunities[0]
            print(f"\n💡 Suggested configuration:")
            print(f"   FUNDING_ARB_SWAP_INST_ID={best['swap']}")
            print(f"   FUNDING_ARB_SPOT_INST_ID={best['spot']}")
            print(f"   FUNDING_ARB_POSITION_SIZE={min(available_usdt * 0.3, 5000):,.0f}")
            print(f"   FUNDING_ARB_MIN_RATE=0.0001  # 0.01% per 8h")
            print(f"\n   Run: python3 run_funding_arbitrage.py")
    
    # Check existing positions
    if swap_positions:
        print(f"\n⚠️  Warning: You have existing swap positions")
        print(f"   Make sure they don't conflict with arbitrage strategy")
    
    if spot_positions:
        print(f"\nℹ️  Note: You have existing spot positions")
        print(f"   They may be used as part of arbitrage if they match swap positions")


def main():
    print('=' * 70)
    print('OKX Account Analysis for Funding Rate Arbitrage')
    print('=' * 70)
    print(f'Environment: BASE_URL={BASE_URL}, SIMULATED={SIMULATED_HEADER}')
    print()
    
    # Check server time
    print("Checking server time...")
    t = get_server_time()
    if t.get('code') == '0':
        server_time = t.get('data', [{}])[0].get('ts', '')
        print(f"Server time: {server_time}")
    else:
        print(f"Warning: Failed to get server time: {t.get('msg', 'Unknown')}")
    print()
    
    # Get account balances
    print("Fetching account balances...")
    balances = get_all_balances()
    if balances.get('code') != '0':
        print(f"Error getting balances: {balances.get('msg', 'Unknown error')}")
        sys.exit(1)
    print("✓ Balances retrieved")
    
    # Get positions
    print("Fetching positions...")
    positions = get_positions()
    if positions.get('code') != '0':
        print(f"Warning: Failed to get positions: {positions.get('msg', 'Unknown error')}")
        positions = {'code': '0', 'data': []}
    print("✓ Positions retrieved")
    print()
    
    # Analyze and provide recommendations
    analyze_account_for_funding_arbitrage(balances, positions)
    
    print("\n" + "=" * 70)
    print("Analysis Complete")
    print("=" * 70)


if __name__ == '__main__':
    main()