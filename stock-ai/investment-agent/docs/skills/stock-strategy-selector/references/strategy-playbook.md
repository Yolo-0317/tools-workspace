# Strategy playbook

## 投顾门控（所有策略共用）

Before any screening command:

1. Read `investment-agent/投顾主策略.md` for current phase (0/1/2)
2. After CSV/DB output, actions are capped by `stock_ai/advisor_selection.py`
3. Phase 0: Top5 = intel only; skip SOP; no selection `alert_rules`; no「候选新开仓」in reports
4. Parallel tracks (`ma5`, `five_factor`, `watch`) also advisor-capped on persist (`selection_strategy_bridge.py`)

| Phase | combined Top5 | aux pools (ma5/五因子/watch) | Monitor selection rules |
|-------|---------------|------------------------------|-------------------------|
| 0 | 继续观察 | 情报标注 | 关闭 |
| 1 | 小仓试探 | 同左 + 可监控 | 启用 |
| 2 | 进攻试探 | 同左 | 启用 |

## Choose the right workflow

### 1) Broad daily stock picking

If the user says:

- 今天帮我选股
- 给我一份股票池
- 做个综合策略筛选

Prefer:

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai/core_v2
uv run python stock_selection_combined.py
```

This is the best default because it merges multiple patterns and produces a ranked CSV with tags, score, and suggested action.

Typical output:

- `output/stock_selection_combined_YYYYMMDD.csv`

After all technical lanes for the day have landed, run the dual-pool merge before publishing Top5:

```bash
cd /Users/huan.yu/dev/tools-workspace/stock-ai
uv run python -m scripts.analysis.merge_dual_pool_selection --top 5
```

This adds bounded major-news context to technical candidates and persists a separate
`news_event_watch` lane. News-only stocks remain observation items and never acquire
buy eligibility without a technical signal. Use `--no-db` for a read-only dry run or
`--date YYYYMMDD` for a specific selection date.

Dual-pool output:

- `output/stock_selection_dual_pool_YYYYMMDD.csv`
- MySQL strategy `dual_pool` for enriched technical rows
- MySQL strategy `news_event_watch` for non-actionable event-only rows

Useful columns from the combined strategy output:

- `代码`
- `策略标签`
- `总分`
- `建议动作`
- `成交额(万)`

Hard daily runbook:

- **Check advisor phase** in `投顾主策略.md` first
- Check `SELECT MAX(trade_date) FROM stock_daily` first.
- Sync daily bars only when requested target date is missing.
- Run capital-flow sync when available (allow partial Eastmoney page failures if enough rows land).
- If import path issues appear, rerun from `/Users/yolo/dev/yolo/tools-workspace/stock-ai/core_v2`.
- After first-pass CSV, Eastmoney second pass = **context only**; final advice must respect advisor phase.
- Final advice: 投顾五段 + interpreted shortlist, not raw CSV dump.

### 2) Momentum / breakout watchlist

If the user wants stronger trend continuation candidates, use:

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/stock_selection.py
```

This focuses on:

- volume-price expansion
- bullish MA stack
- avoiding excessive recent run-up

Typical output:

- `output/stock_selection_YYYYMMDD.csv`

### 3) Lower-risk pullback entries

If the user wants “沿 MA5 低吸”, “回踩买点”, or a cleaner entry setup, use:

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/stock_selection_ma5.py
```

This focuses on:

- touching or hovering near MA5
- positive candle / rebound behavior
- recent strength without being too extended

Typical output:

- `output/stock_selection_ma5_YYYYMMDD.csv`

### 4) AI review after screening

### 4a) Manual strong-sector rotation detector

For “强势板块轮动、板块启动、行业方向机会、为什么选股没选出板块龙头”, run:

```bash
cd /Users/huan.yu/dev/tools-workspace/stock-ai
.venv/bin/python -m scripts.analysis.detect_sector_rotation \
  --edition auto --top-sectors 6 --stocks-per-sector 10 --no-db
