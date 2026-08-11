# Automatic Market Sentiment Stock Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every single-stock diagnosis automatically calculate or safely load an auditable A-share market state and apply it to entry risk without blocking protective exits.

**Architecture:** Add a focused market-regime module that separates deterministic state evaluation from data acquisition. A provider loads the latest valid close state, optionally refreshes intraday OpenCLI evidence, persists immutable market evidence/state, and supplies a view to the session-aware diagnosis runtime. The runtime applies the market state before new-entry checks, while holding exits remain higher priority.

**Tech Stack:** Python 3, dataclasses and protocols, SQLAlchemy/MySQL, existing OpenCLI Eastmoney adapter, pytest.

## Global Constraints

- Normal diagnosis must not accept an artificial market upgrade; explicit overrides are test/replay-only.
- Intraday state may maintain or downgrade the previous completed-session state, never upgrade it.
- Missing, stale, mismatched, or invalid core market evidence produces `FREEZE`.
- `FREEZE` blocks new risk but never blocks `REDUCE` or `EXIT` for an existing holding.
- Do not add dashboards, schedulers, push tasks, or automatic order submission.
- Do not use Python HTTP calls to Eastmoney; live collection stays inside the existing OpenCLI browser adapter.
- Do not change current market thresholds, five stock-entry gates, risk budget, or position limits.

---

### Task 1: Define the market-state domain and downgrade rules

**Files:**
- Create: `a-share-short-term-trading/short_term_trading/market_regime.py`
- Modify: `a-share-short-term-trading/short_term_trading/gates.py`
- Test: `a-share-short-term-trading/tests/test_market_regime.py`
- Test: `a-share-short-term-trading/tests/test_gates.py`

**Interfaces:**
- Produces: `MarketStateView`, `MarketStateProvider`, `freeze_market_state()`, and `apply_intraday_downgrade(previous_status, intraday_breadth, strong_sector_count, data_fresh)`.
- Reuses: `evaluate_market(MarketInputs) -> MarketStatus` without changing its existing thresholds.

- [ ] **Step 1: Write failing market-domain tests**

Cover a valid close `ALLOW`, missing evidence `FREEZE`, `ALLOW -> LIMITED`, `ALLOW -> FREEZE`, and proof that `LIMITED` or `FREEZE` never upgrades intraday.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/test_market_regime.py \
  a-share-short-term-trading/tests/test_gates.py
```

Expected: collection fails because `short_term_trading.market_regime` does not exist.

- [ ] **Step 3: Implement the minimal immutable domain types**

`MarketStateView` contains `status`, `trading_date`, aware `as_of`, `expires_at`, `indexes_above_ma20`, `breadth_pct`, `amount_ratio`, `strong_sector_count`, `reasons`, `evidence_refs`, and optional `emotion_label`. `freeze_market_state()` returns a complete `FREEZE` view with the supplied reason.

- [ ] **Step 4: Implement monotonic intraday downgrade**

Rules:

```text
stale/missing core data -> FREEZE
previous FREEZE -> FREEZE
previous LIMITED -> LIMITED
previous ALLOW + breadth < 40 and strong sectors < 2 -> LIMITED
previous ALLOW otherwise -> ALLOW
```

- [ ] **Step 5: Run focused tests and commit**

Expected: all Task 1 tests pass.

```bash
git add a-share-short-term-trading/short_term_trading/market_regime.py \
  a-share-short-term-trading/short_term_trading/gates.py \
  a-share-short-term-trading/tests/test_market_regime.py \
  a-share-short-term-trading/tests/test_gates.py
