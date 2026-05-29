---
name: stock-strategy-selector
description: A股综合分析工作台 - 每日行情数据同步到MySQL、选股筛选、策略对比、AI审查、持仓次日计划、回测验证、单股诊断。支持 Tushare 和东方财富数据源。
---

# Stock Strategy Selector

Use the local project at `/Users/yolo/dev/yolo/tools-workspace/stock-ai` as the execution backend.

This is the default and unified entrypoint for daily stock-analysis tasks.

## Quick workflow

1. Confirm the task type: data update, daily screening, strategy comparison, AI review, holdings-aware next-day plan, backtest, or single-stock diagnosis.
2. Read `references/project-map.md` once if you need the project layout or prerequisites.
3. Read `references/strategy-playbook.md` when you need strategy selection, command recipes, or result interpretation.
4. If the task depends on the user's current positions, load `holdings/current.csv` from the workspace.
5. Prefer the wrapper script `scripts/run_stock_ai.sh` for common tasks.
6. Report results in plain language, with the exact output file path when a script generates artifacts.

## Operating rules

- Treat this as decision support, not investment advice.
- Prefer fewer, larger writes: run one strategy command, then summarize the output, instead of spamming many small commands.
- Check for required env before long runs:
  - `MYSQL_URL` for any database-backed workflow
  - `DEEPSEEK_API_KEY` only when using AI review features
- Use `uv run python ...` inside the project root when not using the wrapper.
- If a command may take time, say so briefly and run it.
- Do not edit strategy thresholds unless the user asks.
- Do not restart unrelated services; this project is just local scripts plus MySQL/API dependencies.

## 每日行情数据更新（Data Sync）

**这是每日分析的前置步骤**：必须先更新数据，才能进行选股和分析。

### 数据同步脚本

| 脚本 | 功能 | 数据源 |
|------|------|--------|
| `scripts/sync_tushare_daily_to_mysql.py` | 同步日线数据到 MySQL | Tushare |
| `scripts/ingest_eastmoney_daily_to_mysql.py` | 东方财富日线数据入库 | 东方财富 |
| `scripts/poll_eastmoney_intraday_to_mysql.py` | 日内数据实时入库 | 东方财富 |
| `scripts/poll_eastmoney_intraday_snapshot_to_mysql.py` | 日内快照入库 | 东方财富 |

### 使用方式

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai

# 同步 Tushare 日线数据
uv run python scripts/sync_tushare_daily_to_mysql.py

# 同步东方财富日线数据
uv run python scripts/ingest_eastmoney_daily_to_mysql.py

# 实时日内数据（盘中使用）
uv run python scripts/poll_eastmoney_intraday_to_mysql.py
```

### 前置条件

- `MYSQL_URL` 环境变量已配置
- MySQL 中已有 `stock_daily` 表结构
- Tushare token 已配置（如使用 Tushare 数据源）

### 自动化建议

可以配置 cron 每日自动更新：

```bash
# 每个交易日 18:00 更新日线数据
0 18 * * 1-5 cd /Users/yolo/dev/yolo/tools-workspace/stock-ai && uv run python scripts/ingest_eastmoney_daily_to_mysql.py >> logs/sync.log 2>&1
```

---

## Default routing

### Daily stock screening (default)

Use this as the first route for daily requests.

Use one of these:

- Breakout / volume-price strategy: `stock_selection.py`
- MA5 pullback strategy: `stock_selection_ma5.py`
- Combined multi-pattern strategy: `stock_selection_combined.py`

Prefer the combined strategy when the user asks broadly for “today’s stock picks”, “综合选股”, or wants a ranked watchlist.

Hard daily rules (merged from `daily-strategy-selection`):

- Confirm target trade date from MySQL `stock_daily` first.
- Sync missing daily data only when target date is not already present.
- Run capital-flow sync when available; do not fail whole run on partial Eastmoney page errors if enough rows land.
- For combined workflow, run from `/Users/yolo/dev/yolo/tools-workspace/stock-ai/core_v2` if import-path issues appear.
- Do a browser-based Eastmoney second pass (names/news/funds/finance/basic info) before final advice.
- Do not present raw CSV directly as final recommendation; output keep/observe/drop style interpretation.

### Strategy comparison

Run two or more strategy scripts and compare:

- overlap in stock codes
- ranking differences
- style differences: breakout vs low-risk pullback vs multi-signal combined

### AI review

Use `ai_review_top5.py` only after a screening CSV already exists and `DEEPSEEK_API_KEY` is available.

During AI review, use browser-based Eastmoney/news enrichment when stronger recommendation context is needed.

Typical enrichment angles:

- latest company announcements or earnings clues
- industry policy and sector catalysts
- recent negative news, investigations, profit warnings, financing pressure, unlocks, or major shareholder actions

Treat enrichment as context, not a replacement for technical screening. Synthesize technical signals + AI review + browser/news context before final advice.

### Holdings-aware next-day plan

After screening or AI review, compare the candidate list with `holdings/current.csv`.

Use this workflow when the user asks for 次日操作建议, 持仓去留, 明天怎么操作, 调仓建议, or a plan that combines fresh picks with current positions.

Output should separate stocks into a few plain-language buckets:

- 持有观察：still hold, watch key levels, no immediate action
- 逢高减仓 / 反弹减仓：weaker names already held, especially if trapped or no longer aligned with strategy
- 候选新开仓：new names from fresh screening not already held
- 不操作：positions with no clear edge

Base the recommendation on:

- whether the stock is already in holdings
- current cost basis and quantity from `holdings/current.csv`
- total portfolio size when known (user provided: about 5w RMB)
- whether it appears in the latest strategy output
- ranking / score / tags from the latest screening CSV
- AI review conclusions if available
- browser-based Eastmoney/news context when available

For sizing suggestions, keep them proportional to the stated portfolio size instead of speaking in abstract terms only.

Do not present this as certainty; frame it as a next-day watchlist and action plan with risk notes.

### Backtesting / retrospective analysis

Use dedicated backtest scripts instead of inventing ad hoc loops:

- `backtest_combined_strategy.py`
- `backtest_bottom_breakout.py`
- `backtest_recent_week.py`
- `verify_selection_performance.py`
- `compare_daily_selection.py`

### Single-stock diagnosis

Use:

- `analyze_stock.py`
- `check_why_not_selected.py`
- `debug_signal.py`

## Result reporting template

When replying with results, usually include:

- strategy used
- target date
- candidate count
- top 3-10 names/codes if available
- notable tags or scores if available
- output artifact path
- one short caveat about data freshness or risk

## Files to read on demand

- For project setup, commands, and dependencies: `references/project-map.md`
- For strategy choice, output files, and interpretation: `references/strategy-playbook.md`