```

The detector is independent from Top5. It merges detailed industries into checked-in industry chains, shows at most three strongest, two strengthening, and one pullback direction, and keeps at most ten observation stocks per direction. Up to three names receive conditional plans: one leader, one catch-up, and one pullback. Missing sector ranking fails the run; incomplete constituent or price data remains observation-only. It does not schedule, push, create monitoring rules, or place orders. Remove `--no-db` only after MySQL migration `018_sector_rotation.sql` is applied.

If the user wants commentary such as “帮我看看前 5 只哪个更值得关注”, use AI review after results exist in MySQL or CSV:

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/analysis/ai_review_combined_top5.py --top 5
```

Output:

- `output/<csv_stem>_ai_review.md`

Require:

- `DEEPSEEK_API_KEY`

### 5) Holdings-aware next-day action plan

If the user wants “明天怎么操作”, “结合我持仓给建议”, or “复核后给次日计划”, combine four inputs:

1. Latest screening CSV
2. AI review markdown if available
3. Current holdings from MySQL (`portfolio_positions`) or `load_holdings_card()` after card sync
4. Browser-based Eastmoney/news checks for the most relevant names

Recommended sequence:

```bash
# 1. update daily data if needed
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
./run_sync_daily.sh

# 2. run a broad screen
uv run python scripts/stock_selection_combined.py

# 3. optional AI review of the top candidates
uv run python scripts/analysis/ai_review_combined_top5.py --top 5
```

Then compare the fresh candidates against the holdings list, and use browser-based Eastmoney pages to pull quick fundamentals/news context for:

- top 3-5 fresh candidates
- held names with the largest losses or biggest position weight
- ETFs whose theme strength may matter the next day

Useful user-facing sections:

- `继续持有观察`
- `反弹减仓/止损观察`
- `可考虑低吸或新开仓`
- `明日不动`

When holdings cost is known, mention it explicitly:

- whether current setup is above or below cost
- whether the stock reappears in the latest strategy output
- whether it is weaker than fresh candidates
- whether recent news/fundamental context improves or weakens conviction

If the user has stated a portfolio size, use it for sizing language. Current known portfolio size: about 5w RMB.

Keep this practical. The goal is not a long essay; it is a next-day checklist.

### 6) Selection performance check (optional)

If the user asks to validate recent screening results:

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python -m scripts.tools.verify_selection_performance
```

## Compare strategies

When comparing outputs, focus on:

- overlap in selected codes
- candidate count
- ranking logic
- signal style

Plain-language summary:

- `stock_selection.py`: more breakout/chasing style
- `stock_selection_ma5.py`: more pullback/entry-timing style
- `stock_selection_combined.py`: best default watchlist, broader pattern coverage

## Interpret outputs

### Combined strategy score bands

From the script logic:

- `>= 80`: `强势关注`
- `>= 65`: `观察买入`
- `>= 50`: `继续观察`
- otherwise: `谨慎回避`

If a stock only hits the ambush pattern and the score is adequate, it may be labeled:

- `小仓埋伏`

### Good user-facing framing

Prefer phrasing like:

- 今天综合策略筛出 X 只，前几名更适合加入观察池
- 这不是直接买入指令，更像盘后候选名单
- 如果数据还没同步到最新交易日，结果可能滞后

## Useful diagnosis commands

### Why wasn’t a stock selected?

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/check_why_not_selected.py
```

### Single-stock analysis

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/analyze_stock.py
```

### Holdings review

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/analysis/analyze_holdings_v2.py
```

## Safety / quality bar

- Never present results as guaranteed returns.
- Mention data freshness if sync status is unknown.
- If the user asks for direct buy/sell instructions, frame them as candidate, setup, risk, and stop-loss considerations instead of certainty.
- Prefer concise bullets over giant tables in chat.
