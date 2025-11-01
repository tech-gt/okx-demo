#!/usr/bin/env python3
"""
示例：对比逐仓模式和全仓模式在监控和风控上的区别

这个文件用于演示概念，不直接运行
"""

# ============================================================================
# 场景：账户有 10,000 USDT，同时运行 3 个资金费率套利头寸
# ============================================================================

# 假设的账户状态
account_balance = 10000.0

# 三个套利头寸
positions = {
    'BTC-USDT-SWAP': {
        'size_usdt': 1000,
        'margin_allocated': 1000,  # 逐仓：独立分配；全仓：共享
    },
    'ETH-USDT-SWAP': {
        'size_usdt': 800,
        'margin_allocated': 800,
    },
    'SOL-USDT-SWAP': {
        'size_usdt': 600,
        'margin_allocated': 600,
    },
}


# ============================================================================
# 示例 1：逐仓模式下的监控和风控
# ============================================================================

def monitor_positions_isolated():
    """
    逐仓模式：每个头寸独立监控
    """
    print("=" * 60)
    print("逐仓模式（isolated）监控示例")
    print("=" * 60)
    
    # 模拟从 OKX API 获取的逐仓持仓数据
    # 在逐仓模式下，每个头寸有独立的保证金和盈亏
    okx_positions_isolated = {
        'BTC-USDT-SWAP': {
            'pos': '-0.02',           # 空头 0.02 BTC
            'avgPx': '50000',
            'margin': '1000',         # ⭐ 此头寸独立保证金
            'upl': '-50',             # ⭐ 未实现盈亏：-50 USDT
            'liqPx': '55000',         # ⭐ 此头寸的独立强平价格
            'leverage': '3',
            'tdMode': 'isolated',     # ⭐ 逐仓模式
        },
        'ETH-USDT-SWAP': {
            'pos': '-0.27',
            'avgPx': '3000',
            'margin': '800',          # ⭐ 独立保证金
            'upl': '+30',             # ⭐ 独立盈亏：+30 USDT
            'liqPx': '3300',
            'leverage': '3',
            'tdMode': 'isolated',
        },
        'SOL-USDT-SWAP': {
            'pos': '-6',
            'avgPx': '100',
            'margin': '600',          # ⭐ 独立保证金
            'upl': '+15',             # ⭐ 独立盈亏：+15 USDT
            'liqPx': '110',
            'leverage': '3',
            'tdMode': 'isolated',
        },
    }
    
    print("\n【头寸级别的监控】")
    print("-" * 60)
    
    # 可以为每个头寸设置不同的止损阈值
    stop_loss_ratios = {
        'BTC-USDT-SWAP': 0.10,  # BTC 最多亏损 10%
        'ETH-USDT-SWAP': 0.15,  # ETH 最多亏损 15%
        'SOL-USDT-SWAP': 0.12,  # SOL 最多亏损 12%
    }
    
    for inst_id, pos_data in okx_positions_isolated.items():
        margin = float(pos_data['margin'])
        upl = float(pos_data['upl'])
        loss_ratio = abs(upl) / margin if upl < 0 else 0
        
        print(f"\n头寸: {inst_id}")
        print(f"  独立保证金: {margin} USDT")
        print(f"  未实现盈亏: {upl} USDT ({upl/margin*100:+.2f}%)")
        print(f"  强平价格: {pos_data['liqPx']}")
        
        # ⭐ 优势1：可以独立判断每个头寸的风险
        max_loss = stop_loss_ratios[inst_id]
        if loss_ratio >= max_loss:
            print(f"  ⚠️  触发止损！亏损比例 {loss_ratio:.2%} >= {max_loss:.2%}")
            print(f"  ✅ 可以只平掉这个头寸，不影响其他头寸")
        else:
            print(f"  ✓ 风险可控，距离止损还有 {(max_loss - loss_ratio)*100:.2f}%")
    
    print("\n【账户总体状态】")
    print("-" * 60)
    total_upl = sum(float(pos['upl']) for pos in okx_positions_isolated.values())
    total_margin_used = sum(float(pos['margin']) for pos in okx_positions_isolated.values())
    free_balance = account_balance - total_margin_used
    
    print(f"账户总余额: {account_balance} USDT")
    print(f"已使用保证金: {total_margin_used} USDT (逐仓模式)")
    print(f"可用余额: {free_balance} USDT")
    print(f"总体未实现盈亏: {total_upl:+.2f} USDT")
    
    # ⭐ 优势2：即使某个头寸亏损，账户其他资金不受影响
    print(f"\n✅ 即使 BTC 头寸亏损 -50 USDT，ETH 和 SOL 头寸仍然盈利")
    print(f"✅ 账户仍有 {free_balance} USDT 可用于其他策略")


# ============================================================================
# 示例 2：全仓模式下的监控和风控
# ============================================================================

