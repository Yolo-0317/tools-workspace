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

- `scripts/sync_tushare_daily_to_mysql.py`
- `scripts/ingest_eastmoney_daily_to_mysql.py`
- `scripts/poll_eastmoney_intraday_to_mysql.py`
- `scripts/poll_eastmoney_intraday_snapshot_to_mysql.py`

### Screening

- `scripts/stock_selection.py` — volume-price breakout
- `scripts/stock_selection_ma5.py` — MA5 pullback
- `scripts/stock_selection_bottom_breakout.py` — bottom breakout variant
- `scripts/stock_selection_combined.py` — multi-pattern combined ranking

### Review / analysis

- `scripts/ai_review_top5.py`
- `scripts/analyze_stock.py`
- `scripts/analyze_holdings.py`
- `scripts/tools/check_why_not_selected.py`
- `scripts/tools/debug_signal.py`

### Verification (optional)

- `scripts/tools/verify_selection_performance.py`
- `scripts/tools/compare_daily_selection.py`

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
