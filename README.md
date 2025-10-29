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