# High-Precision Short-Term Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned, high-precision short-term selector with orthogonal technical gates and promote it only when a corrected out-of-sample proxy backtest passes the approved sample, win-rate, and expectancy thresholds.

**Architecture:** Pure indicator, relative-strength, execution-proxy, and validation modules live under `stock_ai`; the existing selector composes them through an explicit policy while preserving 2.0 behavior. The manual CLI reads a validated promotion artifact and uses 2.1 only when the artifact passes strict schema and metric checks; otherwise it stays on 2.0. Backtests and production call the same indicator and selector functions.

**Tech Stack:** Python 3.11, dataclasses, pandas, SQLAlchemy, pytest, MySQL 8, existing Pydantic v1.2 persistence contracts.

## Global Constraints

- Precision is more important than candidate count; never fill quotas with rejected stocks.
- Keep `short-term-selection-2.0.0` readable and production-safe.
- Enable `short-term-selection-2.1.0` only when test trades are at least 100, win rate improves by at least 5 percentage points, expectancy is non-negative, and neither shape has zero samples.
- Relative-strength coverage below 95% fails the 2.1 run closed.
- `LIMITED` and `FREEZE` never create a 2.1 executable candidate.
- Historical chips, order books, flows, and sectors are not fabricated; the backtest is labeled `technical_execution_proxy`.
- Use only completed bars available on or before each signal date.
- Do not add scheduling, dashboards, push notifications, or automatic ordering.
- User-visible output contains no emoji, credentials, connection URLs, holdings details, or profitability promises.
- Preserve unrelated dirty workspace files and stage exact paths only.

---

### Task 1: Pure High-Precision Technical Indicators

**Files:**
- Create: `stock-ai/stock_ai/technical_indicators.py`
- Create: `stock-ai/tests/unit/test_technical_indicators.py`

**Interfaces:**
- Consumes: a sequence of bar-like objects with `high`, `low`, `close`, and `amount_qian` attributes.
- Produces: `TechnicalIndicatorSnapshot` and `compute_technical_indicators(bars) -> TechnicalIndicatorSnapshot`.

- [x] **Step 1: Write failing literal indicator tests**

Add tests whose expected values are hand-derived, not computed with production helpers:

```python
def test_monotonic_exponential_prices_have_maximum_trend_r2() -> None:
    snapshot = compute_technical_indicators(exponential_bars(60, daily_log_return=0.01))
    assert snapshot.trend_r2_20 == pytest.approx(1.0, abs=1e-10)
    assert snapshot.trend_slope_20 == pytest.approx(0.01, abs=1e-10)


def test_constant_true_range_produces_literal_atr() -> None:
    snapshot = compute_technical_indicators(constant_range_bars(60, true_range=2.0))
    assert snapshot.atr14 == pytest.approx(2.0)
    assert snapshot.atr_pct == pytest.approx(0.02)


def test_all_up_closes_produce_rsi_100_and_adx_100() -> None:
    snapshot = compute_technical_indicators(strictly_rising_bars(60))
    assert snapshot.rsi14 == pytest.approx(100.0)
    assert snapshot.adx14 == pytest.approx(100.0)
```

Add independent tests for `return20`, `breakout_pct`, `average_amount5`, `advance_amount5`, `pullback_amount5`, and `pullback_amount_ratio`. Add rejection tests for fewer than 60 bars, duplicate dates, non-finite values, zero close, and zero advance amount.

- [x] **Step 2: Run the indicator tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_technical_indicators.py
```

Expected: collection fails because `stock_ai.technical_indicators` does not exist.

- [x] **Step 3: Implement the minimal immutable indicator module**

Use this public shape:

```python
class IndicatorInputError(ValueError):
    pass


@dataclass(frozen=True)
class TechnicalIndicatorSnapshot:
    adx14: float
    rsi14: float
    atr14: float
    atr_pct: float
    trend_r2_20: float
    trend_slope_20: float
    return20: float
    breakout_pct: float
    average_amount5: float
    amount_ratio: float
    advance_amount5: float
    pullback_amount5: float
    pullback_amount_ratio: float


def compute_technical_indicators(bars: Sequence[BarLike]) -> TechnicalIndicatorSnapshot:
    ...
