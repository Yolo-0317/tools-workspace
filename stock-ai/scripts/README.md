# scripts 目录

脚本按职责分子目录。根目录仅保留 `_bootstrap.py` 与少量**兼容入口**（如 `sync_tushare_daily_to_mysql.py`）。

## sync — 数据入库

| 脚本 | 说明 |
|------|------|
| `sync/sync_tushare_daily_to_mysql.py` | Tushare 日线 → MySQL（主入口） |
| `sync/ingest_eastmoney_daily_to_mysql.py` | 东财历史日线补齐 |
| `sync/poll_eastmoney_intraday_to_mysql.py` | 盘中分钟更新 |
| `sync/poll_eastmoney_intraday_snapshot_to_mysql.py` | 盘中快照 |

## selection — 选股

| 脚本 | 说明 |
|------|------|
| `selection/stock_selection.py` | 基础选股 |
| `selection/stock_selection_ma5.py` | MA5 策略 |
| `selection/stock_selection_bottom_breakout.py` | 底部突破 |
| `selection/select_long_term_core.py` | 长期核心标的筛选 |

## analysis — 分析与 DeepSeek

`analysis/analyze_holdings.py`、`run_*_analysis.py`、`run_deepseek_*.py` 等。

## monitor — 监控

`monitor/monitor_stocks_v2.py`、`monitor/monitor_intraday_signals.py`

## backtest / tools / archive

回测脚本、校验工具、已归档的一次性脚本。
