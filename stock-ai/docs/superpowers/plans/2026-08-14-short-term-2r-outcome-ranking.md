# Short-Term 2R Outcome Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add auditable five-session 2R path labels, chronological probability calibration, and calibration-first candidate ranking to the manual buy-point selector.

**Architecture:** Keep deterministic setup detection and price planning unchanged. Enrich the conservative execution simulator with path outcomes and excursions, derive frozen hierarchical calibration metrics from point-in-time observations, then inject only validated calibration records into candidate qualification, ranking, reporting, and append-only audit payloads.

**Tech Stack:** Python 3.12, frozen dataclasses, Decimal arithmetic, pytest, JSON validation artifacts, existing MySQL-backed manual selector.

## Global Constraints

- The objective is positive net expectancy and controlled drawdown over 3—5 trading sessions, not next-day limit-up recall.
- A successful path reaches the frozen 2R target before the frozen invalidation price after a real two-session trigger.
- Untriggered, cancelled, stopped, expired, and ambiguous daily-bar paths remain in the dataset.
- Same-session target and stop ambiguity is resolved as stop first.
- All returns include the existing conservative commissions, tax, and slippage.
- The selector remains manual and never submits broker orders.
- Missing calibration, incomplete point-in-time data, stale artifacts, or insufficient samples fail closed.
- Eastmoney legacy eight/eleven-dimension AI analysis remains prohibited.
- Observe and shadow rows always have zero or absent executable shares.
- Daily formal output remains zero to three names and may be empty.
- Existing 3—5-day decision memory and five hard-event rules are not changed.
- Do not add generated validation artifacts, holdings, account data, or personal memory to Git.

---

### Task 1: Five-Session Path Outcome and Excursion Labels

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/models.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/execution.py`
- Modify: `stock-ai/tests/unit/test_buy_point_execution.py`

**Interfaces:**
- Produces: `OutcomeLabel`, `SimulatedTrade.outcome`, `SimulatedTrade.mfe`, `SimulatedTrade.mae`, and `SimulatedTrade.intraday_order_ambiguous`.
- Consumes: existing `PricePlan`, `BuyPointBar`, `ExecutionCosts`, and conservative exit legs.
- Used by: Task 2 observation loading and calibration.

- [ ] **Step 1: Write failing outcome-label tests**

Add focused tests that prove the production change would fail without the new fields:

```python
def test_target_before_stop_records_two_r_path_and_excursions() -> None:
    trade = simulate_plan(_plan(), target_then_breakeven_bars(), COSTS, sector_code="S1")
    assert trade.outcome is OutcomeLabel.TARGET_2R_FIRST
    assert trade.mfe == Decimal("0.068238692001068238692001068")
    assert trade.mae >= Decimal("0")


def test_untriggered_plan_is_retained_as_not_triggered() -> None:
    trade = simulate_plan(_plan(), two_untriggered_bars(), COSTS, sector_code="S1")
    assert trade.outcome is OutcomeLabel.NOT_TRIGGERED
    assert trade.mfe is None
    assert trade.mae is None


def test_same_bar_target_and_stop_marks_ambiguity_and_stop_first() -> None:
    trade = simulate_plan(_plan(), same_bar_stop_and_target(), COSTS, sector_code="S1")
    assert trade.outcome is OutcomeLabel.STOP_FIRST
    assert trade.intraday_order_ambiguous


def test_five_session_time_exit_classifies_gain_loss_and_flat() -> None:
    assert simulate_plan(_plan(), gain_bars(), COSTS, sector_code="S1").outcome is OutcomeLabel.EXPIRY_GAIN
    assert simulate_plan(_plan(), loss_bars(), COSTS, sector_code="S1").outcome is OutcomeLabel.EXPIRY_LOSS
```

- [ ] **Step 2: Run Task 1 tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_execution.py
```

Expected: failures report missing `OutcomeLabel` or missing `SimulatedTrade` fields.

- [ ] **Step 3: Add immutable outcome labels and conservative path classification**

Add this enum to `models.py`:

```python
class OutcomeLabel(str, Enum):
    NOT_TRIGGERED = "NOT_TRIGGERED"
    TARGET_2R_FIRST = "TARGET_2R_FIRST"
    STOP_FIRST = "STOP_FIRST"
    EXPIRY_GAIN = "EXPIRY_GAIN"
    EXPIRY_LOSS = "EXPIRY_LOSS"
    EXPIRY_FLAT = "EXPIRY_FLAT"
    PENDING = "PENDING"
```

