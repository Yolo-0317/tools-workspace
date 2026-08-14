# Buy-Point PIT Replay and Frozen Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a complete, reproducible point-in-time opportunity ledger from MySQL and the approved alternative reference sources, then freeze calibration on train/validation data and evaluate the untouched test segment once.

**Architecture:** Add a pure historical replay layer beside the existing buy-point selector. A thin CLI adapter bulk-loads daily bars and PIT references, replays each signal date without the calibration gate, simulates the following trigger/holding path, and writes an auditable observation bundle plus an integrity manifest. The existing validation CLI then freezes only train/validation calibrations and uses that frozen profile for test evaluation; missing coverage or unresolved paths fail closed.

**Tech Stack:** Python 3.11+, frozen dataclasses, Decimal arithmetic, SQLAlchemy/MySQL, BaoStock, pytest, JSON artifacts.

## Global Constraints

- Signal dates are 2023-12-26 through 2026-08-04; outcome bars may extend through 2026-08-13.
- At least 630 strictly increasing signal trading dates are required.
- Every decision uses only data with `trade_date <= signal_date` and references effective on that date.
- The two trigger sessions use the next two actual trading dates, not weekday arithmetic.
- Historical sizing uses the fixed stage-1 budget: CNY 500 loss budget, CNY 4,000 ticket limit, CNY 40,000 maximum exposure.
- Same-day target/stop ambiguity remains stop-first.
- Incomplete sector, ST, announcement, market-index, or outcome coverage makes the manifest incomplete and prevents `--point-in-time-complete` promotion.
- Frozen test outcomes cannot influence profile calibration or candidate ranking.
- Generated observations, manifests, profiles, validation artifacts, holdings, and personal data are never committed.
- Eastmoney legacy eight/eleven-dimension AI remains prohibited.
- The workflow is manually triggered and never submits broker orders.

---

### Task 1: Pure Historical Opportunity Replay

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/historical_replay.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/__init__.py`
- Create: `stock-ai/tests/unit/test_buy_point_historical_replay.py`

**Interfaces:**
- Consumes: `BuyPointBar`, `SectorMembership`, `RiskFlag`, `MarketSnapshot`, `SelectionPolicy`, `RiskBudget`, `detect_setups`, existing gates, `build_price_plan`, and `simulate_plan`.
- Produces: `ReplayDayInput`, `HistoricalOpportunity`, `ReplayIntegrity`, `replay_buy_point_history`, and JSON-safe payload helpers.

- [ ] **Step 1: Write failing chronology and outcome tests**

```python
def test_replay_uses_only_signal_date_history_and_actual_next_two_sessions() -> None:
    result = replay_buy_point_history(_fixture_with_holiday_gap())
    opportunity = result.opportunities[0]
    assert opportunity.signal_date == date(2024, 2, 7)
    assert opportunity.plan.valid_through_trade_date == date(2024, 2, 20)
    assert opportunity.trade.outcome is OutcomeLabel.TARGET_2R_FIRST


def test_replay_deduplicates_a_still_active_structure() -> None:
    result = replay_buy_point_history(_same_structure_on_two_signal_days())
    assert len(result.opportunities) == 1
    assert result.integrity.duplicate_structures == 1


def test_incomplete_pit_day_is_retained_in_integrity_but_emits_no_plan() -> None:
    result = replay_buy_point_history(_fixture_with_missing_announcement_coverage())
    assert result.opportunities == ()
    assert result.integrity.complete is False
    assert result.integrity.missing_announcement_dates == (date(2024, 2, 7),)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_historical_replay.py