git commit -m "feat(stt): define automatic market regime"
```

### Task 2: Add immutable market evidence and latest-state persistence

**Files:**
- Modify: `a-share-short-term-trading/short_term_trading/evidence.py`
- Modify: `a-share-short-term-trading/short_term_trading/repositories/evidence.py`
- Modify: `a-share-short-term-trading/short_term_trading/repositories/planning.py`
- Modify: `a-share-short-term-trading/short_term_trading/repositories/__init__.py`
- Test: `a-share-short-term-trading/tests/test_evidence.py`
- Test: `a-share-short-term-trading/tests/test_repositories.py`
- Test: `a-share-short-term-trading/tests/integration/test_mysql_repositories.py`

**Interfaces:**
- Produces: `get_latest_valid_snapshot(None, "market")` support and `PlanningRepository.get_latest_market_state(trading_date)`.
- Consumes: `MarketStateV1` and the existing immutable insert behavior.

- [ ] **Step 1: Write failing repository and market-evidence tests**

Test that market evidence requires `breadth`, `amount_ratio`, `indexes_above_ma20`, `strong_sector_count`, `status`, and `trading_date`; verify code is `None`; verify latest state is selected by `as_of DESC` for one trading date.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run the relevant evidence/repository unit tests. Expected failure: current evidence query requires a stock code and planning repository has no latest-state method.

- [ ] **Step 3: Implement market evidence validation and reads**

Keep the 900-second intraday TTL. Permit `None` code only for market evidence and add a focused repository query using `kind='market' AND code IS NULL`.

- [ ] **Step 4: Implement latest market-state lookup**

Query `stt_market_states` by `trading_date`, `data_status='VALID'`, ordered by `as_of DESC, created_at DESC`, limited to one row, and restore it through `MarketStateV1`.

- [ ] **Step 5: Run unit tests, opt-in MySQL test, and commit**

Use a rollback transaction for integration verification; no test rows may remain.

```bash
git add a-share-short-term-trading/short_term_trading/evidence.py \
  a-share-short-term-trading/short_term_trading/repositories \
  a-share-short-term-trading/tests/test_evidence.py \
  a-share-short-term-trading/tests/test_repositories.py \
  a-share-short-term-trading/tests/integration/test_mysql_repositories.py
git commit -m "feat(stt): persist automatic market states"
```

### Task 3: Build close and intraday market collectors

**Files:**
- Create: `a-share-short-term-trading/short_term_trading/market_capture.py`
- Modify: `stock-ai/scripts/tools/fetch_eastmoney_quotes.py`
- Test: `a-share-short-term-trading/tests/test_market_capture.py`
- Create: `stock-ai/tests/unit/test_fetch_eastmoney_quotes.py`

**Interfaces:**
- Produces: `ClosedMarketPayload`, `IntradayMarketPayload`, `capture_closed_market_state()`, and `capture_intraday_market_state()`.
- Consumes: `fetch_domestic_market_opencli()`, `fetch_hot_industry_board_rows_opencli()`, MySQL completed `stock_daily`, and Task 1 domain rules.

- [ ] **Step 1: Write parser tests from fixed fixtures**

Cover three index histories with at least 20 completed bars, market breadth, same-unit daily amount totals, live breadth, and industry rows. Include wrong index identity, incomplete history, zero denominator, stale time, and malformed units.

- [ ] **Step 2: Run focused tests and confirm failure**

Expected: collector types and functions are missing.

- [ ] **Step 3: Add an index K-line OpenCLI entry point**

Extend the existing browser JSONP K-line mechanism with explicit index market identifiers. It must validate returned identity and date, return rows only, and retain the prohibition on Python-side Eastmoney HTTP.

- [ ] **Step 4: Implement close-state capture**

Calculate three index MA20 relationships, full-market breadth, and current/previous completed-session amount ratio. Record raw market evidence, evaluate with existing thresholds, write an immutable `MarketStateV1`, and return a `MarketStateView`. Any incomplete core field returns and records `FREEZE`.

- [ ] **Step 5: Implement intraday capture and monotonic downgrade**

Use live three-index snapshots, total breadth, and count distinct industry rows with `sector_chg >= 1.0`. Apply Task 1 downgrade rules against the completed-session status; never promote it.

- [ ] **Step 6: Run focused tests and commit**

```bash
git add a-share-short-term-trading/short_term_trading/market_capture.py \
  stock-ai/scripts/tools/fetch_eastmoney_quotes.py \
  a-share-short-term-trading/tests/test_market_capture.py \
  stock-ai/tests/unit/test_fetch_eastmoney_quotes.py