Extend `SimulatedTrade` with the four produced fields. Compute MFE as the maximum non-negative `(high / actual_entry_price) - 1` and MAE as the maximum non-negative `1 - (low / actual_entry_price)` through the final simulated exit session. Preserve complete exit legs after a 2R partial reduction. Classify a closed path from chronological exit legs and final net return; classify insufficient post-entry bars as `PENDING`. For a bar that touches both initial invalidation and 2R before either event has occurred, set ambiguity true and retain stop-first execution.

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run the Step 2 command. Expected: all execution tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock-ai/stock_ai/buy_point_selection/models.py \
  stock-ai/stock_ai/buy_point_selection/execution.py \
  stock-ai/tests/unit/test_buy_point_execution.py
git commit -m "feat(stock-ai): label five-session 2R outcomes"
```

---

### Task 2: Chronological Outcome Calibration and Artifact V2

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/models.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/validation.py`
- Modify: `stock-ai/scripts/analysis/backtest_buy_point_selection.py`
- Modify: `stock-ai/tests/unit/test_buy_point_validation.py`
- Modify: `stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py`

**Interfaces:**
- Produces: `OutcomeCalibration`, `calibration_key`, `build_outcome_calibrations`, `resolve_outcome_calibration`, `trade_observation_from_simulation`, and validation artifact schema `buy-point-selection-validation-v2`.
- Consumes: Task 1 `OutcomeLabel` plus existing chronological splits and promotion metrics.
- Used by: Tasks 3 and 4.

- [ ] **Step 1: Write failing calibration tests**

Add tests for triggered denominators, Wilson intervals, excursions, hierarchy, and fail-closed parsing:

```python
def test_calibration_excludes_untriggered_plans_from_triggered_rates() -> None:
    calibration = build_outcome_calibrations(
        observations_with_two_targets_one_stop_one_untriggered(),
        test_dates=(),
        trading_dates=_trading_dates(63),
    )
    setup = calibration[calibration_key(SetupType.PRE_BREAKOUT, None, None)]
    assert setup.total_plans == 4
    assert setup.triggered_trades == 3
    assert setup.target_2r_rate == Decimal("0.6666666666666666666666666667")
    assert setup.stop_first_rate == Decimal("0.3333333333333333333333333333")


def test_calibration_uses_fixed_hierarchy_and_minimum_thirty_samples() -> None:
    resolved = resolve_outcome_calibration(calibrations, SetupType.PRE_BREAKOUT, "ALLOW", True)
    assert resolved.key == calibration_key(SetupType.PRE_BREAKOUT, "ALLOW", None)
    assert resolved.triggered_trades >= 30


def test_artifact_v1_or_missing_outcome_fields_fail_closed(tmp_path) -> None:
    release = load_historical_release(
        v1_artifact,
        expected_rule_version=SelectionPolicy().rule_version,
        expected_policy_hash=policy_hash(SelectionPolicy()),
    )
    assert not release.live_eligible
    assert "VALIDATION_SCHEMA_MISMATCH" in release.reasons
```

- [ ] **Step 2: Run Task 2 tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_validation.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py
```

Expected: calibration types/functions and artifact v2 are absent.

- [ ] **Step 3: Extend observation and calibration models**

Extend `TradeObservation` with `outcome`, `market_status`, `sector_resonating`, `mfe`, and `mae`. Retain untriggered rows in `total_plans`, but exclude `NOT_TRIGGERED` and `PENDING` from net expectancy, Profit Factor, 2R rate, and stop rate denominators. Add `total_plans` and `untriggered_plans` to `SetupMetrics` without changing existing promotion thresholds.

`OutcomeCalibration` must contain the grouping key, data cutoff date, sample counts, net expectancy, rolling stability, 2R and stop rates with 95% Wilson bounds, Profit Factor, profit/loss ratio, median MFE/MAE, nearest-rank MFE 25th percentile, nearest-rank MAE 75th percentile, `promoted`, and rejection reasons. `trade_observation_from_simulation` converts a Task 1 simulation plus its setup, market, sector-resonance, and resolution date into the exact immutable observation used by JSON export and metric computation.

- [ ] **Step 4: Implement deterministic calibration hierarchy**

Build all three non-overlapping views from the same observations:

```python
calibration_key(setup, market_status, sector_resonating)
calibration_key(setup, market_status, None)
calibration_key(setup, None, None)
```

At runtime resolve from most specific to least specific and accept the first cell with at least 30 triggered observations. A cell is promoted only when `_performance_reasons(metrics, 30)` is empty. Use 95% Wilson bounds and nearest-rank percentiles; do not round stored Decimal metrics.

- [ ] **Step 5: Bump the rule and artifact identity**

Change `SelectionPolicy.rule_version` to `buy-point-selection-3.1.0`. Require observation JSON rows to contain all Task 2 fields. Emit `buy-point-selection-validation-v2` with a `calibrations` mapping. Extend `HistoricalRelease` with a default-empty calibration mapping so missing, stale, v1, or malformed artifacts remain non-live without breaking callers.

- [ ] **Step 6: Run Task 2 tests and verify GREEN**

Run the Step 2 command. Expected: all validation and backtest CLI tests pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add stock-ai/stock_ai/buy_point_selection/models.py \
  stock-ai/stock_ai/buy_point_selection/validation.py \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  stock-ai/tests/unit/test_buy_point_validation.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py
git commit -m "feat(stock-ai): calibrate 2R outcomes chronologically"
```

