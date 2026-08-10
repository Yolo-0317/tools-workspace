# OpenCLI Chip Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable Eastmoney CYQ chip snapshot on demand and use its latest completed-trading-day values in the unified stock diagnosis.

**Architecture:** A pure `chip.py` module calculates CYQ metrics from ordered OHLC and turnover rows. The existing stock OpenCLI adapter supplies those rows inside the browser context, `capture.py` validates and persists one legacy evidence snapshot, and `DiagnosisRuntime` refreshes only a missing static-session snapshot before building the EOD plan.

**Tech Stack:** Python 3.11, pytest, OpenCLI browser automation, SQLAlchemy/MySQL, existing `CaptureRecorder` and trading calendar adapters.

## Global Constraints

- Eastmoney access must run in the OpenCLI browser context; do not add Python HTTP access.
- Chip values are deterministic CYQ estimates, not exchange-disclosed investor costs.
- No timers, dashboards, notifications, or broker order submission.
- Never commit `.env`, credentials, browser sessions, holdings, or raw personal data.
- All new production behavior follows red-green-refactor TDD.
- Missing, stale, malformed, or failed evidence must remain `NO_TRADE`.

---

### Task 1: Pure CYQ Calculation

**Files:**
- Create: `a-share-short-term-trading/short_term_trading/chip.py`
- Create: `a-share-short-term-trading/tests/test_chip.py`

**Interfaces:**
- Produces: `ChipKline`, `ChipMetrics`, `calculate_chip_metrics(bars: list[ChipKline]) -> ChipMetrics`.
- `ChipMetrics.to_payload()` returns `source_trade_date`, `cost_90_low`, `cost_90_high`, `average_cost`, `profit_ratio`, `concentration`, `input_bar_count`, and `method`.

- [ ] **Step 1: Write failing calculator tests**