def monitor_positions_cross():
    """
    全仓模式：所有头寸共享保证金池
    """
    print("\n" + "=" * 60)
    print("全仓模式（cross）监控示例")
    print("=" * 60)
    
    # 模拟从 OKX API 获取的全仓持仓数据
    # 在全仓模式下，所有头寸共享账户余额
    okx_positions_cross = {
        'BTC-USDT-SWAP': {
            'pos': '-0.02',
            'avgPx': '50000',
            'margin': '0',            # ⚠️ 全仓模式下 margin 为 0（共享账户）
            'upl': '-50',
            'liqPx': '55000',         # ⚠️ 强平价格依赖账户总权益
            'leverage': '3',
            'tdMode': 'cross',
        },
        'ETH-USDT-SWAP': {
            'pos': '-0.27',
            'avgPx': '3000',
            'margin': '0',
            'upl': '+30',
            'liqPx': '3300',
            'leverage': '3',
            'tdMode': 'cross',
        },
        'SOL-USDT-SWAP': {
            'pos': '-6',
            'avgPx': '100',
            'margin': '0',
            'upl': '+15',
            'liqPx': '110',
            'leverage': '3',
            'tdMode': 'cross',
        },
    }
    
    # ⚠️ 全仓模式下，需要查询账户总权益来判断强平
    account_equity = account_balance  # 需要加上所有未实现盈亏
    total_upl = sum(float(pos['upl']) for pos in okx_positions_cross.values())
    account_equity_with_upl = account_balance + total_upl
    
    print("\n【全仓模式的问题】")
    print("-" * 60)
    print(f"账户总权益（含未实现盈亏）: {account_equity_with_upl} USDT")
    print(f"总体未实现盈亏: {total_upl:+.2f} USDT")
    
    print("\n⚠️  问题1：无法独立计算每个头寸的盈亏比例")
    print("   因为所有头寸共享保证金，无法确定单个头寸的止损阈值")
    
    print("\n⚠️  问题2：无法只止损单个头寸")
    print("   如果要止损 BTC 头寸，需要手动计算并平仓，")
    print("   但账户总权益变化会影响所有头寸的强平价格")
    
    print("\n⚠️  问题3：风险传染")
    print("   如果 BTC 头寸亏损严重，账户总权益下降，")
    print("   可能导致 ETH 和 SOL 头寸也被强制平仓")
    
    # 示例：BTC 头寸亏损严重的情况
    print("\n【极端情况示例】")
    print("-" * 60)
    btc_extreme_loss = -500  # BTC 头寸亏损 500 USDT
    extreme_total_upl = btc_extreme_loss + 30 + 15  # BTC -500, ETH +30, SOL +15
    extreme_equity = account_balance + extreme_total_upl
    
    print(f"如果 BTC 头寸亏损 -500 USDT:")
    print(f"  账户总权益: {extreme_equity} USDT")
    print(f"  所有头寸的强平风险都会增加")
    print(f"  ⚠️  ETH 和 SOL 即使盈利，也可能因为账户总权益不足而被强平")


# ============================================================================
# 示例 3：实际的监控代码对比
# ============================================================================

def risk_control_isolated():
    """
    逐仓模式下的风控代码示例
    """
    print("\n" + "=" * 60)
    print("逐仓模式风控代码示例")
    print("=" * 60)
    
    # 从 OKX API 获取持仓
    okx_positions = {
        'BTC-USDT-SWAP': {
            'margin': '1000',
            'upl': '-80',
            'liqPx': '55000',
        }
    }
    
    # ⭐ 逐仓模式的优势：可以直接计算单个头寸的风险
    for inst_id, pos in okx_positions.items():
        margin = float(pos['margin'])
        upl = float(pos['upl'])
        loss_ratio = abs(upl) / margin if upl < 0 else 0
        
        # 每个头寸独立的止损逻辑
        max_loss_ratio = 0.10  # 最多亏 10%
        
        if loss_ratio >= max_loss_ratio:
            print(f"⚠️  {inst_id} 触发止损")
            print(f"   亏损比例: {loss_ratio:.2%}")
            print(f"   可以独立平仓，不影响其他头寸")
            # close_position(inst_id)  # 只平这个头寸


def risk_control_cross():
    """
    全仓模式下的风控代码示例（更复杂）
    """
    print("\n" + "=" * 60)
    print("全仓模式风控代码示例（更复杂）")
    print("=" * 60)
    
    # 全仓模式下，需要获取账户总权益
    account_equity = 10000.0
    total_upl = -50
    
    # ⚠️ 问题：无法独立判断单个头寸的风险
    # 只能基于账户总体权益来判断
    
    equity_after_upl = account_equity + total_upl
    equity_ratio = equity_after_upl / account_balance
    
    print(f"账户总权益比例: {equity_ratio:.2%}")
    print(f"⚠️  无法判断单个头寸的风险，只能整体止损")
    print(f"⚠️  如果要止损某个头寸，需要重新计算所有头寸的强平价格")


if __name__ == '__main__':
    monitor_positions_isolated()
    monitor_positions_cross()
    risk_control_isolated()
    risk_control_cross()