```

Expected: import failure for `historical_replay`.

- [ ] **Step 3: Implement replay with exact chronology**

For each signal date, slice every code to bars at or before that date, apply base, setup, anti-chase, sector, market, and price-plan gates, and pass `valid_through_trade_date=trading_dates[index + 2]`. Simulate with later bars only. Record every valid plan including `NOT_TRIGGERED` and `PENDING`; do not apply historical calibration during opportunity generation.

- [ ] **Step 4: Add deterministic observation payloads**

Each row must include:

```python
{
    "signal_date": opportunity.signal_date.isoformat(),
    "exit_date": opportunity.resolution_date.isoformat(),
    "code": opportunity.code,
    "structure_id": opportunity.plan.structure_id,
    "setup_type": opportunity.setup_type.value,
    "sector_code": opportunity.sector_code,
    "market_status": opportunity.market_status,
    "sector_resonating": opportunity.sector_resonating,
    "trigger_price": str(opportunity.plan.trigger_price),
    "invalidation_price": str(opportunity.plan.invalidation_price),
    "target_2r": str(opportunity.plan.target_2r),
    "risk_fraction": str(opportunity.plan.risk_distance / opportunity.plan.trigger_price),
    "net_return": str(opportunity.trade.net_return or Decimal("0")),
    "net_pnl": str(opportunity.trade.net_pnl),
    "outcome": opportunity.trade.outcome.value,
    "mfe": None if opportunity.trade.mfe is None else str(opportunity.trade.mfe),
    "mae": None if opportunity.trade.mae is None else str(opportunity.trade.mae),
}
```

- [ ] **Step 5: Run Task 1 tests and commit**

Expected: focused tests pass.

```bash
git add stock-ai/stock_ai/buy_point_selection/historical_replay.py \
  stock-ai/stock_ai/buy_point_selection/__init__.py \
  stock-ai/tests/unit/test_buy_point_historical_replay.py
git commit -m "feat(stock-ai): replay historical buy-point opportunities"
```

---

### Task 2: Bulk PIT Loader and Observation Bundle CLI

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/reference_data.py`
- Create: `stock-ai/scripts/analysis/generate_buy_point_observations.py`
- Modify: `stock-ai/tests/unit/test_buy_point_reference_repository.py`
- Create: `stock-ai/tests/unit/test_generate_buy_point_observations_cli.py`

**Interfaces:**
- Produces: bounded `coverage_between`, a MySQL-backed replay loader, `trading-dates.json`, `outcome-observations.json`, and `replay-integrity.json`.
- Consumes: Task 1 replay API and existing `MYSQL_URL` configuration.

- [ ] **Step 1: Write failing bulk-coverage and CLI tests**

```python
def test_coverage_between_uses_one_bounded_query() -> None:
    result = repository.coverage_between((date(2024, 1, 2), date(2024, 1, 3)))
    assert result[date(2024, 1, 2)].complete
    assert connection.execute_calls == 1


def test_cli_writes_bundle_only_with_explicit_output_directory(tmp_path) -> None:
    exit_code = main(["--start", "2023-12-26", "--end", "2026-08-04", "--out", str(tmp_path)])
    assert exit_code == 0
    assert json.loads((tmp_path / "replay-integrity.json").read_text())["complete"] is True
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_reference_repository.py \
  stock-ai/tests/unit/test_generate_buy_point_observations_cli.py
```

Expected: missing bulk API and CLI import.

- [ ] **Step 3: Implement bounded reads and fail-closed manifest**

Load the 180-calendar-day lookback, signal range, and seven future sessions using bounded queries. Load PIT memberships, risk flags, and completed sync-run coverage in bulk. The manifest stores date bounds, counts, rule version/hash, source coverage, unresolved plans, rejection counts, and SHA-256 hashes of both JSON data files.

- [ ] **Step 4: Run Task 2 tests and commit**

Expected: focused tests pass and JSON ordering is deterministic.

```bash
git add stock-ai/stock_ai/buy_point_selection/reference_data.py \
  stock-ai/scripts/analysis/generate_buy_point_observations.py \
  stock-ai/tests/unit/test_buy_point_reference_repository.py \
  stock-ai/tests/unit/test_generate_buy_point_observations_cli.py
git commit -m "feat(stock-ai): generate PIT outcome observations"
```

---

### Task 3: Frozen Calibration Profile and Untouched Test Evaluation

**Files:**
- Modify: `stock-ai/scripts/analysis/backtest_buy_point_selection.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/validation.py`
- Modify: `stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py`
- Modify: `stock-ai/tests/unit/test_buy_point_validation.py`

**Interfaces:**
- Consumes: Task 2 bundle and integrity manifest.
- Produces: frozen profile v2 with train/validation calibrations and one-time v2 validation artifact.

- [ ] **Step 1: Write failing leakage and integrity tests**