Add deterministic fixtures that assert the output of turnover decay, a one-price limit bar, percentage units, ordered input normalization, and rejection of fewer than 20 valid rows.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests/test_chip.py
```

Expected: collection or assertion failure because `short_term_trading.chip` does not exist.

- [ ] **Step 3: Implement the minimal CYQ calculator**

Use 150 price buckets, daily turnover decay capped to `[0, 1]`, triangular allocation over each bar range, a rectangular allocation for `high == low`, cumulative 5%/50%/95% quantiles, and percentage outputs multiplied by 100.

- [ ] **Step 4: Run focused and nearby tests**

Run the Task 1 test plus `test_diagnosis.py`; both must pass.

- [ ] **Step 5: Commit Task 1**

Commit only `chip.py` and `test_chip.py` with `feat(stt): calculate auditable CYQ chip metrics`.

### Task 2: OpenCLI Discovery and Chip K-lines

**Files:**
- Modify: `stock-ai/scripts/tools/fetch_eastmoney_quotes.py`
- Create: `stock-ai/tests/unit/test_fetch_eastmoney_chip.py`
- Modify: `stock-ai/.env.example`

**Interfaces:**
- Produces: `resolve_opencli_bin() -> str` and `fetch_chip_kline_rows_opencli(code: str, limit: int = 210, ...) -> list[list[str]]`.
- The returned rows preserve Eastmoney fields through index 10, where index 10 is turnover percentage.

- [ ] **Step 1: Write failing discovery and row-preservation tests**

Test explicit `OPENCLI_BIN`, `PATH`, semantically newest executable nvm fallback, missing-install error text, and preservation of the turnover column from browser JSONP output.

- [ ] **Step 2: Run the focused test and verify RED**

Run `stock-ai/tests/unit/test_fetch_eastmoney_chip.py`; expected failure is missing public functions.

- [ ] **Step 3: Implement minimal discovery and browser fetch**

Replace the hard-coded default lookup with explicit environment, `shutil.which`, and injectable nvm-root discovery. Reuse `_open_page`, `_wait_page_ready`, `_eval_js`, `secid`, and browser release behavior. Do not add `requests`, `urllib`, or curl.

- [ ] **Step 4: Update configuration example and verify**

Document `OPENCLI_BIN` as optional because automatic discovery is supported. Run the focused test and existing stock-ai tests that import the adapter.

- [ ] **Step 5: Commit Task 2**

Commit the three Task 2 files with `fix(stock-ai): discover OpenCLI for chip capture`.

### Task 3: Validated Chip Capture and Trading-date Freshness

**Files:**
- Modify: `a-share-short-term-trading/short_term_trading/capture.py`
- Modify: `a-share-short-term-trading/short_term_trading/evidence.py`
- Modify: `a-share-short-term-trading/short_term_trading/diagnosis.py`
- Modify: `a-share-short-term-trading/tests/test_capture.py`
- Modify: `a-share-short-term-trading/tests/test_evidence.py`
- Modify: `a-share-short-term-trading/tests/test_diagnosis.py`

**Interfaces:**
- Produces: `ChipPayload`, `default_chip_fetcher(code: str) -> ChipPayload`, `capture_chip(code, recorder, *, fetcher=..., now=None) -> None`.
- Produces: `is_chip_snapshot_for_trade_date(snapshot, expected_trade_date) -> bool`.
- Extends: `build_eod_trade_plan(..., expected_trade_date: date | None = None)`.

- [ ] **Step 1: Write failing validation, capture, and freshness tests**

Assert that valid calculated fields write one `chip` snapshot and one successful attempt; malformed percentages or missing source date write only `PARSE_ERROR`; source exceptions write `SOURCE_ERROR`; a Friday source remains valid on Monday pre-market when Friday is the expected date; a different source date fails the plan.

- [ ] **Step 2: Run focused tests and verify RED**

Run the three modified test files; expected failures are missing chip APIs and date-aware validation.

- [ ] **Step 3: Implement capture and strict fields**

Convert OpenCLI rows to `ChipKline`, calculate metrics, store all audit fields, validate ranges and minimum bar count, and record source failures without raising. Keep generic TTL behavior for other snapshot kinds.

- [ ] **Step 4: Implement target-trading-date checks**

When `expected_trade_date` is supplied, accept only a `chip` snapshot whose `source_trade_date` equals it; do not reject it merely because 24 wall-clock hours elapsed. Preserve legacy TTL behavior when no expected date is supplied.

- [ ] **Step 5: Run focused and evidence repository tests**

Run all Task 3 tests plus `test_repositories.py`; all must pass.

- [ ] **Step 6: Commit Task 3**

Commit only Task 3 files with `feat(stt): capture trading-date chip snapshots`.

### Task 4: On-demand Unified Diagnosis Integration

**Files:**
- Modify: `a-share-short-term-trading/short_term_trading/diagnosis_runtime.py`
- Modify: `a-share-short-term-trading/scripts/diagnose_stock.py`
- Modify: `a-share-short-term-trading/tests/test_diagnose_stock_cli.py`
- Modify: `a-share-short-term-trading/README.md`

**Interfaces:**
- Extends: `DiagnosisRuntime` with `chip_refresh: Callable[[str], None] | None`.
- Static diagnosis reads a snapshot for `context.diagnosis_trade_date`, calls `chip_refresh` at most once when absent or wrong-date, rereads it, then builds the EOD plan.
- Intraday and midday handlers never call `chip_refresh`.

- [ ] **Step 1: Write failing runtime tests**

Assert one refresh and reread for a missing post-market snapshot, zero refresh for a current snapshot, zero refresh during intraday and midday, and safe `NO_TRADE` after a failed refresh.

- [ ] **Step 2: Run focused tests and verify RED**

Run `test_diagnose_stock_cli.py`; expected failures are missing `chip_refresh` and no static refresh behavior.

- [ ] **Step 3: Implement minimal runtime composition**

Wire `CaptureRecorder` and `capture_chip` in `default_runtime`; keep `--no-intraday-refresh` scoped to real-time quote/fund capture and add `--no-chip-refresh` for explicit offline diagnosis. Pass the target trading date to `build_eod_trade_plan`.

- [ ] **Step 4: Update usage documentation and run local regression**

Document that chip refresh is on demand and estimated. Run all `a-share-short-term-trading/tests` and the JYWG portfolio unit test.

- [ ] **Step 5: Commit Task 4**

Commit the four Task 4 files with `feat(stt): refresh chip evidence on diagnosis`.

### Task 5: MySQL and 603011 Acceptance

**Files:**
- No production files unless a failing acceptance test exposes a scoped defect.

**Interfaces:**
- Consumes the unified CLI and existing household `MYSQL_URL`; writes only a validated 603011 `chip` snapshot and capture audit row.

- [ ] **Step 1: Run full local verification**

Run the complete local suite with bytecode and pytest cache disabled, then compile the modified entry points.

- [ ] **Step 2: Run household MySQL integration tests**

Set `STT_MYSQL_INTEGRATION=1` and run `a-share-short-term-trading/tests/integration`; expect all tests to pass with rollback and no test residue.

- [ ] **Step 3: Run controlled 603011 capture and diagnosis**

Run the unified CLI after market close with JSON output. Verify one valid current-trading-date `chip` snapshot, non-secret evidence reference, generated price-plan fields when all static gates pass, and a non-actionable `WAIT_ENTRY` or explicit rules-based `NO_TRADE` rather than a missing-chip error.

- [ ] **Step 4: Run secret and scope checks**

Confirm the staged diff contains neither `MYSQL_URL` nor `MYSQL_ROOT_PASSWORD`; run `git diff --check`; confirm unrelated WeChat changes are unstaged.

- [ ] **Step 5: Commit any acceptance-only documentation change**

If no file change is needed, do not create an empty commit. Otherwise commit only the scoped documentation with `docs(stt): verify chip diagnosis workflow`.
