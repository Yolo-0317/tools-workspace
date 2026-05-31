---
name: daily-stock-deepseek-pipeline
description: Syncs A-share daily bars to MySQL via Tushare only, runs stock-ai strategy screening, then sends the top-ranked tickers to DeepSeek for review. Use when the user asks for daily 日线更新、策略选股流水线、选股前几名 DeepSeek 分析、或盘后自动化选股+AI解读。
---

# 日线更新 → 策略选股 → DeepSeek 前几名分析

> **生产自动化**（17:30 选股 + SOP + 战报 + 微信）见 **[CAPABILITIES.md](../CAPABILITIES.md)**。  
> 本文档描述**手动 / 研究**用的盘后流水线。

工作目录：`/Users/yolo/dev/yolo/tools-workspace/stock-ai`。决策辅助，非投资建议。

**相关**：[strategy.md](strategy.md)（五因子）、[agent_browser_navigate_eastmoney_sop.md](agent_browser_navigate_eastmoney_sop.md)（浏览器补资讯）。

---

## 环境前置

| 变量 | 用途 |
|------|------|
| `MYSQL_URL` | `stock_daily` 及选股脚本 |
| `DEEPSEEK_API_KEY` | DeepSeek 调用 |
| `TUSHARE_TOKEN` | Tushare 日线同步 |

命令均在项目根：`cd /Users/yolo/dev/yolo/tools-workspace/stock-ai`，优先 `uv run python ...`。

---

## 1. 日线数据（Tushare → MySQL）

**顺序**：先保证 MySQL 有目标交易日数据，再选股。

| 脚本 | 作用 |
|------|------|
| `scripts/sync/sync_tushare_daily_to_mysql.py` | 主同步入口 |
| `scripts/tools/ensure_daily_bars.py` | 检测落后并 `by_date` 补缺（17:30 自动化已内置） |

```bash
./run_sync_daily.sh
# 或
uv run python -m scripts.tools.ensure_daily_bars --sync-if-stale
uv run python scripts/sync/sync_tushare_daily_to_mysql.py --mode by_date --days 7
```

Tushare 当日收盘数据一般 **17:00 后**较稳定。本机 `host.docker.internal` 会在 sync 内替换为 `127.0.0.1`。

---

## 2. 策略选股（择一）

输出在 `output/`。

| 场景 | 命令 | 典型输出 |
|------|------|----------|
| **综合选股（17:30 默认）** | `uv run python core_v2/stock_selection_combined.py` | `stock_selection_combined_YYYYMMDD.csv` |
| 五因子（core_v3） | `uv run python core_v3/stock_selection_five_factor_mysql.py` | MySQL `strategy=five_factor` + CSV 备份 |
| 筑底突破 | `uv run python scripts/selection/stock_selection_bottom_breakout.py` | `stock_selection_bottom_breakout_*.csv` |
| MA5 回踩 | `uv run python scripts/selection/stock_selection_ma5.py` | `stock_selection_ma5_*.csv` |

确认 CSV 非空并记下交易日期。

---

## 3. DeepSeek 分析（按场景选型）

均需 `DEEPSEEK_API_KEY`。决策上下文见 `scripts/tools/decision_context.py`。

### A. 最新综合选股 + 合并 DeepSeek 报告（Top 5）

```bash
uv run python scripts/analysis/ai_review_combined_top5.py --top 5
```

不传 CSV 时从 MySQL `selection_daily_results` 读最新一批。输出：微信摘要 + `{csv 主名}_ai_review.md`。

### B. 任意 CSV + 合并一篇 DeepSeek 报告

```bash
uv run python scripts/analysis/ai_review_combined_top5.py output/stock_selection_combined_20260528.csv --top 5
```

微信摘要 + `{csv 主名}_ai_review.md`。

### C. Top5 东财 SOP + DeepSeek（推荐深度分析）

**17:30 自动化默认路径**；也可单独跑：

```bash
# 选股 + SOP 一步（与 launchd 17:30 相同，不含战报推送）
./run_selection_daily.sh

# 仅 SOP（已有 CSV）
uv run python -m scripts.analysis.sop_review_top5_concurrent output/stock_selection_combined_YYYYMMDD.csv --top 5

# 跳过 SOP（轻量简评，不推荐）
DISABLE_SOP_TOP5=1 ./run_selection_daily.sh
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--top` | 5 | 分析前几名 |
| `--sop-workers` | 1 | OpenCLI 单会话（已弃用并发） |
| `--deepseek-workers` | 3 | DeepSeek 并发 |

输出：

- `output/sop_preliminary/YYYYMMDD/{code}_初步报告_SOP版.md`
- `output/stock_selection_combined_YYYYMMDD_sop_review.md`
- `output/sop_review_latest.json`（监控元数据）
- `output/daily_selection_ai_latest.txt`（干净微信摘要）

耗时约 **2～4 分钟**（Top5、workers=3）。

### D. 五因子逐股 DeepSeek

```bash
uv run python core_v3/deepseek_analyze_five_factor.py
uv run python core_v3/deepseek_analyze_five_factor.py --top 2   # 控费试跑
```

默认从 MySQL `selection_daily_results`（`strategy=five_factor`）读取；无库数据时回退 `output/stock_selection_five_factor_*.csv`。

输出：`output/deepseek_v3_five_factor_review_*.md` / `.json`。

### E. 持仓全维度整合

```bash
uv run python scripts/analysis/analyze_holdings_v2.py
```

从 MySQL `portfolio_positions` 读持仓；需先 `uv run python -m scripts.tools.sync_portfolio_from_card`。

---

## 4. 推荐手动顺序

### 路径 A：与生产一致的 17:30 能力（含微信）

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
./push_selection_wechat.sh
```

### 路径 B：五因子研究闭环

```bash
uv run python scripts/sync/sync_tushare_daily_to_mysql.py --mode by_date --days 7
uv run python core_v3/stock_selection_five_factor_mysql.py
uv run python core_v3/deepseek_analyze_five_factor.py
```

### 路径 C：综合选股 + SOP（不推微信）

```bash
uv run python -m scripts.tools.ensure_daily_bars --sync-if-stale
./run_selection_daily.sh
```

---

## 5. 定时任务

**当前生产使用 launchd**（非 cron）：

| 任务 | 安装 |
|------|------|
| 17:30 选股 + 战报 | `scripts/install-daily-selection-launchd.sh` |
| 09/12/15/20 战报 | `scripts/install-daily-briefing-launchd.sh` |
| 盘中监控 | `scripts/install-holdings-monitor-launchd.sh` |

详见 [CAPABILITIES.md](../CAPABILITIES.md) §2。

可选：`docker/daily-sync` 工作日 17:00 Tushare 同步。

---

## 6. 操作约定

- 勿把原始 CSV 当最终结论；结合 DeepSeek 与 [strategy.md](strategy.md) 表述为「观察 / 条件」。
- 用户未要求时不要改策略阈值。
- 东财页面资讯补全见 SOP skill，不替代 Tushare 日线入库。

*最后更新：2026-05-30*
