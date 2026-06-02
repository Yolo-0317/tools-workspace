# 掘金仿真策略（综合选股 + 执行卡盘中规则）

## 两层逻辑

| 层级 | 时机 | 来源 |
|------|------|------|
| **综合选股** | 每交易日 09:35 等 4 个时点 | 复刻 `stock_selection_combined.py` |
| **执行卡规则** | **每 60 秒 K 线收盘** `on_bar` | `持仓执行卡.md` → `rules.json` |

执行卡导出与 stock-ai `holdings_card_parser` **同源**（只读 `持仓执行卡.md`），但仿真策略**独立运行**：

- **P-买 / `buy_triggers`**：按 `rules.json` 条件可新开仓（不看执行卡实盘持仓）。
- **`holdings_rules`（减仓/止损）**：仅当 **仿真户 `get_position()` 该标的 ≥100 股** 时才订阅行情并判规则；无仓标的（如未持有的广州发展）**不会**再刷卖出日志。

## 会触发的动作（示例）

| 规则 | 仿真动作 |
|------|----------|
| 梅花跌破 9.0 | 清仓 `sell_all` |
| 梅花 ≥10.5 / 南网 ≥16 / 广州 7.8–8.3 | 减仓 200 股 |
| 广核跌破 4.30 / 核电跌破 8.60 | 减 500 / 300 股 |
| 宝新能源 ≤5.5 | 买 100 股（仓位≤75%） |
| 单日涨幅>5% | 当日禁止买（`block_buy`） |
| P-买 皖能 9.50–9.65 等 | 条件满足买 100–200 股 |

每条规则 **每个交易日只触发一次**（`fired_ids`）。

## 维护流程

改 `investment-agent/持仓执行卡.md` 后：

```bash
cd emquant-sim
PYTHONPATH=. python3 -m scripts.tools.export_emquant_rules
./scripts/win/deploy_emquant_strategy.sh 5aa6af16-5da8-11f1-996b-001c42c700fc
```

终端 **停止 → 再运行** 策略以加载新 `rules.json`。

## 文件

| 文件 | 作用 |
|------|------|
| `main.py` | 订阅 60s、`on_bar`、定时综合选股调仓 |
| `combined_selection_gm.py` | 综合选股信号/评分 |
| `holdings_rules_gm.py` | 规则判定与下单 |
| `rules.json` | 执行卡导出（部署到策略目录） |

## 注意

- 行情为终端 **60 秒 bar**，不是 tick；比微信监控（东财 OpenCLI）略慢，但属真实盘中触发。
- 仿真 **整手** 下单；规则里股数已按 100 股对齐。
- Mac 微信监控仍可并行；仿真成交仅在掘金仿真户。
