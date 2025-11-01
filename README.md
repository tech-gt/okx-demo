# OKX V5 模拟盘交易示例（Python）

本示例基于 OKX 官方 V5 REST API，演示如何在模拟盘（Paper Trading）环境下查询余额并下发一笔现货市价订单。

注意：示例已在 `.env` 中填入你提供的 API Key/Secret/Passphrase，仅用于本地演示。生产环境请务必妥善管理密钥并避免硬编码。

## 环境要求
- Python 3.8+

## 安装依赖
- 在项目根目录执行：
```
python3 -m pip install -r requirements.txt
```

## 配置说明
- `.env` 包含以下变量：
  - `OKX_API_KEY`、`OKX_API_SECRET`、`OKX_API_PASSPHRASE`（已填入你提供的值）
  - `OKX_SIMULATED=1`（启用模拟盘）
  - 如需切换到实盘，请移除或设为 `0`，并确保账户、风险控制与资金安全。

## 运行示例
```
python3 okx_demo.py
```

## 量化系统框架（Python，模拟盘/回测）

目录 `quant/` 提供可扩展架构，支持不同策略与不同产品（先从 SPOT/行情 Tick 开始）：

- 核心模块：`quant/core/`
  - `types.py` 定义 `Tick`/`Order`/`Fill`/`PortfolioState` 等通用数据结构
  - `strategy.py` 策略基类（`on_start/on_tick/on_end`）
  - `datafeed.py` 行情源抽象
  - `broker.py` 交易通道抽象
  - `portfolio.py` 组合持仓与资金变更逻辑
  - `risk.py` 简单风控（单笔名义金额等）
- 适配层：`quant/adapters/`
  - `okx_rest_feed.py` 基于 OKX REST 的简易轮询行情源（模拟盘友好）
  - `okx_ws_feed.py` 基于 OKX WebSocket 的实时行情源（低延迟）
  - `paper_broker.py` 简单模拟撮合，按最新价即时成交（含费率）
  - `okx_broker.py` ⭐ **真实 OKX 交易所连接**（支持模拟盘和实盘）
  - `csv_feed.py` 用于回测的 CSV Tick 源（列：`ts,last[,bid,ask]`）
- 引擎：`quant/engines/`
  - `paper_loop.py` 事件循环（策略 -> 风控 -> 模拟撮合 -> 组合）
- 策略示例：`quant/strategies/sma_cross.py`（SMA 金叉/死叉，按报价币下单）

### 运行模拟盘

有两种方式运行模拟盘：

**方式1：REST 轮询行情（更简单，适合测试）**

```
python3 run_paper.py
```

**方式2：WebSocket 实时行情（低延迟，推荐用于生产）**

```
python3 run_paper_ws.py
```

可选环境变量：
- `OKX_PAPER_INST_IDS`（默认 `BTC-USDT`，多品种逗号分隔）
- `OKX_PAPER_INTERVAL`（仅 REST 模式，默认 `1.0` 秒）
- `OKX_WS_PUBLIC_URL`（仅 WS 模式，默认 `wss://ws.okx.com:8443/ws/v5/public`）
- `PAPER_START_CASH`（默认 `10000`，初始模拟资金）
- `PAPER_USE_REAL_BALANCE`（设置为 `true`/`1`/`yes` 从 OKX API 获取真实余额作为初始资金）
- `PAPER_BALANCE_CURRENCY`（查询余额的币种，默认 `USDT`，需配合 `PAPER_USE_REAL_BALANCE` 使用）
- `PAPER_MAX_NOTIONAL`（单笔上限，默认 `200`）
- `SMA_SHORT`/`SMA_LONG`（默认 `5/20`）
- `SMA_QUOTE_PER_TRADE`（每次下单的报价币金额，默认 `50`）
- `PAPER_DRY_RUN`（设置为 `true`/`1`/`yes` 启用干跑模式，只输出日志不实际下单）
- `OKX_PAPER_TICKS`（运行多少 tick 后停止，默认 `200`）

**重要**：设置 `PAPER_DRY_RUN=true` 可以查看策略逻辑和运行流程，但不会实际下单和修改资金。

**从 OKX 获取初始资金**：
如果你想使用 OKX 账户的真实余额作为模拟盘初始资金，设置 `PAPER_USE_REAL_BALANCE=true` 并配置 `PAPER_BALANCE_CURRENCY=USDT`（或其他币种）。如果 API 查询失败，将回退到 `PAPER_START_CASH` 的默认值。

