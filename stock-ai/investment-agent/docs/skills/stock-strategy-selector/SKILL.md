---
name: stock-strategy-selector
description: A股投顾带操工作台 — 投顾主策略决策 → 数据/选股/SOP/监控工具 → 看板/微信交付。支持 Tushare 与东财 OpenCLI。
---

# Stock Strategy Selector（投顾带操）

Use the local project at `/Users/yolo/dev/yolo/tools-workspace/stock-ai` as the execution backend.

**所有任务须先对齐投顾阶段**，再调用工具。决策权威：`investment-agent/投顾主策略.md`；执行价位：`持仓执行卡.md`。

## 投顾阶段门控（必读）

| 阶段 | 含义 | Top5 / combined | SOP & AI 简评 | 次日监控 | 新开仓建议 |
|------|------|-----------------|---------------|----------|------------|
| **0** | 止血降仓 | 情报池（继续观察） | **SOP 启用** / AI 简评跳过 | **不写** selection 规则 | **禁止**；仅减仓 |
| **1** | 稳态组合 | 小仓试探 | 启用 | 启用 | ≤1 只试探 |
| **2** | 进攻试探 | 可进攻 | 启用 | 启用 | 每月 ≤2 只 |

- 代码门控：`stock_ai/advisor_selection.py`（读 `投顾主策略.md` 阶段标记）
- Agent 回复：先输出投顾五段（见 `投顾主策略.md` §六），再附执行卡触发价
- 阶段 0 当前重点：降仓 ≤65%、减梅花/广州/锁南网；**不**把 Top5 当必买

## Quick workflow

1. **Read `investment-agent/投顾主策略.md`** — 阶段、本周必做、禁止项
2. **Read `investment-agent/投顾专业技能.md`** — 账户诊断、七段交付、中证协职责映射
3. Confirm task type: data update, screening, AI review, monitor, or diagnosis
3. Read `references/project-map.md` if you need layout or prerequisites
4. Read `references/strategy-playbook.md` for commands and interpretation
5. Load holdings from MySQL (`portfolio_db.load_positions`) or sync card if updated
6. Prefer `scripts/run_stock_ai.sh` for common tasks
7. Report in plain language with artifact paths; **frame as advisor-led plan**, not raw CSV

## Operating rules

- **投顾带操**：工具输出是投顾的输入，不是最终指令；与用户口头冲突时以投顾主策略为准（可反对补梅花、A 档追高）
- Treat as decision support, not licensed investment advice
- Inject decision context for all AI analysis: `inject_decision_context()` / `load_full_decision_context()`
- Required env: `MYSQL_URL`; `DEEPSEEK_API_KEY` only for AI features
- Do not edit strategy thresholds unless the user asks
- Do not restart unrelated services

## 每日行情数据更新（Data Sync）

**这是每日分析的前置步骤**：必须先更新数据，才能进行选股和分析。

### 数据同步脚本

| 脚本 | 功能 | 数据源 |
|------|------|--------|
| `scripts/sync/sync_tushare_daily_to_mysql.py` | 同步日线数据到 MySQL | Tushare |
| `scripts/tools/fetch_eastmoney_quotes.py` | 实时现价、K 线、SOP、战报指数 | OpenCLI（东财页面） |
| `scripts/tools/fetch_eastmoney_macro_news.py` | 宏观财经快讯 | OpenCLI |

### 使用方式

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai

# 同步 Tushare 日线数据
uv run python scripts/sync/sync_tushare_daily_to_mysql.py --mode by_date --days 7