Do not commit a generated validation artifact.

---

### Task 3: Calibration-Gated Qualification and Ranking

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/service.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/formatting.py`
- Modify: `stock-ai/tests/unit/test_buy_point_service.py`

**Interfaces:**
- Consumes: Task 2 calibration mapping and resolver.
- Produces: `SelectionItem.calibration`, fail-closed calibration reasons, and calibration-first stable ranking.
- Used by: Task 4 runtime materialization.

- [ ] **Step 1: Write failing qualification and ranking tests**

```python
def test_missing_or_insufficient_calibration_downgrades_to_observe() -> None:
    result = select_buy_points(request(calibrations={}))
    assert result.qualified == ()
    assert result.observe[0].reasons == ("CALIBRATION_MISSING",)


def test_negative_calibration_cannot_gain_trade_qualification() -> None:
    result = select_buy_points(request(calibrations=negative_calibration()))
    assert result.qualified == ()
    assert result.observe[0].reasons == ("CALIBRATION_NOT_PROMOTED",)


def test_ranking_prefers_expectancy_then_target_rate_then_lower_stop_rate() -> None:
    result = select_buy_points(request(candidates=three_candidates(), calibrations=ranked_calibrations()))
    assert [item.code for item in result.qualified] == ["600003", "600001", "600002"]
```

- [ ] **Step 2: Run Task 3 tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_service.py
```

Expected: selection input and items have no calibration behavior.

- [ ] **Step 3: Fail closed before formal eligibility**

Add a calibration mapping to `SelectionInput` and a selected calibration to `SelectionItem`. After a price plan is valid, resolve the candidate's setup, current market status, and sector-resonating state. Missing/under-30 calibration becomes `OBSERVE/CALIBRATION_MISSING`; a non-promoted cell becomes `OBSERVE/CALIBRATION_NOT_PROMOTED`. Neither receives a price plan or shares in the observe output.

- [ ] **Step 4: Replace the formal ranking key**

Use this stable order:

```python
(
    -calibration.net_expectancy,
    -calibration.target_2r_rate,
    calibration.stop_first_rate,
    -calibration.positive_rolling_window_ratio,
    plan.risk_distance / plan.trigger_price,
    code,
)
```

Retain the existing one-sector-per-day, total exposure, `ALLOW/LIMITED/FREEZE`, and zero-to-three limits after sorting.

- [ ] **Step 5: Render calibrated research facts**

Formal rows show integer Wilson ranges, triggered sample size, net expectancy, trigger, invalidation, 2R target, and maximum shares. Observe rows show the calibration rejection reason and never show shares.

- [ ] **Step 6: Run Task 3 tests and verify GREEN**

Run the Step 2 command. Expected: all service and formatting tests pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add stock-ai/stock_ai/buy_point_selection/service.py \
  stock-ai/stock_ai/buy_point_selection/formatting.py \
  stock-ai/tests/unit/test_buy_point_service.py
git commit -m "feat(stock-ai): rank buy points by calibrated expectancy"
```

---

### Task 4: Manual Runtime Wiring, Report, and Audit Payload

**Files:**
- Modify: `a-share-short-term-trading/scripts/select_short_term_candidates.py`
- Modify: `a-share-short-term-trading/short_term_trading/buy_point_selection_service.py`
- Modify: `a-share-short-term-trading/tests/test_buy_point_selection_service.py`
- Modify: `a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py`
- Modify: `stock-ai/tests/unit/test_buy_point_full_universe_runtime.py`

**Interfaces:**
- Consumes: Task 2 `HistoricalRelease.calibrations` and Task 3 `SelectionItem.calibration`.
- Produces: calibrated manual reports and persisted calibration evidence inside the existing candidate `sector_metrics_json`.

- [ ] **Step 1: Write failing runtime tests**

```python
def test_scan_receives_historical_calibrations_before_selection() -> None:
    runtime = runtime_with_calibrated_release()
    report = runtime.execute(
        context=runtime.context,
        analysis_date=ANALYSIS_DATE,
        trading_date=TRADING_DATE,
    )
    assert report.shadow[0].calibration.triggered_trades == 40