### 运行真实 OKX 交易（OkxBroker）

使用 `OkxBroker` 可以将策略直接连接到 OKX 交易所（支持模拟盘和实盘）：

```
python3 run_real_trading.py
```

⚠️ **重要安全提示**：
- 默认使用 OKX 模拟盘（`OKX_SIMULATED=1`）
- 切换到实盘需设置 `OKX_SIMULATED=0` 并在提示中输入 'YES' 确认
- 实盘有资金风险，请谨慎操作

环境变量：
- `OKX_SIMULATED`（默认 `1`，模拟盘；设为 `0` 切换到实盘）
- `OKX_REAL_INST_IDS`（默认 `DOGE-USDT`，交易品种）
- `OKX_REAL_TICKS`（默认 `50`，运行多少个 tick）
- `OKX_REAL_DRY_RUN`（默认 `false`，设为 `true` 只查看不实际下单）
- `OKX_REAL_MAX_NOTIONAL`（单笔上限，默认 `200`）
- `OKX_FILL_WAIT`（等待订单成交的超时时间，默认 `10` 秒）
- `SMA_SHORT`/`SMA_LONG`（默认 `5/20`）
- `SMA_QUOTE_PER_TRADE`（每次下单的报价币金额，默认 `50`）

### 运行回测（CSV Tick）

```
python3 run_backtest.py <csv_path> <inst_id>
```

例如：

```
python3 run_backtest.py data/btc_usdt_ticks.csv BTC-USDT
```

环境变量：
- `BT_START_CASH`（默认 `10000`）
- `BT_MAX_NOTIONAL`（默认 `1e9`，基本不限制）
- `BT_SMA_SHORT`/`BT_SMA_LONG`/`BT_QUOTE_PER_TRADE`

### 架构扩展点

- 新策略：实现 `Strategy`，在 `on_tick` 输出 `Order`
- 新产品：扩展 `Instrument`/下单规则，在 `Broker` 侧处理
- 实盘接入：✅ 已完成！`OkxBroker` 已实现，支持 OKX 模拟盘和实盘

运行后脚本会：
- 查询服务器时间（`/api/v5/public/time`）
- 查询账户余额（`/api/v5/account/balance`，默认查询 USDT）
- 下发一笔现货市价买入 `BTC-USDT` 的订单（数量 `0.0001`），交易模式 `cash`

## 重要说明
- 模拟盘通过请求头 `x-simulated-trading: 1` 开启，示例已默认启用。
- 私有 WebSocket 在模拟盘中建议使用域名 `wspap.okx.com`，并在 URL 上附带 `x-simulated-trading=true`（脚本已处理）。
- 若返回 `code != 0`，通常可能为签名错误、时间戳偏差过大、余额不足或参数不合法。
- 模拟盘的资金需要在 OKX 的模拟环境中准备，若余额不足会下单失败。

## 安全建议
- 切勿在公共仓库提交 `.env` 与密钥。
- 生产环境应使用安全的密钥管理方案，并在网络与系统层面做好访问控制与审计。
- 私有 WebSocket（订单）订阅与推送：
```
python3 okx_ws_private_demo.py
```
运行后脚本会：
- 登录私有 WS（使用 `wspap.okx.com` 并附带 `x-simulated-trading=true`）
- 订阅 `orders`（`instType=SPOT`）
- 触发一笔市价买单以产生订单事件，打印订单状态变更（live/partially_filled/filled）

## WebSocket 示例参数
- 公共行情：`okx_ws_demo.py`
  - `OKX_WS_PUBLIC_URL`（默认 `wss://ws.okx.com:8443/ws/v5/public`）
  - `OKX_WS_INST_ID`（默认 `BTC-USDT`）
  - `OKX_WS_DURATION`（默认 `15` 秒）
- 私有频道：`okx_ws_private_demo.py`
  - `OKX_WS_PRIVATE_URL`（默认 `wss://wspap.okx.com:8443/ws/v5/private`）
  - `OKX_WS_INST_ID`（默认 `BTC-USDT`）
  - `OKX_WS_QUOTE_SZ`（默认 `10`，下单花费 10 USDT）
  - `OKX_WS_DURATION`（默认 `25` 秒）