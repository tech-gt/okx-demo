# 资金费率套利策略更新说明

## 更新内容

策略已修改为**自动识别并利用现有现货持仓**，无需重复买入现货。

## 主要改进

### 1. 智能识别现有持仓

策略现在会：
- ✅ 检测账户中已有的现货持仓
- ✅ 如果已有足够的现货，直接使用，不再买入
- ✅ 如果现货不足，只买入差额部分
- ✅ 然后建立对应的合约空头

### 2. 工作流程

#### 场景A：你已有1 BTC现货，需要1 BTC套利
```
检测到：已有 1 BTC 现货
目标：需要 1 BTC 套利
操作：
  ✅ 使用现有 1 BTC（不买入）
  ✅ 做空 1 BTC-USDT-SWAP 合约
结果：节省 70,000+ USDT，立即建立套利头寸
```

#### 场景B：你已有0.5 BTC现货，需要1 BTC套利
```
检测到：已有 0.5 BTC 现货
目标：需要 1 BTC 套利
操作：
  ✅ 使用现有 0.5 BTC
  ✅ 买入 0.5 BTC 现货（补齐差额）
  ✅ 做空 1 BTC-USDT-SWAP 合约
结果：只花费 35,000 USDT，而不是 70,000 USDT
```

#### 场景C：你没有现货，需要1 BTC套利
```
检测到：现货持仓为 0
目标：需要 1 BTC 套利
操作：
  ✅ 买入 1 BTC 现货
  ✅ 做空 1 BTC-USDT-SWAP 合约
结果：标准流程，花费 70,000+ USDT
```

## 日志输出示例

当策略检测到现有持仓时，会输出类似日志：

```
Funding rate 0.3101% >= threshold 0.0100%, opening arbitrage position
Target position: 1.000000
Existing spot: 1.009994, Need to buy: 0.000000
Opening arbitrage: Spot long 1.000000 BTC-USDT (using 1.009994 existing + buying 0.000000), Swap short 1.000000 BTC-USDT-SWAP
Using existing 1.009994 BTC-USDT spot, no need to buy
Shorting 1.000000 BTC-USDT-SWAP swap
```

## 配置建议（针对你的账户）

基于你的账户状态：
- ✅ 已有 1 BTC 现货
- ✅ 已有 1 ETH 现货
- ✅ 可用资金：3,748 USDT

### 推荐配置1：BTC套利（最优）

```bash
FUNDING_ARB_SWAP_INST_ID=BTC-USDT-SWAP
FUNDING_ARB_SPOT_INST_ID=BTC-USDT
FUNDING_ARB_POSITION_SIZE=1  # 只做1个BTC，利用现有持仓
FUNDING_ARB_MIN_RATE=0.0001
```

**优势：**
- 直接使用现有 1 BTC，无需买入
- 只需保证金 ~2,333 USDT（3x杠杆）或 ~7,000 USDT（1x杠杆）
- 你的 3,748 USDT 足够

### 推荐配置2：ETH套利

```bash
FUNDING_ARB_SWAP_INST_ID=ETH-USDT-SWAP
FUNDING_ARB_SPOT_INST_ID=ETH-USDT
FUNDING_ARB_POSITION_SIZE=1  # 只做1个ETH，利用现有持仓
FUNDING_ARB_MIN_RATE=0.0001
```

**优势：**
- 直接使用现有 1 ETH，无需买入
- 只需保证金 ~1,167 USDT（3x杠杆）
- 还有剩余资金可做其他套利

## 注意事项

1. **持仓检测限制**
   - 策略通过 `portfolio.positions` 检测持仓
   - 如果你只是持有币种余额（未交易），可能检测不到
   - 通常已交易的现货持仓会显示在positions中

2. **持仓匹配**
   - 策略会匹配 `spot_inst_id` 对应的持仓
   - 例如：`BTC-USDT` 会匹配 `BTC-USDT` 现货持仓
   - 如果你持有的是其他交易对（如 `BTC-USD`），需要相应配置

3. **头寸管理**
   - 策略会在平仓时同时平掉现货和合约
   - 如果你只想平掉合约空头而保留现货，需要手动操作

## 测试建议

1. **先用小仓位测试**
   ```bash
   FUNDING_ARB_POSITION_SIZE=0.1  # 先测试0.1 BTC
   ```

2. **使用dry run模式**
   ```bash
   PAPER_DRY_RUN=true python3 run_funding_arbitrage.py
   ```

3. **观察日志**
   - 查看是否正确识别现有持仓
   - 确认是否只买入差额部分
   - 验证合约空头是否正常建立

## 总结

✅ 策略已支持自动利用现有现货持仓
✅ 节省资金，提高资金利用率
✅ 特别适合已有BTC/ETH现货的用户

现在可以直接运行策略，它会自动识别你的现有持仓并优化操作！

