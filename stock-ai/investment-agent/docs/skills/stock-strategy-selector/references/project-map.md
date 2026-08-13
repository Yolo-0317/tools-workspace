# Project map

## Location

- Project root: `/Users/yolo/dev/yolo/tools-workspace/stock-ai`
- Main dependency manager: `uv`
- Main runtime: Python scripts, MySQL-backed daily data, optional DeepSeek API

## Key prerequisites

### Required for most screening tasks

- `MYSQL_URL`
- Existing `stock_daily` table populated with daily bars

### Optional

- `DEEPSEEK_API_KEY` for AI review and some AI-assisted workflows
- `.env` in the project root; many scripts call `load_dotenv()` and can read local env values

## Main folders

- `scripts/`: operational entry points
- `docs/`: human-written strategy and setup guides
- `sql/`: table DDL
- `output/`: generated CSV and markdown reports
- `logs/`: runtime logs

## High-value scripts

### Data sync / ingestion

- `scripts/sync/sync_tushare_daily_to_mysql.py`
- `scripts/tools/ensure_daily_bars.py`
- `scripts/tools/fetch_eastmoney_quotes.py` — OpenCLI quotes / objective page data / indices

### Screening

- `core_v2/stock_selection_combined.py` — multi-pattern combined ranking
- `scripts/selection/stock_selection.py` — volume-price breakout
- `scripts/selection/stock_selection_ma5.py` — MA5 pullback
- `scripts/selection/stock_selection_bottom_breakout.py` — bottom breakout variant

### Review / analysis

- `scripts/analysis/ai_review_combined_top5.py`
- `scripts/analysis/sop_review_top5_concurrent.py` — legacy human-audit entry; forbidden to AI
- `scripts/analysis/analyze_holdings_v2.py`
- `scripts/tools/check_why_not_selected.py`
- `scripts/tools/debug_signal.py`

### Verification (optional)

- `scripts/tools/verify_selection_performance.py`

## Common command pattern

```bash
cd /Users/yolo/dev/yolo/tools-workspace/stock-ai
uv run python scripts/<script>.py [args]
```

## Output conventions

### Screening outputs

Usually land under `output/` with names like:

- `stock_selection_YYYYMMDD.csv`
- `stock_selection_ma5_YYYYMMDD.csv`
- `stock_selection_combined_YYYYMMDD.csv`
- `stock_selection_bottom_breakout_YYYYMMDD.csv`

### AI review outputs

Usually:

- `<csv_stem>_ai_review.md`

## Reading results fast

If you only need a quick user summary:

1. Find the newest relevant file in `output/`
2. Read the header and top rows
3. Report candidate count, top names/codes, and ranking features

## Known limits

- Many docs are in Chinese and opinionated; keep summaries concise.
- Some scripts assume local env and MySQL are already working.
- AI review can be slow and API-dependent.
- This project is oriented to Chinese A-shares and local workflows, not global equities.