# 检测落后并自动补同步（17:30 自动化已内置）
uv run python -m scripts.tools.ensure_daily_bars --sync-if-stale
```

### 前置条件

- `MYSQL_URL` 环境变量已配置
- MySQL 中已有 `stock_daily` 表结构
- Tushare token 已配置（如使用 Tushare 数据源）

### 自动化建议

可以配置统一调度每日自动更新（见 `scripts/install-stock-ai-scheduler.sh` 与 [docs/SCHEDULING.md](../../../docs/SCHEDULING.md)）。

---

## Default routing

### Daily stock screening (default)

Use this as the first route for daily requests.

Use one of these:

- Breakout / volume-price strategy: `stock_selection.py`
- MA5 pullback strategy: `stock_selection_ma5.py`
- Combined multi-pattern strategy: `stock_selection_combined.py`

Prefer the combined strategy when the user asks broadly for “today’s stock picks”, “综合选股”, or wants a ranked watchlist.

Hard daily rules (merged from `daily-strategy-selection` + **投顾门控**):

- **First**: read `投顾主策略.md` phase; stage 0 = intel pool only, no SOP, no selection watch
- Confirm target trade date from MySQL `stock_daily` first.
- Sync missing daily data only when target date is not already present.
- Run combined workflow from `core_v2/stock_selection_combined.py` if import-path issues appear.
- Results are **advisor-filtered** (`apply_advisor_to_results_row`); do not undo with execution-card B-tier in phase 0.
- After first-pass CSV, Eastmoney second pass is for **context**, not override of advisor phase.
- Do not present raw CSV as final advice; output 投顾五段 + keep/observe/drop interpretation.
- Stage 0 buckets: **无「候选新开仓」**；仅 持有观察 / 反弹减仓 / 情报观察

### Strategy comparison

Run two or more strategy scripts and compare:

- overlap in stock codes
- ranking differences
- style differences: breakout vs low-risk pullback vs multi-signal combined

### AI review

Use `scripts/analysis/ai_review_combined_top5.py` after screening, with `DEEPSEEK_API_KEY`.

**投顾门控**：阶段 0 跳过 AI 简评与次日监控（`ai_selection_review_enabled()` / `selection_watch_sync_enabled()`）。**Top5 东财 SOP 默认关**（`DISABLE_SOP_TOP5=1` / `sop_review_enabled()`）；恢复 SOP 设 `DISABLE_SOP_TOP5=0`。

During AI review, inject `load_full_decision_context()` (投顾主策略 > 执行卡 > 通用策略).

Typical enrichment angles (context only, not override):

- latest company announcements or earnings clues
- industry policy and sector catalysts
- recent negative news, investigations, profit warnings

Treat enrichment as context. Synthesize **advisor phase + technical + AI + news** before final advice.

### Holdings-aware next-day plan

Compare candidates with holdings from MySQL (`portfolio_db.load_holding_codes()`).

Use when user asks for 次日操作建议, 持仓去留, 调仓建议.

Output buckets (**phase-aware**):

| 阶段 | 允许桶 |
|------|--------|
| **0** | 持有观察 · 反弹/逢高减仓 · 情报观察（**无候选新开仓**） |
| **1** | + 小仓试探（最多 1 只，符合目标组合） |
| **2** | + 进攻试探（仍禁追高、禁补梅花） |

Base on:

- `投顾主策略.md` weekly must-do / forbidden
- MySQL `portfolio_positions` + execution card triggers
- latest screening (advisor-capped actions)
- AI/SOP if phase ≥1
- OpenCLI live price for intraday (not Tushare last close as 现价)

Frame as next-day watchlist with risk notes; user executes in **东方财富证券** (East Money brokerage).

### Selection performance check (optional)

If the user asks to compare recent picks vs actual moves:

- `scripts/tools/verify_selection_performance.py`

### Single-stock diagnosis

Use:

- `analyze_stock.py`
- `check_why_not_selected.py`
- `debug_signal.py`

## Result reporting template

When replying with results, **lead with advisor summary**:

```text
【市场一句话】档位 + 主线
【回本进度】现净资产/6万；距目标差额
【本周必做 1～3 条】代码+股数+条件+理由
【本周不做】
【触发价附录】摘自执行卡
```

Then include:

- strategy used + advisor phase
- target date + candidate count
- top names with **advisor-capped 建议动作**
- output artifact path
- caveat on data freshness / 决策支持非投资建议

## Files to read on demand

- For project setup, commands, and dependencies: `references/project-map.md`
- For strategy choice, output files, and interpretation: `references/strategy-playbook.md`