def test_runtime_report_prints_plan_and_probability_ranges_without_live_permission() -> None:
    text = render_buy_point_runtime_report(shadow_calibrated_report())
    assert "2R概率" in text
    assert "止损概率" in text
    assert "无交易资格" in text
    assert "最大股数" not in text


def test_candidate_audit_payload_contains_calibration_identity() -> None:
    persist_buy_point_runtime(
        report,
        _result(),
        dependencies,
        _request(),
        repository,
    )
    assert repository.rows[0][0].sector_metrics["calibration_key"] == expected_key
```

- [ ] **Step 2: Run Task 4 tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_full_universe_runtime.py \
  a-share-short-term-trading/tests/test_buy_point_selection_service.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py
```

Expected: runtime models and scan do not carry calibration evidence.

- [ ] **Step 3: Load the historical release before scanning**

In `DefaultRuntime.execute`, load and validate the v2 historical artifact immediately after constructing `SelectionPolicy`. Pass `historical_release.calibrations` through `scan_buy_point_universe` into `SelectionInput`. Reuse the same `HistoricalRelease` object during materialization so artifact validation and ranking cannot disagree.

- [ ] **Step 4: Carry calibration through materialization and persistence**

Add an optional calibration field to `BuyPointRuntimeItem`. Copy it for formal, observe, and newly generated shadow rows. Add the calibration key, sample count, Wilson bounds, net expectancy, and data cutoff to `CandidateV3.sector_metrics`; do not add a migration because this field is already JSON.

- [ ] **Step 5: Expand the manual report without creating actionable shadow output**

Formal rows show all plan prices and calibrated metrics. Calibrated shadow rows show the same research metrics and frozen plan prices but the phrase `无交易资格` and no maximum shares. Observe rows show metrics when available and no plan sizing. Legacy shadows remain unchanged.

- [ ] **Step 6: Run Task 4 tests and verify GREEN**

Run the Step 2 command. Expected: all runtime, materialization, CLI, and audit payload tests pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add a-share-short-term-trading/scripts/select_short_term_candidates.py \
  a-share-short-term-trading/short_term_trading/buy_point_selection_service.py \
  a-share-short-term-trading/tests/test_buy_point_selection_service.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py \
  stock-ai/tests/unit/test_buy_point_full_universe_runtime.py
git commit -m "feat(stock-ai): wire calibrated buy-point reports"
```

---

### Task 5: Documentation and Full Verification

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md`
- Modify: `stock-ai/docs/PROJECT_LAYOUT.md`
- Modify: `a-share-short-term-trading/README.md`

**Interfaces:**
- Documents: rule `buy-point-selection-3.1.0`, observation v2 fields, manual backtest flow, probability interpretation, and continued `SHADOW` constraints.

- [ ] **Step 1: Update operator documentation**

Document that 2R probability is a historical Wilson interval for the resolved calibration cohort, not an individualized guarantee. List the required observation fields: `exit_date`, `setup_type`, `sector_code`, `net_return`, `net_pnl`, `outcome`, `market_status`, `sector_resonating`, `mfe`, and `mae`. State that v1 artifacts and observations without these fields fail closed.

- [ ] **Step 2: Run the complete offline regression suite**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_*.py \
  stock-ai/tests/unit/test_sync_buy_point_reference_data.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py \
  a-share-short-term-trading/tests/test_buy_point_*.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py
```

Expected: zero failures.

- [ ] **Step 3: Verify CLI help and diff hygiene**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/python stock-ai/scripts/analysis/backtest_buy_point_selection.py --help

PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/python a-share-short-term-trading/scripts/select_short_term_candidates.py --help

git diff --check
```

Expected: both CLIs exit zero and no whitespace errors are reported.

- [ ] **Step 4: Run a fail-closed manual smoke test**

Run the selector at a reproducible intraday timestamp. An absent or non-promoted v2 artifact must retain `SHADOW`, produce no executable formal rows, and preserve calibrated research facts only when a valid calibration exists.

- [ ] **Step 5: Commit documentation**

```bash
git add stock-ai/docs/CAPABILITIES.md stock-ai/docs/PROJECT_LAYOUT.md \
  a-share-short-term-trading/README.md
git commit -m "docs(stock-ai): document calibrated 2R selection"
```

Do not claim strategy promotion or profitability unless a fresh, complete point-in-time frozen run and the existing forward gate both pass.