```

Implement Wilder smoothing for ATR, RSI, and ADX. Calculate trend regression on log closes with direct sums; do not add NumPy. `breakout_pct` must use `max(high[-21:-1])`, and `average_amount5` must use `amount[-6:-1]`.

- [x] **Step 4: Run GREEN and selector regression tests**

Run the Task 1 test plus `stock-ai/tests/unit/test_short_term_selection.py`. Expected: all pass.

- [x] **Step 5: Commit Task 1**

```bash
git add stock-ai/stock_ai/technical_indicators.py stock-ai/tests/unit/test_technical_indicators.py
git commit -m "feat(stock-ai): add high-precision technical indicators"
```

---

### Task 2: Full-Market Relative Strength With Coverage Gate

**Files:**
- Create: `stock-ai/stock_ai/relative_strength.py`
- Create: `stock-ai/tests/unit/test_relative_strength.py`

**Interfaces:**
- Consumes: normalized current/prior close pairs or one SQLAlchemy engine and analysis date.
- Produces: `RelativeStrengthSnapshot(percentiles, eligible_count, current_count, coverage_ratio, prior_trade_date)` and `load_relative_strength_snapshot(engine, analysis_date)`.

- [x] **Step 1: Write failing percentile and coverage tests**

```python
def test_tied_returns_receive_the_average_percentile_rank() -> None:
    snapshot = build_relative_strength_snapshot(
        current_count=4,
        prior_trade_date=date(2026, 7, 13),
        pairs=(
            ClosePair("600001", 10, 11),
            ClosePair("600002", 10, 12),
            ClosePair("000001", 10, 11),
            ClosePair("000002", 10, 9),
        ),
    )
    assert snapshot.percentiles["600002"] == 1.0
    assert snapshot.percentiles["600001"] == pytest.approx(0.5)
    assert snapshot.percentiles["000001"] == pytest.approx(0.5)
    assert snapshot.percentiles["000002"] == 0.0


def test_coverage_below_95_percent_is_not_usable() -> None:
    snapshot = build_relative_strength_snapshot(
        current_count=100, prior_trade_date=PRIOR, pairs=fixture_pairs(94)
    )
    assert snapshot.coverage_ratio == 0.94
    assert snapshot.is_usable is False
```

Add tests that suffix and six-digit duplicate rows resolve to one code, invalid closes are excluded, and a one-code universe receives percentile 1.0.

- [x] **Step 2: Run and verify RED**

Run `pytest stock-ai/tests/unit/test_relative_strength.py` with the standard environment. Expected: module missing.

- [x] **Step 3: Implement pure ranking and the MySQL adapter**

Use average ranks for ties and `(average_rank - 1) / (n - 1)`. The adapter must:

1. Resolve the 21st distinct completed market date at or before `analysis_date`.
2. Read valid main-board closes at the analysis and prior dates.
3. Normalize `600000.SH` and `600000` to one code deterministically, preferring the suffixed row when duplicates exist.
4. Return coverage rather than silently accepting missing pairs.

- [x] **Step 4: Run GREEN and a read-only rollback integration test**

Add an integration assertion to `a-share-short-term-trading/tests/integration/test_mysql_repositories.py` that the configured database produces a snapshot with dates in order and percentiles in `[0, 1]`; keep it behind `STT_MYSQL_INTEGRATION=1` and perform no writes.

- [x] **Step 5: Commit Task 2**

```bash
git add stock-ai/stock_ai/relative_strength.py stock-ai/tests/unit/test_relative_strength.py \
  a-share-short-term-trading/tests/integration/test_mysql_repositories.py
git commit -m "feat(stock-ai): calculate full-market relative strength"
```

---

### Task 3: Versioned Strict Selection Policies

**Files:**
- Modify: `stock-ai/stock_ai/short_term_selection.py`
- Modify: `stock-ai/tests/unit/test_short_term_selection.py`

**Interfaces:**
- Consumes: Task 1 indicators, Task 2 percentiles, and an explicit `SelectionPolicy`.
- Produces: `BASELINE_POLICY`, `STRICT_A`, `STRICT_B`, `STRICT_C`, and policy-aware `select_short_term_candidates`.

- [x] **Step 1: Write failing high-precision gate tests**

Add real-bar tests where one mutation breaks one behavior:

```python
def test_strict_breakout_rejects_an_overheated_rsi() -> None:
    result = select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=[ROW],
        bars_by_code={CODE: overheated_breakout_bars()},
        relative_strength_by_code={CODE: 0.90},
        policy=STRICT_A,
        holding_codes=set(),
        st_codes=set(),
    )
    assert [(item.code, item.reason) for item in result.rejected] == [
        (CODE, "RSI_OVERHEATED")
    ]