```python
def test_freeze_profile_contains_only_train_validation_calibrations(tmp_path) -> None:
    profile = freeze_profile(bundle_with_extreme_test_winners(), tmp_path)
    assert profile["schema"] == "buy-point-selection-frozen-profile-v2"
    assert profile["calibrations"] == expected_without_test_winners


def test_run_test_rejects_incomplete_replay_manifest(tmp_path) -> None:
    result = run_test_with_manifest(tmp_path, complete=False)
    assert result.returncode == 2
    assert "point-in-time replay is incomplete" in result.stderr


def test_run_test_uses_frozen_calibration_for_test_candidate_ranking(tmp_path) -> None:
    artifact = run_frozen_test(_ranking_fixture(), tmp_path)
    assert artifact["technical_core_metrics"]["triggered_trades"] == 1
    assert artifact["selected_test_structure_ids"] == ["train-ranked-candidate"]
```

- [ ] **Step 2: Run Task 3 tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_validation.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py
```

Expected: profile v1 lacks frozen calibrations and manifest checks.

- [ ] **Step 3: Freeze train/validation calibration and rank test opportunities**

`--freeze-profile` requires observations and a complete matching manifest. It builds calibration from train plus validation dates only, serializes the calibration mapping into profile v2, and stores the manifest hash. `--run-test` loads those frozen calibrations, resolves each test opportunity without reading its outcome, applies the production stable ranking and daily/sector limits, then computes test metrics only from the selected outcomes.

- [ ] **Step 4: Preserve one-time test identity**

Reject a second artifact for the same rule version and policy hash when its profile hash, split bounds, or manifest hash differs. Do not overwrite an existing frozen artifact with a different identity.

- [ ] **Step 5: Run Task 3 tests and commit**

Expected: focused tests pass.

```bash
git add stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  stock-ai/stock_ai/buy_point_selection/validation.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py \
  stock-ai/tests/unit/test_buy_point_validation.py
git commit -m "feat(stock-ai): freeze calibrated buy-point test replay"
```

---

### Task 4: Execute the Manual Historical Workflow

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md`
- Modify: `stock-ai/docs/PROJECT_LAYOUT.md`
- Generated and ignored: `stock-ai/output/buy-point-replay/*`
- Generated and ignored: `stock-ai/config/buy_point_selection_profile.json`
- Generated and ignored: `stock-ai/config/buy_point_selection_validation.json`

**Interfaces:**
- Produces: the real observation bundle, frozen profile, and validation v2 artifact.

- [ ] **Step 1: Complete and audit PIT backfill**

Run:

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2023-12-26 --end 2026-08-13
```

Expected: sector, ST, and announcement coverage are complete for every signal date.

- [ ] **Step 2: Generate the observation bundle**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/generate_buy_point_observations.py \
  --start 2023-12-26 --end 2026-08-04 \
  --out stock-ai/output/buy-point-replay
```

Expected: integrity is complete, at least 630 trading dates exist, and no `PENDING` result remains.

- [ ] **Step 3: Research, freeze, and run test once**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --research-train-validation \
  --trading-dates stock-ai/output/buy-point-replay/trading-dates.json \
  --observations stock-ai/output/buy-point-replay/outcome-observations.json \
  --manifest stock-ai/output/buy-point-replay/replay-integrity.json \
  --point-in-time-complete

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --freeze-profile \
  --trading-dates stock-ai/output/buy-point-replay/trading-dates.json \
  --observations stock-ai/output/buy-point-replay/outcome-observations.json \
  --manifest stock-ai/output/buy-point-replay/replay-integrity.json \
  --point-in-time-complete

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  --run-test --write-artifact \
  --trading-dates stock-ai/output/buy-point-replay/trading-dates.json \
  --observations stock-ai/output/buy-point-replay/outcome-observations.json \
  --manifest stock-ai/output/buy-point-replay/replay-integrity.json \
  --point-in-time-complete
```

- [ ] **Step 4: Run full verification**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_*.py \
  stock-ai/tests/unit/test_sync_buy_point_reference_data.py \
  stock-ai/tests/unit/test_generate_buy_point_observations_cli.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py \
  a-share-short-term-trading/tests/test_buy_point_*.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py

git diff --check
```

- [ ] **Step 5: Document commands and commit**

```bash
git add stock-ai/docs/CAPABILITIES.md stock-ai/docs/PROJECT_LAYOUT.md
git commit -m "docs(stock-ai): document PIT replay and frozen test"
```

Do not report `LIVE` or profitability unless both the generated v2 artifact and the existing forward gate pass.
