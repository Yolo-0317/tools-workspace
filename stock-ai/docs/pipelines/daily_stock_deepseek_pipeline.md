---
name: daily-stock-deepseek-pipeline
description: Syncs A-share daily bars to MySQL via Tushare only, runs stock-ai strategy screening, then sends the top-ranked tickers to DeepSeek for review. Use when the user asks for daily 日线更新、策略选股流水线、选股前几名 DeepSeek 分析、或盘后自动化选股+AI解读。
---

# 日线更新 → 策略选股 → DeepSeek 前几名分析

工作目录：仓库根目录 `/Users/yolo/dev/yolo/tools-workspace/stock-ai`。本流程为决策辅助，不构成投资建议。

**与本目录关系**：五因子逻辑与评分细则见同目录 [strategy.md](strategy.md)。**日线入库仅使用 Tushare**（见下节）。若需在分析阶段用浏览器补充东方财富资讯（非行情入库），见 [agent_browser_navigate_eastmoney_sop.md](agent_browser_navigate_eastmoney_sop.md)。

---

## 环境前置

| 变量 | 用途 |
|------|------|
| `MYSQL_URL` | `stock_daily` 及依赖库的选股脚本 |
| `DEEPSEEK_API_KEY` | 所有 DeepSeek 调用 |
| Tushare token | 日线同步必需（见项目 `docs/`、`.env`） |

命令均在项目根执行：`cd /Users/yolo/dev/yolo/tools-workspace/stock-ai`，优先 `uv run python ...`。

---

## 1. 每日更新日线数据（仅 Tushare）

**顺序**：先保证 MySQL 中目标交易日已有完整日线，再跑选股。

| 脚本 | 作用 |
|------|------|
| `scripts/sync_tushare_daily_to_mysql.py` | Tushare 日线入库（唯一入库入口） |

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/sync_tushare_daily_to_mysql.py
```

若目标日数据已在库中可跳过；不确定则跑一遍增量同步。

**重复执行同步**：若对应日期已在 `stock_daily` 中，当前脚本可能按行 `INSERT` 失败并刷屏「Duplicate entry」，汇总为**入库 0 条**，属预期；数据仍可用，可直接进行选股。后续可在脚本侧改为 `INSERT ... ON DUPLICATE KEY UPDATE` 以消除噪音。

---

## 2. 策略选股（择一）

输出默认在 `output/`。

| 场景 | 命令 | 典型输出 |
|------|------|----------|
| 筑底突破（scripts） | `uv run python scripts/stock_selection_bottom_breakout.py` | `output/stock_selection_bottom_breakout_YYYYMMDD.csv` |
| **五因子（core_v3，推荐与本目录文档配套）** | `uv run python core_v3/stock_selection_five_factor_mysql.py`（可选参数：`[日期] [最低总分]`） | `output/stock_selection_five_factor_YYYYMMDD.csv`、`technical_candidates_five_factor_*.csv` |

若仓库中存在综合选股脚本（例如 `core_v2/stock_selection_combined.py`），会生成 `output/stock_selection_combined_YYYYMMDD.csv`，可与下节 `run_deepseek_recommendations.py` 直接衔接。

确认 CSV 非空，并记下路径与交易日期。

---

## 3. 将选股前几名交给 DeepSeek

均需 `DEEPSEEK_API_KEY`。按「已有 CSV」选型。

### A. 最新综合选股 CSV + 逐股 `deepseek_trade_signal`（默认 Top 5）

自动选 `output/stock_selection_combined_*.csv` 中**修改时间最新**的一份，对前 5 只调用 DeepSeek，输出 `output/deepseek_analysis_日期.md`。

```bash
uv run python scripts/run_deepseek_recommendations.py
```

### B. 任意选股 CSV + 合并一篇 DeepSeek 报告（可调 Top N）

适合带 `代码` 列的任意结果（如 MA5、突破、五因子导出副本）。默认 Top 5，`--top` 可调。

```bash
uv run python scripts/ai_review_top5.py output/stock_selection_ma5_20260108.csv --top 5
```

报告：与 CSV 同目录，`{csv 主名}_ai_review.md`。

### C. Top5 并发东财 SOP + DeepSeek 投资决策（推荐盘后深度分析）

对综合选股 Top5 **并发**执行：Playwright 东财 8 维度采集 → MySQL 技术面补全 → DeepSeek 逐股终审 → 汇总微信摘要。

```bash
# 单独跑（默认取最新 stock_selection_combined_*.csv）
uv run python -m scripts.analysis.sop_review_top5_concurrent --top 5