```

Cover exact boundaries for ADX, RSI, ATR%, R², relative strength, breakout percentage, 2.5 amount ratio, pullback amount ratio, and stop confirmation. Add a no-lookahead test that appends and mutates bars after `analysis_date` and gets the identical signal. Add a compatibility test proving omitted policy retains the 2.0 result.

- [x] **Step 2: Run RED**

Expected failures: missing policy constants and unsupported selector arguments.

- [x] **Step 3: Implement policies and structured rejection codes**

Use immutable policy fields with exact values from the spec. Keep `policy=None` equivalent to `BASELINE_POLICY`. For a 2.1 policy, require `relative_strength_by_code`; a missing code rejects with `RELATIVE_STRENGTH_MISSING`. Add every Task 1 metric and `relative_strength_percentile` to `CandidateSignal.metrics` when accepted.

Do not replace current base-shape tests. Evaluate the 2.0 shape first, then apply the selected strict gate and return the first stable rejection code.

- [x] **Step 4: Run GREEN and adapter regressions**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_technical_indicators.py \
  stock-ai/tests/unit/test_relative_strength.py \
  stock-ai/tests/unit/test_short_term_selection.py \
  stock-ai/tests/unit/test_short_term_trade.py
```

- [x] **Step 5: Commit Task 3**

```bash
git add stock-ai/stock_ai/short_term_selection.py stock-ai/tests/unit/test_short_term_selection.py
git commit -m "feat(stock-ai): add strict high-precision selection policies"
```

---

### Task 4: Technical Proxy Plans and Finite-Capital Portfolio Simulation

**Files:**
- Create: `stock-ai/stock_ai/technical_execution.py`
- Create: `stock-ai/tests/unit/test_technical_execution.py`

**Interfaces:**
- Consumes: accepted `CandidateSignal`, its completed bars, and subsequent daily bars.
- Produces: `TechnicalProxyPlan`, `ProxyTrade`, `PortfolioBacktestResult`, `build_proxy_plan`, `simulate_proxy_trade`, and `simulate_proxy_portfolio`.

- [x] **Step 1: Write failing plan and execution tests**

Use literal prices:

```python
def test_gap_above_entry_ceiling_is_not_filled() -> None:
    result = simulate_proxy_trade(
        literal_plan(trigger=10.00, ceiling=10.15, invalidation=9.70, target=10.45),
        [bar("2026-08-11", open=10.16, high=10.50, low=10.10, close=10.30)],
    )
    assert result.status == "GAP_REJECTED"


def test_same_day_stop_and_target_uses_the_stop() -> None:
    result = simulate_proxy_trade(
        literal_plan(trigger=10.00, ceiling=10.15, invalidation=9.70, target=10.45),
        [bar("2026-08-11", open=10.00, high=10.50, low=9.60, close=10.20)],
        commission_rate=0,
        slippage_rate=0,
    )
    assert result.exit_reason == "STOP"
    assert result.exit_price == 9.70
```

Add tests for untriggered T+1, trigger fill, exact 1.5R target, risk below 1.5%, risk above 5%, five-day time exit, no same-code overlap, five-session cooldown, two-slot cap, one-position 50% allocation, and a hand-calculated daily equity drawdown.

- [x] **Step 2: Run RED**

Expected: `stock_ai.technical_execution` is missing.

- [x] **Step 3: Implement exact proxy plan formulas and conservative fills**

Use the cent rounding and formulas from the design. Model every non-fill with a status code. A trade occupies one 50% slot from entry through exit. Compute equity for every market date using marked closes, cash, and realized proceeds; do not derive portfolio drawdown by multiplying standalone trade returns.

- [x] **Step 4: Run GREEN and mutation checks**

Verify that changing ceiling comparison from `>` to `>=`, changing stop-first ordering, removing cooldown, or allowing a third slot would each fail a named test.

- [x] **Step 5: Commit Task 4**

```bash
git add stock-ai/stock_ai/technical_execution.py stock-ai/tests/unit/test_technical_execution.py
git commit -m "feat(stock-ai): simulate conservative technical execution"
```

---

### Task 5: Walk-Forward Profile Selection and Promotion Artifact

**Files:**
- Create: `stock-ai/stock_ai/selection_validation.py`
- Create: `stock-ai/tests/unit/test_selection_validation.py`
- Create at verification time: `stock-ai/config/short_term_selection_validation.json`

**Interfaces:**
- Consumes: dated baseline/profile backtest summaries.
- Produces: `chronological_splits`, `wilson_lower_bound`, `choose_validation_profile`, `evaluate_promotion`, `ValidationArtifact`, and `load_promoted_policy`.

- [x] **Step 1: Write failing time-isolation and promotion tests**