git commit -m "feat(stt): capture auditable market sentiment"
```

### Task 4: Integrate automatic market state into session diagnosis

**Files:**
- Modify: `a-share-short-term-trading/short_term_trading/diagnosis_runtime.py`
- Modify: `a-share-short-term-trading/short_term_trading/session_diagnosis.py`
- Modify: `a-share-short-term-trading/short_term_trading/intraday.py`
- Modify: `a-share-short-term-trading/scripts/diagnose_stock.py`
- Test: `a-share-short-term-trading/tests/test_diagnose_stock_cli.py`
- Test: `a-share-short-term-trading/tests/test_session_diagnosis.py`
- Test: `a-share-short-term-trading/tests/test_intraday.py`

**Interfaces:**
- Consumes: `MarketStateProvider.get_state(context) -> MarketStateView`.
- Produces: `SessionAwareDiagnosis.market` and rendered market environment lines.

- [ ] **Step 1: Write failing runtime tests**

Verify automatic provider invocation after session classification, market `FREEZE` blocking a new entry, intraday downgrade display, and provider failure becoming an explicit `FREEZE` reason.

- [ ] **Step 2: Write the holding-exit precedence regression test**

Construct an existing holding below a frozen plan invalidation price with market `FREEZE`; assert the result is `EXIT`, not `NO_TRADE`.

- [ ] **Step 3: Run focused tests and confirm failure**

Expected: runtime has no provider and current `verify_intraday_plan()` checks market before the holding invalidation price.

- [ ] **Step 4: Move protective exit ahead of entry-only market checks**

Require a fresh quote and valid plan price levels, then evaluate an existing holding's hard invalidation before market and portfolio entry gates. Do not relax any buy condition.

- [ ] **Step 5: Wire the provider into normal CLI runtime**

Remove normal reliance on `--market-status`. If a replay-only override remains, name it `--replay-market-status`, require `--at`, and disallow it from upgrading a calculated state.

- [ ] **Step 6: Render the market summary**

Output status, data time, index/MA20 count, breadth, amount ratio, strong-sector count, reason, and “对本股影响”. Missing data must say why it froze rather than displaying fabricated zeroes.

- [ ] **Step 7: Run focused tests and commit**

```bash
git add a-share-short-term-trading/short_term_trading/diagnosis_runtime.py \
  a-share-short-term-trading/short_term_trading/session_diagnosis.py \
  a-share-short-term-trading/short_term_trading/intraday.py \
  a-share-short-term-trading/scripts/diagnose_stock.py \
  a-share-short-term-trading/tests/test_diagnose_stock_cli.py \
  a-share-short-term-trading/tests/test_session_diagnosis.py \
  a-share-short-term-trading/tests/test_intraday.py
git commit -m "feat(stt): apply market sentiment to stock diagnosis"
```

### Task 5: Document and verify the complete workflow

**Files:**
- Modify: `a-share-short-term-trading/README.md`
- Modify: `stock-ai/investment-agent/短线交易投顾系统设计书.md`
- Test: `a-share-short-term-trading/tests/integration/test_mysql_repositories.py`

**Interfaces:**
- Documents: automatic market acquisition, safe `FREEZE`, no schedule, and holding-exit precedence.

- [ ] **Step 1: Update operator documentation**

Document that normal `diagnose_stock.py --code CODE` automatically loads or captures market state, and that missing market evidence blocks buying but not protective selling.

- [ ] **Step 2: Run the full local regression suite**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests \
  stock-ai/tests/unit/test_jywg_portfolio_sync.py
```

Expected: zero failures.

- [ ] **Step 3: Run the opt-in MySQL integration suite**

```bash
STT_MYSQL_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/integration
```

Expected: zero failures and no persistent test records.

- [ ] **Step 4: Run a live shadow diagnosis**

```bash
PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/python a-share-short-term-trading/scripts/diagnose_stock.py \
  --code 603011 --is-holding --output json
```

Expected: output includes an automatic market state and evidence time. Missing data explicitly yields `FREEZE`; no live buy is actionable.

- [ ] **Step 5: Review scope and commit**

Confirm `.env`, credentials, holdings, generated distributions, and unrelated WeChat assets are absent from the diff.

```bash
git add a-share-short-term-trading/README.md \
  stock-ai/investment-agent/短线交易投顾系统设计书.md
git commit -m "docs(stt): explain automatic market sentiment gate"
```
