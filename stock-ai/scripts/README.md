# scripts 目录

脚本按职责分子目录。根目录仅保留 `_bootstrap.py` 与少量**兼容入口**（如 `sync_tushare_daily_to_mysql.py`）。

完整能力地图见 **[docs/CAPABILITIES.md](../docs/CAPABILITIES.md)**。

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

| 脚本 | 说明 |
|------|------|
| `monitor/monitor_holdings_alerts.py` | 持仓 + 选股池条件监控 → 微信（launchd 每 5 分钟） |
| `../push_holdings_monitor.sh` | launchd 入口 |

## tools

| 脚本 | 说明 |
|------|------|
| `tools/fetch_eastmoney_macro_news.py` | Playwright 抓取东财 7×24 宏观财经快讯 |
| `tools/deepseek_client.py` | LLM 统一封装（DeepSeek API 或 `LLM_BACKEND=cursor` → `agent --model auto`） |
| `tools/cursor_agent_client.py` | Cursor CLI 非交互调用（战报/SOP/MCP 共用） |
| `tools/ensure_daily_bars.py` | 检测 MySQL 日线是否落后，17:00 后期望日缺失则 Tushare 补同步 |
| `tools/holdings_context.py` | 持仓执行卡 + trading-strategies 决策上下文 |
| `tools/wechat_format.py` | 战报 AI 解读 / SOP 摘要微信排版 |
| `tools/decision_context.py` | 决策上下文注入（执行卡 + 策略） |
| `tools/position_sizing.py` | 换仓 / 试探仓执行表 |
| `tools/sop_watch_parse.py` | SOP 终审标签解析（DECISION 优先） |
| `tools/daily_briefing_report.py` | 每日战报（数据抓取 + DeepSeek 解读） |
| `tools/patch_qclaw_daily_briefing_jobs.py` | 同步 QClaw daily_briefing 定时任务 |
| `tools/wechat_acp_push_text.py` | 微信文本推送（wechat-acp） |