# 选股 + SOP 一步完成
uv run python -m scripts.selection.daily_selection_report --with-sop --sop-only

# 定时任务：在 run_selection_daily.sh 前设置
ENABLE_SOP_TOP5=1 ./run_selection_daily.sh
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--top` | 5 | 分析前几名 |
| `--sop-workers` | 3 | Playwright 并发（每只约 50s） |
| `--deepseek-workers` | 3 | DeepSeek API 并发 |

输出：
- `output/sop_preliminary/YYYYMMDD/{code}_初步报告_SOP版.md`
- `output/stock_selection_combined_YYYYMMDD_sop_review.md`

耗时约 **2~4 分钟**（Top5、workers=3）。

### D. 五因子专用：九维逐股 DeepSeek（与 core_v3 默认闭环）

读取最新 `output/stock_selection_five_factor_*.csv`（也可用 `--csv 路径` 指定），对**前 N 只**逐股调用 DeepSeek。**默认 `--top 5`**（与脚本一致）；试跑省 API 可改为 `--top 2` 等。更多参数：`uv run python core_v3/deepseek_analyze_five_factor.py --help`。

**日常默认（前 5 只）：**

```bash
uv run python core_v3/deepseek_analyze_five_factor.py
```

**试跑 / 控费（示例：只分析前 2 只）：**

```bash
uv run python core_v3/deepseek_analyze_five_factor.py --top 2
```

输出：`output/deepseek_v3_five_factor_review_*.md` 与同名 `.json`。

### E. 其它全维度 / 持仓整合

按需使用 `scripts/run_deepseek_final_analysis.py`、`scripts/analyze_holdings_v2.py` 等（非每日最小路径）。

---

## 推荐每日顺序（五因子闭环）

逻辑顺序：

```text
Tushare 同步日线 → 五因子选股 → DeepSeek 逐股分析 → 汇报策略名、目标日、候选数、报告路径与简要风险
```

对应命令（在项目根**逐行执行**即可，无需再记聊天里的补充说明）：

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/sync_tushare_daily_to_mysql.py
uv run python core_v3/stock_selection_five_factor_mysql.py
uv run python core_v3/deepseek_analyze_five_factor.py
```

若未跑五因子而用了综合/突破等 CSV，DeepSeek 改用上文 **A 或 B**，不要照抄第三条。

若当日已在库中、无需同步，可跳过第一条。

---

## 定时任务（可选）

交易日盘后同步 Tushare 日线示例：

```bash
0 18 * * 1-5 cd /Users/yolo/dev/yolo/tools-workspace/stock-ai && uv run python scripts/sync_tushare_daily_to_mysql.py >> logs/sync.log 2>&1
```

选股与 DeepSeek 可写成 `scripts/` 下 shell 再挂一条 cron，或手动在收盘后执行。

---

## 操作约定

- 勿把原始 CSV 当最终结论；结合 DeepSeek 与 [strategy.md](strategy.md) 中的因子含义做「观察 / 风险」表述。
- 用户未要求时不要改策略阈值与过滤参数。
- 需要东财页面资讯补全（非替换 Tushare 日线）时，在交付最终文字前完成抓取（见 [agent_browser_navigate_eastmoney_sop.md](agent_browser_navigate_eastmoney_sop.md) 与 `scripts/ai_review_top5.py` 说明）。