```python
def test_profile_choice_never_reads_test_metrics() -> None:
    chosen = choose_validation_profile(
        validation={"STRICT_A": valid(80, 44), "STRICT_B": valid(80, 48)},
    )
    assert chosen == "STRICT_B"


def test_negative_expectancy_prevents_promotion_despite_high_win_rate() -> None:
    decision = evaluate_promotion(
        baseline=test_metrics(200, win_rate=0.40, expectancy=-0.4),
        candidate=test_metrics(120, win_rate=0.55, expectancy=-0.01),
        shape_counts={"BREAKOUT": 60, "PULLBACK": 60},
    )
    assert decision.promoted is False
    assert "NEGATIVE_EXPECTANCY" in decision.reasons
```

Cover fewer than 120 sessions per split, validation total below 75, either validation shape below 25, test total below 100, improvement exactly 5 percentage points, zero shape samples, malformed artifacts, unknown rule versions, and Wilson literals.

- [x] **Step 2: Run RED**

Expected: validation module missing.

- [x] **Step 3: Implement immutable validation logic**

`choose_validation_profile` accepts only validation metrics, making test-set leakage impossible through its public interface. Evaluate the chosen profile on test data later through `evaluate_promotion`. Serialize the artifact with schema version, data bounds, split bounds, costs, selected profile, all metrics, promotion boolean, reasons, and generation timestamp. `load_promoted_policy` returns `BASELINE_POLICY` unless every required field validates and `promoted` is true.

- [x] **Step 4: Run GREEN**

Run Task 5 tests plus Task 3 and Task 4 suites.

- [x] **Step 5: Commit Task 5 without a generated artifact**

```bash
git add stock-ai/stock_ai/selection_validation.py stock-ai/tests/unit/test_selection_validation.py
git commit -m "feat(stock-ai): gate strict rules with walk-forward validation"
```

---

### Task 6: Rebuild the Backtest Around Shared Production Rules

**Files:**
- Modify: `stock-ai/scripts/analysis/backtest_short_term_trade.py`
- Modify: `stock-ai/tests/unit/test_short_term_selection.py`
- Create: `stock-ai/tests/unit/test_backtest_short_term_trade.py`

**Interfaces:**
- Consumes: Tasks 1–5 and MySQL `stock_daily`.
- Produces: one baseline/profile comparison report and optional validated promotion artifact.

- [x] **Step 1: Write failing script-level behavior tests**

Run the script module against an in-memory DataFrame and assert:

- signal classification sees only bars through T;
- relative strength is computed from the whole fixture universe, not selected rows;
- baseline and three strict profiles use identical dates, costs, and portfolio simulation;
- chronological splits are disjoint and ordered;
- `--write-validation PATH` writes an artifact only after a complete run;
- malformed chronology exits with code 2 and no promotion conclusion;
- JSON output uses `technical_execution_proxy` and contains no credentials or holdings.

- [x] **Step 2: Run RED**

Expected: old `run_backtest` lacks policy comparison, portfolio result, and artifact CLI.

- [x] **Step 3: Implement cached daily orchestration**

Compute indicators and relative-strength snapshots once per code/date, then reuse them across baseline and strict profiles. Run each policy once and collect both shapes in the same pass. Change default dates to `2024-01-02` through the latest configured completed date so 60/20/20 splits can each contain at least 120 sessions. Add:

```text
--output text|json
--write-validation PATH
--commission-rate 0.001
--slippage-rate 0.001
--max-positions 2
--cooldown-sessions 5
```

The report must include training, validation, and test metrics, rejection counters, the selected validation profile, and promotion reasons.

- [x] **Step 4: Run GREEN and one local fixture benchmark**

The test fixture benchmark must finish in under 5 seconds; this protects against accidentally recalculating indicators for every policy.

- [x] **Step 5: Commit Task 6**

```bash
git add stock-ai/scripts/analysis/backtest_short_term_trade.py \
  stock-ai/tests/unit/test_short_term_selection.py \
  stock-ai/tests/unit/test_backtest_short_term_trade.py
git commit -m "feat(stock-ai): compare strict selectors out of sample"
```

---

### Task 7: Production CLI, Evidence, and Market-State Integration

**Files:**
- Modify: `a-share-short-term-trading/scripts/select_short_term_candidates.py`
- Modify: `a-share-short-term-trading/short_term_trading/selection_service.py`
- Modify: `a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py`
- Modify: `a-share-short-term-trading/tests/test_selection_service.py`

**Interfaces:**
- Consumes: validated artifact, selected policy, relative-strength snapshot, and current market state.
- Produces: safely versioned 2.0 or 2.1 candidates, evidence, plans, and chat reports.

- [x] **Step 1: Write failing production-gate tests**

Add tests proving:

- absent, malformed, failed, or stale artifact selects 2.0;
- promoted artifact selects its exact 2.1 profile and passes its rule version into `SelectionRequest`;
- 2.1 relative-strength coverage below 95% exits code 2 without prices;
- 2.1 under `LIMITED` saves observation candidates and no executable plan;
- 2.1 under `FREEZE` keeps the existing zero-share observation plan;
- technical evidence persists ADX, RSI, ATR%, R², relative strength, and the shape-specific volume/breakout metric;
- rerunning the same rule/date remains idempotent and does not overwrite 2.0 rows.

- [x] **Step 2: Run RED**

Expected: CLI always calls 2.0 and service still permits two LIMITED executable candidates.

- [x] **Step 3: Implement validated policy resolution**

Load `stock-ai/config/short_term_selection_validation.json` through Task 5. Load full-market relative strength only for a promoted 2.1 policy. Pass the explicit policy to the selector and its version to materialization. Keep 2.0 behavior unchanged.

In materialization, apply the stricter market rule only when `request.rule_version == "short-term-selection-2.1.0"`; this prevents changing historical 2.0 semantics.

- [x] **Step 4: Run GREEN and MySQL rollback integration**

Run the CLI/service tests, repository tests, then the configured integration tests. Confirm 2.0 and 2.1 deterministic IDs coexist.

- [x] **Step 5: Commit Task 7**

```bash
git add a-share-short-term-trading/scripts/select_short_term_candidates.py \
  a-share-short-term-trading/short_term_trading/selection_service.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py \
  a-share-short-term-trading/tests/test_selection_service.py
git commit -m "feat(stt): activate only validated strict selection rules"
```

---

### Task 8: Remote Validation, Promotion Decision, Documentation, and Final Verification

**Files:**
- Modify: `a-share-short-term-trading/README.md`
- Create: `stock-ai/config/short_term_selection_validation.json`
- Modify: `docs/superpowers/plans/2026-08-11-high-precision-short-term-selection.md` checkboxes only.

**Interfaces:**
- Consumes: completed implementation and configured read-only market history.
- Produces: reproducible validation evidence, the safe production policy decision, and operator documentation.

- [x] **Step 1: Run all local tests before accessing MySQL**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_market_codes.py \
  stock-ai/tests/unit/test_technical_indicators.py \
  stock-ai/tests/unit/test_relative_strength.py \
  stock-ai/tests/unit/test_short_term_selection.py \
  stock-ai/tests/unit/test_short_term_trade.py \
  stock-ai/tests/unit/test_technical_execution.py \
  stock-ai/tests/unit/test_selection_validation.py \
  stock-ai/tests/unit/test_backtest_short_term_trade.py \
  a-share-short-term-trading/tests --ignore=a-share-short-term-trading/tests/integration
```

- [x] **Step 2: Run the configured remote proxy backtest once**

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_short_term_trade.py \
  --start 2024-01-02 --end 2026-07-31 --output json \
  --write-validation stock-ai/config/short_term_selection_validation.json
```

Do not modify thresholds after seeing test metrics. Record the actual selected profile, sample sizes, win-rate change, expectancy, and promotion reasons. A failed promotion is a valid completed outcome.

- [x] **Step 3: Verify artifact replay and production resolution**

Run the backtest again without writing an artifact and require byte-stable metric JSON except `generated_at`. Load the committed artifact through `load_promoted_policy`; assert it resolves to 2.1 only if every approved gate passed, otherwise 2.0.

- [x] **Step 4: Run remote integration and one shadow CLI**

```bash
STT_MYSQL_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/integration/test_mysql_migrations.py \
  a-share-short-term-trading/tests/integration/test_mysql_repositories.py

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/select_short_term_candidates.py \
  --output text --skip-lanes
```

The shadow CLI must state the active rule, market state, and rejection counts and must not claim an order was placed.

- [x] **Step 5: Document operation and experimental outcome**

Update README with indicator meanings, relative-strength coverage, proxy limitations, artifact promotion rules, exact backtest command, active rule version, actual out-of-sample results, and the fact that failed validation leaves 2.0 active.

- [x] **Step 6: Run final verification and commit exact files**

Re-run the complete local suite, remote integration suite, `git diff --check`, and inspect `git status --short`. Then:

```bash
git add stock-ai/config/short_term_selection_validation.json \
  a-share-short-term-trading/README.md \
  docs/superpowers/plans/2026-08-11-high-precision-short-term-selection.md
git commit -m "docs(stt): record high-precision validation outcome"
```

Do not stage unrelated WeChat scripts, assets, `dist/`, credentials, holdings, or generated trade-level reports.
