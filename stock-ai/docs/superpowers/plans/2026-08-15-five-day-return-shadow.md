# Five-Day Return Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manual, zero-share `FIVE_DAY_RETURN` research track that compares four fixed entry/stop profiles, validates them on chronological train/validation/test segments, and permits only historically qualified profiles to enter separate forward shadow screens.

**Architecture:** Keep production `TWO_R` selection unchanged. Add isolated pure modules for profile math, execution, and validation; add a read-only runtime for point-in-time discovery; add strict immutable artifacts and a thin five-stage manual CLI. Research reads only train/validation outcomes, freeze writes fixed train+validation calibrations, and a separate one-shot test stage is the first component allowed to read test outcomes.

**Tech Stack:** Python 3.11, frozen dataclasses, `Decimal`, SQLAlchemy/PyMySQL read-only access, existing point-in-time buy-point inputs, deterministic JSON/Markdown artifacts, pytest.

## Global Constraints

- Run implementation commands from `/Users/huan.yu/dev/tools-workspace/stock-ai`.
- Schema is exactly `buy-point-five-day-return-shadow-v1`.
- Strategy mode is always `CASE_ANALYSIS_ONLY`; trade permission is always `NO-TRADE`; recursive `executable_shares` values are always `0`.
- Production rule `buy-point-selection-3.1.0`, production selector imports, `TWO_R` planning, validation, artifacts, candidate limits, and release state remain unchanged.
- Profiles are exactly, in order: `BREAKOUT_TRIGGER__FIXED_3_PERCENT`, `BREAKOUT_TRIGGER__STRUCTURE_ATR`, `PULLBACK_RECLAIM__FIXED_3_PERCENT`, and `PULLBACK_RECLAIM__STRUCTURE_ATR`.
- Entry validity is the two confirmed trading sessions after the signal date.
- `BREAKOUT_TRIGGER` uses `ceil_cent(structure_high + 0.01)`, 3% gap cancellation, 5% chase cancellation, and locked-limit-up cancellation.
- `PULLBACK_RECLAIM` requires `low <= signal_close <= close`, positive range, close location at least `0.60`, close no more than 3% above signal close, and no locked limit-up; fill is close plus buy slippage.
- `FIXED_3_PERCENT` uses `floor_cent(entry_price * 0.97)` and no ATR buffer.
- `STRUCTURE_ATR` uses `floor_cent(structure_low - 0.2 * ATR14)` and accepts actual entry-to-stop distance only in the inclusive range 1.5% to 5%.
- There is no profit target. Entry day is holding session 1; the only strategy exit before session 5 is the frozen stop; otherwise exit on session-5 close. Locked limit-down or suspension delays the real exit.
- Evaluation target notional is exactly `10000`; quantity is `max(100, floor(10000 / entry_price / 100) * 100)`; sizing version is immutable and separate from costs.
- Evaluation portfolio capital is a fixed research constant of `30000` with at most three concurrently active research positions. It is not the user's account or a position recommendation.
- Costs use the existing default values: 0.1% commission, 5 yuan minimum commission, 0.1% slippage on each side, and 0.1% sell tax. A versioned identity covers every value.
- Hard vetoes are main-board eligibility, ST/suspension or risk veto, liquidity, point-in-time completeness, and market `FREEZE`. `ALLOW/LIMITED`, sector resonance, anti-chase evidence, and repeated-pivot resistance are soft features only.
- History contains at least 630 strictly increasing signal sessions and uses the existing deterministic 60%/20%/20% split; 630 sessions split to 378/126/126.
- Calibration fallback is exactly profile/setup/market/sector, then profile/setup/market, then profile/setup; each selected unit requires at least 30 triggered resolved samples.
- Validation and test thresholds are strict: positive net expectancy, Profit Factor greater than 1.10, 95% Wilson profitable-rate lower bound at least 45%, stop rate at most 40%, at least 60% positive 63-session windows, and maximum drawdown at most 10%.
- Minimum evidence per profile is train+validation at least 70, validation at least 30, test at least 30, and all segments at least 100 triggered resolved samples.
- Combined Top 3 concentration limits are: one stock at most 10% of trades and 15% of gross profit; one sector at most 35% of trades and 40% of gross profit; top five trades at most 35% of gross profit.
- Test outcomes cannot be read before freeze and each freeze identity can create at most one test artifact. Empty research, freeze, test eligibility, and forward screen are valid; no fallback or candidate padding is allowed.
- No scheduler, notification, holdings, orders, database writes, advisor memory, decision ledger, or formal selector integration is added.
- Generated artifacts remain ignored under `output/research/buy_point_five_day_returns/`.
- Use TDD for every implementation task, commit only scoped files, and preserve unrelated dirty-worktree changes.

---

### Task 1: Freeze the profile matrix, sizing, stops, and repeated-resistance primitive

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_return_profiles.py`
- Modify: `stock_ai/buy_point_selection/resistance_research.py`
- Create: `tests/unit/test_five_day_return_profiles.py`
- Modify: `tests/unit/test_buy_point_resistance_research.py`

**Interfaces:**
- Consumes: `BuyPointBar`, `DetectedSetup`, `SetupType`, `atr14`, `_ceil_cent`, `_floor_cent`, and the existing local-pivot definition.
- Produces: `FiveDayReturnProfile`, `EvaluationSizing`, `EvaluationPosition`, `StopDecision`, `RepeatedResistanceEvidence`, `build_five_day_return_profiles()`, `five_day_profile_hash()`, `evaluation_position()`, `resolve_profile_stop()`, and `repeated_pivot_resistance()`.

- [ ] **Step 1: Write the failing exact-profile and sizing tests**

```python
def test_profile_matrix_and_hash_are_exact() -> None:
    profiles = build_five_day_return_profiles()
    assert tuple(value.profile_id for value in profiles) == (
        "BREAKOUT_TRIGGER__FIXED_3_PERCENT",
        "BREAKOUT_TRIGGER__STRUCTURE_ATR",
        "PULLBACK_RECLAIM__FIXED_3_PERCENT",
        "PULLBACK_RECLAIM__STRUCTURE_ATR",
    )
    assert len(five_day_profile_hash(profiles)) == 64
    with pytest.raises(ValueError, match="profile matrix"):
        validate_five_day_return_profiles(tuple(reversed(profiles)))


@pytest.mark.parametrize(
    ("price", "shares", "notional", "exceeds"),
    (("5", 2000, "10000", False), ("30", 300, "9000", False),
     ("100", 100, "10000", False), ("101", 100, "10100", True)),
)
def test_evaluation_position_targets_ten_thousand_yuan(
    price: str, shares: int, notional: str, exceeds: bool
) -> None:
    value = evaluation_position(Decimal(price))
    assert value.evaluation_target_notional == Decimal("10000")
    assert value.evaluation_shares == shares
    assert value.evaluation_notional == Decimal(notional)
    assert value.minimum_lot_exceeds_target is exceeds
    assert value.executable_shares == 0
```

- [ ] **Step 2: Run the tests to verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_five_day_return_profiles.py
```

Expected: collection fails because `five_day_return_profiles` does not exist.

- [ ] **Step 3: Implement immutable profiles and sizing**

```python
FIVE_DAY_RULE_VERSION = "five-day-return-shadow-1.0.0"
SIZING_VERSION = "target-notional-10000-board-lot-100-v1"

@dataclass(frozen=True)
class FiveDayReturnProfile:
    profile_id: str
    entry_kind: str
    stop_kind: str

@dataclass(frozen=True)
class EvaluationSizing:
    target_notional: Decimal = Decimal("10000")
    board_lot: int = 100
    version: str = SIZING_VERSION

@dataclass(frozen=True)
class EvaluationPosition:
    evaluation_target_notional: Decimal
    evaluation_shares: int
    evaluation_notional: Decimal
    minimum_lot_exceeds_target: bool
    executable_shares: int = 0
```

Hash the compact, sorted-key JSON of the ordered matrix. Reject non-finite or non-positive entry prices. Calculate quantity using `ROUND_FLOOR`; require a positive multiple of 100.

- [ ] **Step 4: Write failing stop-boundary tests**

```python
def test_fixed_stop_is_exactly_three_percent_without_atr() -> None:
    decision = resolve_profile_stop(
        profile=build_five_day_return_profiles()[0],
        entry_price=Decimal("10.11"),
        structure_stop=None,
    )
    assert decision.stop_price == Decimal("9.80")
    assert decision.reasons == ()


@pytest.mark.parametrize(
    ("entry", "stop", "accepted"),
    (("10", "9.85", True), ("10", "9.50", True),
     ("10", "9.86", False), ("10", "9.49", False)),
)
def test_structure_stop_uses_inclusive_one_point_five_to_five_percent(
    entry: str, stop: str, accepted: bool
) -> None:
    decision = resolve_profile_stop(
        profile=build_five_day_return_profiles()[1],
        entry_price=Decimal(entry),
        structure_stop=Decimal(stop),
    )
    assert (decision.stop_price is not None) is accepted
```

- [ ] **Step 5: Implement stop resolution**

```python
@dataclass(frozen=True)
class StopDecision:
    stop_price: Decimal | None
    risk_fraction: Decimal | None
    reasons: tuple[str, ...]

def structure_atr_stop(setup: DetectedSetup, bars: Sequence[BuyPointBar]) -> Decimal | None:
    bounded = tuple(bar for bar in bars if bar.trade_date <= setup.analysis_date)
    volatility = atr14(bounded)
    if not volatility.is_finite() or volatility <= 0:
        return None
    return _floor_cent(setup.structure_low - Decimal("0.2") * volatility)
```

Fixed stop uses the actual slipped entry. Structure stop is frozen from signal-time bars and is accepted only when `Decimal("0.015") <= risk_fraction <= Decimal("0.05")`.

- [ ] **Step 6: Extract and test the reusable repeated-pivot primitive**

```python
@dataclass(frozen=True)
class RepeatedResistanceEvidence:
    complete: bool
    level: Decimal | None
    touch_count: int

def repeated_pivot_resistance(
    reference_price: Decimal,
    signal_date: date,
    bars: Sequence[BuyPointBar],
) -> RepeatedResistanceEvidence:
    bounded = tuple(sorted(
        (value for value in bars if value.trade_date <= signal_date),
        key=lambda value: value.trade_date,
    )[-60:])
    if len(bounded) != 60 or len({value.trade_date for value in bounded}) != 60:
        return RepeatedResistanceEvidence(False, None, 0)
    volatility = atr14(bounded)
    if (not reference_price.is_finite() or reference_price <= 0
            or not volatility.is_finite() or volatility <= 0):
        return RepeatedResistanceEvidence(False, None, 0)
    tolerance = max(Decimal("0.5") * volatility,
                    Decimal("0.005") * reference_price)
    pivots = tuple(value for value in _local_pivots(bounded)
                   if value[2] > reference_price)
    level, touches = _repeated_pivot_cluster(pivots, tolerance)
    return RepeatedResistanceEvidence(True, level, touches)
```

Test exactly 60 signal-time bars, future-bar exclusion through the explicit `signal_date`, two touches at least three sessions apart, tolerance `max(0.5 * ATR14, 0.005 * reference_price)`, no cluster, and incomplete input. Refactor `analyze_significant_resistance()` to call this helper and assert all existing resistance tests remain equivalent at the dataclass boundary.

- [ ] **Step 7: Run Task 1 tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_five_day_return_profiles.py \
  tests/unit/test_buy_point_resistance_research.py \
  tests/unit/test_buy_point_planning.py
```

- [ ] **Step 8: Commit Task 1**

```bash
git add stock_ai/buy_point_selection/five_day_return_profiles.py \
  stock_ai/buy_point_selection/resistance_research.py \
  tests/unit/test_five_day_return_profiles.py \
  tests/unit/test_buy_point_resistance_research.py
git commit -m "feat(stock-ai): define five-day return profiles"
```

**Checkpoint:** Report the passing-test count and the exact profile and sizing hashes. Do not start candidate discovery in this task.

---

### Task 2: Discover point-in-time candidates and expand four zero-share plans

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_return_runtime.py`
- Create: `tests/unit/test_five_day_return_runtime.py`

**Interfaces:**
- Consumes: Task 1 profiles/stops/resistance, production `base_gate`, `anti_chase_gate`, `classify_market`, `sector_gate`, `detect_setups`, point-in-time memberships/risk flags/coverage, and `second_trading_date_after`.
- Produces: `FiveDaySignalCandidate`, `FiveDaySignalPlan`, `FiveDayDiscovery`, `FiveDayRejection`, `discover_five_day_signal_plans()`, and `entry_blockers_by_date()`.

- [ ] **Step 1: Write failing hard-gate versus soft-feature tests**

```python
def test_discovery_keeps_limited_and_weak_sector_as_soft_features() -> None:
    result = discover_five_day_signal_plans(**fixture_inputs(
        market_status="LIMITED", sector_resonating=False, anti_chase_passed=False
    ))
    assert len(result.plans) == 4
    assert {value.candidate.market_status for value in result.plans} == {"LIMITED"}
    assert {value.candidate.sector_resonating for value in result.plans} == {False}
    assert {value.candidate.anti_chase_passed for value in result.plans} == {False}
    assert all(value.executable_shares == 0 for value in result.plans)


@pytest.mark.parametrize(
    "reason",
    ("POINT_IN_TIME_COVERAGE_INCOMPLETE", "POINT_IN_TIME_RISK_VETO",
     "LIQUIDITY_TOO_LOW", "MARKET_FREEZE", "SECTOR_MISSING"),
)
def test_discovery_fails_closed_only_on_approved_hard_gates(reason: str) -> None:
    result = discover_five_day_signal_plans(**fixture_inputs(hard_failure=reason))
    assert result.plans == ()
    assert reason in result.rejection_counts
```

- [ ] **Step 2: Run the discovery tests to verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_five_day_return_runtime.py
```

- [ ] **Step 3: Define immutable candidate and plan contracts**

```python
@dataclass(frozen=True)
class FiveDaySignalCandidate:
    code: str
    signal_date: date
    setup: DetectedSetup
    market_status: str
    sector_code: str
    sector_resonating: bool
    anti_chase_passed: bool
    average_amount5_qian: Decimal
    valid_through_trade_date: date
    executable_shares: int = 0

@dataclass(frozen=True)
class FiveDaySignalPlan:
    candidate: FiveDaySignalCandidate
    profile: FiveDayReturnProfile
    structure_id: str
    signal_close: Decimal
    breakout_trigger: Decimal
    structure_stop: Decimal | None
    reference_entry: Decimal
    resistance_basis: str
    resistance_effective_r: Decimal | None
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"
    executable_shares: int = 0

@dataclass(frozen=True)
class FiveDayDiscovery:
    signal_dates: tuple[date, ...]
    plans: tuple[FiveDaySignalPlan, ...]
    rejection_counts: Mapping[str, int]
    incomplete_dates: tuple[date, ...]

@dataclass(frozen=True)
class FiveDayRejection:
    signal_date: date
    code: str
    profile_id: str | None
    stage: str
    reasons: tuple[str, ...]
```

- [ ] **Step 4: Implement production-order discovery with soft evidence**

For each signal date: validate complete coverage, classify market, reject only `FREEZE`, bound bars through the date, call `base_gate(code, bars, set(), flags, policy)`, detect and choose the maximum `(quality, setup_type.value)`, calculate anti-chase without rejecting it, require point-in-time sector membership and sector snapshot, and store `sector_gate(sector, policy).passed` as a Boolean. Expand every candidate into the exact four profiles.

Use a new structure identity based on code, setup, `FIVE_DAY_RULE_VERSION`, and profile ID so it cannot collide with `TWO_R`:

```python
payload = ":".join((normalize_code6(code), setup.setup_type.value,
                    setup.structure_start.isoformat(), f"{setup.structure_high:.2f}",
                    f"{setup.structure_low:.2f}", FIVE_DAY_RULE_VERSION,
                    profile.profile_id))
identity = hashlib.sha256(payload.encode()).hexdigest()[:32]
```

- [ ] **Step 5: Write and pass expansion and lookahead tests**

Require one setup to produce four stable plans, a future low to leave structure stop unchanged, a future pivot to leave resistance unchanged, and the last bounded bar to equal the signal date. Require an unavailable structure stop to reject only the two structure profiles while fixed-stop profiles remain present.

- [ ] **Step 6: Implement entry-day blockers**

```python
def entry_blockers_by_date(
    code: str,
    entry_dates: Sequence[date],
    *,
    coverage_by_date: Mapping[date, ReferenceCoverage],
    risk_flags: Sequence[RiskFlag],
    market_snapshots: Mapping[date, MarketSnapshot],
) -> dict[date, tuple[str, ...]]:
    result: dict[date, tuple[str, ...]] = {}
    for day in sorted(set(entry_dates)):
        reasons: list[str] = []
        coverage = coverage_by_date.get(day)
        if coverage is None or not coverage.complete:
            reasons.append("POINT_IN_TIME_COVERAGE_INCOMPLETE")
        flags = risk_flags_on(risk_flags, day).get(normalize_code6(code), ())
        if any(value.severity == "VETO" for value in flags):
            reasons.append("POINT_IN_TIME_RISK_VETO")
        snapshot = market_snapshots.get(day, MarketSnapshot(0, 0.0, 0.0, False))
        if classify_market(snapshot).status == "FREEZE":
            reasons.append("MARKET_FREEZE")
        result[day] = tuple(dict.fromkeys(reasons))
    return result
```

Emit blockers for incomplete coverage, risk veto/ST/suspension facts, or market `FREEZE`. `ALLOW` and `LIMITED` emit no blocker. Sort reasons and dates deterministically.

- [ ] **Step 7: Run Task 2 tests and gate regressions**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_buy_point_gates.py \
  tests/unit/test_buy_point_patterns.py
```

- [ ] **Step 8: Commit Task 2**

```bash
git add stock_ai/buy_point_selection/five_day_return_runtime.py \
  tests/unit/test_five_day_return_runtime.py
git commit -m "feat(stock-ai): discover five-day return shadows"
```

**Checkpoint:** Report raw setup count, four-profile expansion count, and hard-gate rejection counts from fixtures. Do not read MySQL yet.

---

### Task 3: Simulate two entry styles, costs, stops, and five holding sessions

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_return_execution.py`
- Create: `tests/unit/test_five_day_return_execution.py`

**Interfaces:**
- Consumes: `FiveDaySignalPlan`, `EvaluationPosition`, `resolve_profile_stop()`, `BuyPointBar`, `ExecutionCosts`, a confirmed trading calendar, and entry blockers.
- Produces: `FiveDayExit`, `FiveDayTrade`, `simulate_five_day_plan()`, `EVALUATOR_VERSION`, and `COST_VERSION`.

- [ ] **Step 1: Write failing entry-path tests**

```python
def test_breakout_uses_open_or_trigger_and_cancels_gap_chase_and_lock() -> None:
    trade = simulate_five_day_plan(plan, breakout_bars(open_="10.02"), calendar)
    assert trade.entry_price == Decimal("10.03002")
    cancelled = simulate_five_day_plan(plan, breakout_bars(open_="10.40"), calendar)
    assert cancelled.status == "CANCELLED"


def test_pullback_reclaim_enters_only_on_confirmed_close() -> None:
    trade = simulate_five_day_plan(
        pullback_plan,
        pullback_bars(low="9.90", high="10.30", close="10.20"),
        calendar,
    )
    assert trade.entry_price == Decimal("10.21020")
    assert trade.entry_date == calendar[1]
```

Add boundary rows for close location `0.60`, immediately below it, close exactly 3% above signal close, immediately above it, no touch, no reclaim, and locked limit-up.

- [ ] **Step 2: Run entry tests to verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_five_day_return_execution.py
```

- [ ] **Step 3: Define exact execution models and versions**

```python
EVALUATOR_VERSION = "five-day-return-evaluator-v1"
COST_VERSION = "execution-costs-default-v1"

@dataclass(frozen=True)
class FiveDayExit:
    planned_exit_date: date
    actual_exit_date: date
    price: Decimal
    reason: str
    fees: Decimal
    delayed: bool

@dataclass(frozen=True)
class FiveDayTrade:
    profile_id: str
    structure_id: str
    code: str
    signal_date: date
    status: str
    entry_date: date | None
    entry_price: Decimal | None
    stop_price: Decimal | None
    evaluation_target_notional: Decimal
    evaluation_shares: int
    evaluation_notional: Decimal
    entry_fees: Decimal
    exit: FiveDayExit | None
    net_pnl: Decimal
    net_return: Decimal | None
    mfe: Decimal | None
    mae: Decimal | None
    intraday_order_ambiguous: bool
    reasons: tuple[str, ...]
    executable_shares: int = 0
```

- [ ] **Step 4: Implement deterministic entry and fee helpers**

Use existing default `ExecutionCosts`. Commission is `max(5, gross * 0.001)`. Entry price is base price times `1.001`; exit price is raw price times `0.999`; sell fees include commission plus `gross * 0.001` tax. A cancelled or untriggered trade has zero evaluation shares and no invented fees.

- [ ] **Step 5: Write failing stop, ambiguity, expiry, and delayed-exit tests**

```python
assert breakout_same_bar_entry_and_stop.status == "STOPPED"
assert breakout_same_bar_entry_and_stop.intraday_order_ambiguous
assert pullback_entry_day_low_below_stop.status == "TIME_EXIT_GAIN"
assert not pullback_entry_day_low_below_stop.intraday_order_ambiguous
assert five_session_trade.exit.actual_exit_date == fifth_holding_session
assert locked_limit_down_exit.exit.delayed
assert insufficient_future_sessions.status == "PENDING"
assert never_triggered.status == "NOT_TRIGGERED"
```

Also test an open below stop exits at slipped open rather than the better stop; a structure stop at 1.49% rejects only that plan; and a 101 yuan entry uses 100 evaluation shares and records the target-notional exception.

- [ ] **Step 6: Implement holding and exit simulation**

Breakout stop monitoring starts on the entry bar and resolves same-bar uncertainty as stop-first. Pullback-reclaim entry occurs at close, so stop monitoring begins on the next confirmed session. Count entry date as holding session 1. On session 5, exit at close unless the bar is absent or locked limit-down; scan later confirmed sessions until a tradable bar exists. Emit only `NOT_TRIGGERED`, `CANCELLED`, `STOPPED`, `TIME_EXIT_GAIN`, `TIME_EXIT_FLAT`, `TIME_EXIT_LOSS`, or `PENDING`. Calculate MFE and MAE only from bars observed after entry through the actual exit. If the supplied cutoff cannot resolve the trade, return `PENDING` without fabricated PnL.

- [ ] **Step 7: Run Task 3 tests and old execution regressions**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_five_day_return_execution.py \
  tests/unit/test_buy_point_execution.py \
  tests/unit/test_buy_point_historical_replay.py
```

- [ ] **Step 8: Commit Task 3**

```bash
git add stock_ai/buy_point_selection/five_day_return_execution.py \
  tests/unit/test_five_day_return_execution.py
git commit -m "feat(stock-ai): simulate five-day return trades"
```

**Checkpoint:** Report the exact status matrix and fee assertions. Do not add calibration or artifacts yet.

---

### Task 4: Build calibrations, frozen ranking, portfolio metrics, and promotion gates

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_return_validation.py`
- Create: `tests/unit/test_five_day_return_validation.py`

**Interfaces:**
- Consumes: `chronological_split()`, `FiveDaySignalPlan`, `FiveDayTrade`, setup/market/sector metadata, and confirmed signal dates.
- Produces: `FiveDayObservation`, `FiveDayCalibration`, `FiveDaySegmentMetrics`, `FiveDayPortfolioMetrics`, `FrozenFiveDayProfile`, `FiveDayFreeze`, `FiveDayTestAssessment`, `build_five_day_calibrations()`, `resolve_five_day_calibration()`, `rank_five_day_plans()`, `evaluate_validation_freeze()`, and `evaluate_frozen_test()`.

- [ ] **Step 1: Write failing chronological and calibration-fallback tests**

```python
def test_split_is_existing_sixty_twenty_twenty_contract() -> None:
    split = chronological_split(trading_dates(630))
    assert (len(split.train), len(split.validation), len(split.test)) == (378, 126, 126)


def test_calibration_falls_back_without_merging_samples() -> None:
    values = build_five_day_calibrations(observations, trading_dates=train_dates)
    resolved = resolve_five_day_calibration(
        values, profile_id=PROFILE, setup_type=SetupType.PRE_BREAKOUT,
        market_status="ALLOW", sector_resonating=True,
    )
    assert resolved.key == f"{PROFILE}|PRE_BREAKOUT|ALLOW|*"
    assert resolved.triggered_resolved == 30
```

The finest fixture has 29 samples, the market fallback has 30, and the broad fallback has 60. Assert the selected count remains 30 rather than 89 or 119.

- [ ] **Step 2: Define observation and calibration contracts**

```python
@dataclass(frozen=True)
class FiveDayObservation:
    plan: FiveDaySignalPlan
    trade: FiveDayTrade
    resolution_date: date

@dataclass(frozen=True)
class FiveDayCalibration:
    key: str
    profile_id: str
    setup_type: SetupType
    market_status: str | None
    sector_resonating: bool | None
    data_end: date
    total_plans: int
    triggered_resolved: int
    positive_net: int
    profitable_rate: Decimal
    profitable_interval: tuple[Decimal, Decimal]
    net_expectancy: Decimal
    profit_factor: Decimal | None
    stop_rate: Decimal
    mae_p75: Decimal
    positive_window_ratio: Decimal

@dataclass(frozen=True)
class FiveDaySegmentMetrics:
    profile_id: str
    segment: str
    triggered_resolved: int
    net_expectancy: Decimal
    profit_factor: Decimal | None
    profitable_wilson_lower: Decimal
    stop_rate: Decimal
    positive_window_ratio: Decimal
    maximum_drawdown: Decimal
    qualifies: bool
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class FiveDayPortfolioMetrics:
    accepted_trades: int
    maximum_drawdown: Decimal
    maximum_stock_trade_share: Decimal
    maximum_stock_profit_share: Decimal
    maximum_sector_trade_share: Decimal
    maximum_sector_profit_share: Decimal
    top5_profit_share: Decimal
    qualifies: bool
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class FrozenFiveDayProfile:
    profile_id: str
    rank: int
    train_validation_samples: int
    validation_metrics: FiveDaySegmentMetrics

@dataclass(frozen=True)
class FiveDayFreeze:
    schema: str
    research_identity: str
    profile_matrix_hash: str
    sizing_version: str
    evaluator_version: str
    cost_version: str
    profiles: tuple[FrozenFiveDayProfile, ...]
    calibrations: Mapping[str, FiveDayCalibration]
    empty: bool
    freeze_hash: str

@dataclass(frozen=True)
class FiveDayTestAssessment:
    profile_metrics: tuple[FiveDaySegmentMetrics, ...]
    portfolio_metrics: FiveDayPortfolioMetrics
    eligible_profile_ids: tuple[str, ...]
    reasons: tuple[str, ...]
```

Cancelled, untriggered, and pending rows remain in `total_plans` but not `triggered_resolved`.

- [ ] **Step 3: Implement exact metrics and Wilson interval**

Use 95% z-score `1.959963984540054`. Profit Factor is gross positive net PnL divided by absolute gross negative net PnL and is `None` when the loss denominator is zero. A 63-session window is positive only when it contains a triggered resolved sample and its mean net return is greater than zero.

- [ ] **Step 4: Write failing ranking tests**

Require the exact key:

```python
key = (
    -calibration.net_expectancy,
    -calibration.profitable_interval[0],
    calibration.mae_p75,
    calibration.stop_rate,
    -market_allow_rank,
    -sector_resonance_rank,
    -resistance_rank,
    -plan.candidate.setup.quality,
    -plan.candidate.average_amount5_qian,
    normalize_code6(plan.candidate.code),
    plan.profile.profile_id,
)
```

Resistance ranks are: at least 2R = 2, no reliable level = 1, below 2R = 0. Test deterministic code/profile ties, one plan per code/active structure, and a maximum of three plans per signal date.

- [ ] **Step 5: Implement frozen ranking without AI inputs**

Resolve a calibration through the exact three-level hierarchy. Missing calibration yields `INSUFFICIENT_CALIBRATION`. Deduplicate the same code/structure to its best profile, exclude supplied active structure IDs, sort by the literal key, and take at most three.

- [ ] **Step 6: Write failing promotion and portfolio-boundary tests**

Parameterize the immediate pass/fail sides of every threshold: expectancy 0, PF 1.10, Wilson lower 0.45, stop rate 0.40, rolling ratio 0.60, drawdown 0.10, validation samples 30, train+validation 70, test samples 30, and total samples 100. Add exact concentration boundaries of 10%/15%, 35%/40%, and 35% top-five profit.

- [ ] **Step 7: Implement the research portfolio**

Accept ranked plans in signal-date/rank order. A plan that actually triggers is admitted only when fewer than three accepted trades remain active on its entry date. Start equity at `Decimal("30000")`, apply net PnL on actual exit dates, and calculate peak-to-trough drawdown. This capacity simulation is only for profile/combined validation; it never changes raw profile evidence or emits executable shares.

- [ ] **Step 8: Implement validation freeze and test assessment**

Profile sample counts and return thresholds use every hard-gate-eligible, triggered, resolved row for that profile; they do not use only Top 3. Validation freeze keeps every profile that independently passes its validation metrics and sample counts, then evaluates the separate combined deterministic Top 3 portfolio. If the combined portfolio fails, freeze is empty; do not search profile subsets. Rebuild frozen calibrations from train+validation only. Test evaluates only frozen profiles, applies test and total sample thresholds, and fails the entire forward eligibility set if the combined test portfolio fails.

- [ ] **Step 9: Run Task 4 tests and existing validation regressions**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_five_day_return_validation.py \
  tests/unit/test_buy_point_validation.py
```

- [ ] **Step 10: Commit Task 4**

```bash
git add stock_ai/buy_point_selection/five_day_return_validation.py \
  tests/unit/test_five_day_return_validation.py
git commit -m "feat(stock-ai): validate five-day return profiles"
```

**Checkpoint:** Report every boundary test, frozen profile IDs from fixtures, and the empty-freeze case.

---

### Task 5: Generate train/validation research and immutable research/freeze artifacts

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_return_runtime.py`
- Create: `stock_ai/buy_point_selection/five_day_return_report.py`
- Modify: `tests/unit/test_five_day_return_runtime.py`
- Create: `tests/unit/test_five_day_return_report.py`

**Interfaces:**
- Consumes: Tasks 1-4, read-only `SQLReferenceRepository`, historical daily-bar/calendar helpers, BaoStock benchmark snapshots, and canonical input fingerprints.
- Produces: `FiveDayRuntimeInputs`, `FiveDayResearchReview`, `load_mysql_five_day_inputs()`, `build_five_day_research_review()`, `five_day_research_payload()`, `write_five_day_research()`, `load_five_day_research()`, `five_day_freeze_payload()`, `write_five_day_freeze()`, and `load_five_day_freeze()`.

- [ ] **Step 1: Write failing data-boundary tests**

Use an injected loader that records requested dates. For a 630-session calendar, assert research requests history through the final validation resolution cutoff but never asks for a test outcome bar. Assert the payload contains split bounds and test signal dates but no test candidates, trades, outcomes, metrics, or calibrations.

```python
assert review.split.train[-1] < review.split.validation[0]
assert review.split.validation[-1] < review.split.test[0]
assert review.test_outcomes_read is False
assert all(row.plan.candidate.signal_date not in set(review.split.test)
           for row in review.observations)
```

- [ ] **Step 2: Implement read-only runtime inputs**

```python
@dataclass(frozen=True)
class FiveDayRuntimeInputs:
    signal_dates: tuple[date, ...]
    trading_dates: tuple[date, ...]
    bars_by_code: Mapping[str, tuple[BuyPointBar, ...]]
    memberships: tuple[SectorMembership, ...]
    risk_flags: tuple[RiskFlag, ...]
    coverage_by_date: Mapping[date, ReferenceCoverage]
    market_snapshots: Mapping[date, MarketSnapshot]
    input_fingerprint: str
```

The MySQL loader reads only. Replace `host.docker.internal` with `127.0.0.1` exactly as the existing replay runtime does, honor the configured LAN `MYSQL_URL`, and never create or update tables. Load at least 180 calendar days of signal-time history and enough post-validation sessions to resolve a second-day entry held for five sessions plus delayed exits.

- [ ] **Step 3: Implement the research review flow**

```python
@dataclass(frozen=True)
class FiveDayResearchReview:
    split: ChronologicalSplit
    input_fingerprint: str
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    sizing_version: str
    evaluator_version: str
    cost_version: str
    observations: tuple[FiveDayObservation, ...]
    train_calibrations: Mapping[str, FiveDayCalibration]
    validation_metrics: tuple[FiveDaySegmentMetrics, ...]
    validation_portfolio: FiveDayPortfolioMetrics
    point_in_time_complete: bool
    test_outcomes_read: bool = False
```

Discover and simulate all four profiles for train and validation. Build calibrations from train only, use them to rank validation Top 3, compute validation metrics, and retain all raw rows needed for independent recomputation. Do not call test input loaders.

- [ ] **Step 4: Write failing immutable research payload tests**

Require schema/stage/safety labels, profile/sizing/evaluator/cost versions, all split bounds, input fingerprint, canonical raw rows, recursive zero shares, and recomputed summaries. Tamper with one net return, profile ID, split date, or share field and require the loader to reject it.

- [ ] **Step 5: Implement research identity and exclusive writer**

Use sorted-key compact JSON for identities and indented sorted JSON for files. Identity includes schema, stage, all split dates, input fingerprint, formal rule/policy hashes, profile matrix hash, sizing/evaluator/cost versions, and normalized content revision. Use exclusive create; identical content verifies byte equality, while different content at an existing path raises `immutable artifact content mismatch`.

- [ ] **Step 6: Write and implement freeze artifact tests**

Freeze loader must recompute every validation metric and calibration from research raw rows, verify that no test outcome exists, call `evaluate_validation_freeze()`, and allow an empty profile list. Freeze identity includes the parent research identity and frozen calibration content. Tampered metrics, sample counts, rank order, versions, parent identity, or nonzero shares fail closed.

- [ ] **Step 7: Run Task 5 tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py \
  tests/unit/test_generate_buy_point_observations_cli.py
```

- [ ] **Step 8: Commit Task 5**

```bash
git add stock_ai/buy_point_selection/five_day_return_runtime.py \
  stock_ai/buy_point_selection/five_day_return_report.py \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py
git commit -m "feat(stock-ai): freeze five-day return research"
```

**Checkpoint:** Report research identity, split sizes, train/validation row counts, and prove the research artifact contains no test outcomes.

---

### Task 6: Execute the one-shot frozen test and derive forward eligibility

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_return_runtime.py`
- Modify: `stock_ai/buy_point_selection/five_day_return_report.py`
- Modify: `tests/unit/test_five_day_return_runtime.py`
- Modify: `tests/unit/test_five_day_return_report.py`

**Interfaces:**
- Consumes: a validated `FiveDayFreeze`, its parent research artifact, and read-only inputs restricted to the frozen test dates and their outcome horizon.
- Produces: `FiveDayTestReview`, `build_five_day_test_review()`, `five_day_test_payload()`, `write_five_day_test_once()`, and `load_five_day_test()`.

- [ ] **Step 1: Write failing freeze-before-test and date-membership tests**

```python
def test_test_builder_requires_exact_frozen_test_dates() -> None:
    review = build_five_day_test_review(freeze, research, inputs)
    assert review.signal_dates == research.split.test
    assert review.freeze_hash == freeze.freeze_hash
    assert set(value.plan.profile.profile_id for value in review.observations) \
        <= set(value.profile_id for value in freeze.profiles)
```

Reject a missing freeze, mismatched parent research identity, changed split, extra date, missing date, or any input fingerprint whose signal-time prefix conflicts with the research artifact.

Define the review before implementing the builder:

```python
@dataclass(frozen=True)
class FiveDayTestReview:
    signal_dates: tuple[date, ...]
    research_identity: str
    freeze_hash: str
    input_fingerprint: str
    observations: tuple[FiveDayObservation, ...]
    assessment: FiveDayTestAssessment
    sizing_version: str
    evaluator_version: str
    cost_version: str
```

- [ ] **Step 2: Implement test execution using frozen calibrations only**

Discover candidates under the unchanged matrix, keep only frozen profile IDs, rank every test date using the calibrations serialized before test, simulate outcomes, and call `evaluate_frozen_test()`. Do not rebuild ranking calibrations from test rows and do not change profile order after seeing results.

- [ ] **Step 3: Write failing one-shot and tamper tests**

```python
write_five_day_test_once(review, output_dir)
with pytest.raises(ValueError, match="test already exists"):
    write_five_day_test_once(review, output_dir)
```

The second call fails even for identical content. Also reject changed freeze hash, raw outcome, summary, eligibility list, cost/sizing version, recursive nonzero share, or a test artifact whose parent freeze/research lineage is not already valid.

- [ ] **Step 4: Implement the immutable test payload**

Store all test raw rows, profile metrics, combined portfolio metrics, every explicit failure reason, and `forward_eligible_profile_ids`. Empty eligibility is valid. Before evaluating or writing, scan the output directory for any test artifact bearing the same freeze hash and reject a second attempt.

- [ ] **Step 5: Run Task 6 tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py
```

- [ ] **Step 6: Commit Task 6**

```bash
git add stock_ai/buy_point_selection/five_day_return_runtime.py \
  stock_ai/buy_point_selection/five_day_return_report.py \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py
git commit -m "feat(stock-ai): test frozen five-day profiles"
```

**Checkpoint:** Report the single test identity and eligible profile IDs. Do not run the real historical test dataset during code implementation unless the user explicitly starts that irreversible one-shot stage.

---

### Task 7: Add immutable forward screen and separate settlement

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_return_runtime.py`
- Modify: `stock_ai/buy_point_selection/five_day_return_report.py`
- Modify: `tests/unit/test_five_day_return_runtime.py`
- Modify: `tests/unit/test_five_day_return_report.py`

**Interfaces:**
- Consumes: validated freeze and test artifacts, one completed forward signal date, its bounded point-in-time inputs, and later settlement bars.
- Produces: `FiveDayForwardScreen`, `FiveDayForwardSettlement`, `build_five_day_forward_screen()`, `build_five_day_forward_settlement()`, strict payload/load/write functions, and immutable parent membership.

Use these exact artifact models:

```python
@dataclass(frozen=True)
class FiveDayForwardScreen:
    signal_date: date
    freeze_hash: str
    test_identity: str
    input_fingerprint: str
    candidates: tuple[FiveDaySignalPlan, ...]
    risk_coverage_complete: bool

@dataclass(frozen=True)
class FiveDayForwardSettlement:
    parent_screen_identity: str
    signal_date: date
    outcome_cutoff: date
    freeze_hash: str
    test_identity: str
    input_fingerprint: str
    candidates: tuple[FiveDaySignalPlan, ...]
    outcomes: tuple[FiveDayObservation, ...]
    risk_coverage_complete: bool
```

- [ ] **Step 1: Write failing forward-screen tests**

Require the signal date to be strictly after the frozen test end and confirmed complete. Only `forward_eligible_profile_ids` may screen. Require at most three candidates, one code/structure, frozen ranking, no entry/outcome/exit/net-return fields, and recursive zero shares.

```python
payload = five_day_forward_screen_payload(screen)
assert payload["stage"] == "forward-screen"
assert payload["candidates"] == sorted(payload["candidates"], key=screen_rank_key)
assert "outcomes" not in payload
assert all(value["executable_shares"] == 0 for value in payload["candidates"])
```

- [ ] **Step 2: Implement forward screen identity and writer**

Identity includes freeze hash, test identity, signal date, input fingerprint, all versions, and exact candidate membership. Empty screens are valid. An identical screen rerun verifies bytes; changed content creates a different content revision without overwriting the old screen.

- [ ] **Step 3: Write failing settlement-horizon and membership tests**

For an entry on the second valid date, require enough calendar data to include that entry plus four later holding sessions. Reject settlement before every candidate is terminal. Require exact `(signal_date, code, structure_id, profile_id)` membership equality with the screen and forbid added, missing, or reordered members.

- [ ] **Step 4: Implement separate settlement**

Load the original screen without modifying it, reconstruct its plans, simulate only its members through the supplied cutoff, and write a new `forward-settlement` artifact. Preserve screen identity, freeze hash, test identity, signal date, candidate order, entry blockers, fees, actual delayed exits, and recursive zero shares.

- [ ] **Step 5: Prove settlement never rewrites the screen**

Read and hash the screen bytes before settlement, write settlement, and assert the screen hash is unchanged. Tampering with either artifact or settling twice with different content must fail closed.

- [ ] **Step 6: Run Task 7 tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py \
  tests/unit/test_buy_point_structure_stop_report.py
```

- [ ] **Step 7: Commit Task 7**

```bash
git add stock_ai/buy_point_selection/five_day_return_runtime.py \
  stock_ai/buy_point_selection/five_day_return_report.py \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py
git commit -m "feat(stock-ai): observe five-day profiles forward"
```

**Checkpoint:** Report the empty-screen path, maximum-three path, second-day-entry settlement horizon, and byte-preservation assertion.

---

### Task 8: Add the manual CLI, documentation, and full isolation regression

**Files:**
- Create: `scripts/analysis/research_five_day_return_shadow.py`
- Create: `tests/unit/test_research_five_day_return_shadow_cli.py`
- Modify: `docs/CAPABILITIES.md`
- Modify: `docs/PROJECT_LAYOUT.md`

**Interfaces:**
- Consumes: all Tasks 1-7 builders/loaders/writers and injected read-only runtime loaders.
- Produces: `RuntimeInputLoader`, `build_parser()`, `dispatch_stage()`, and manual `research`, `freeze`, `test`, `forward-screen`, and `forward-settlement` commands with exit code 2 on validation failures.

- [ ] **Step 1: Write failing parser and safety tests**

Require these exact subcommands and required arguments:

```text
research --signal-start YYYY-MM-DD --signal-end YYYY-MM-DD
freeze --research-artifact PATH
test --freeze-artifact PATH --research-artifact PATH
forward-screen --signal-date YYYY-MM-DD --freeze-artifact PATH --test-artifact PATH
forward-settlement --screen-artifact PATH --outcome-cutoff YYYY-MM-DD
```

All commands accept `--output-dir`, defaulting to `output/research/buy_point_five_day_returns`. Assert no parser option can install a schedule, send a notification, set executable shares, write holdings, or bypass a failed gate.

- [ ] **Step 2: Run parser tests to verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_research_five_day_return_shadow_cli.py
```

- [ ] **Step 3: Implement a thin injectable CLI**

```python
RuntimeInputLoader = Callable[[date, date, date], FiveDayRuntimeInputs]

def main(
    argv: Sequence[str] | None = None,
    *,
    research_input_loader: RuntimeInputLoader = load_mysql_five_day_inputs,
    test_input_loader: RuntimeInputLoader = load_mysql_five_day_inputs,
    forward_input_loader: RuntimeInputLoader = load_mysql_five_day_inputs,
) -> int:
    try:
        args = build_parser().parse_args(argv)
        paths = dispatch_stage(
            args, research_input_loader, test_input_loader, forward_input_loader
        )
    except (RuntimeError, ValueError) as exc:
        print(f"五日净收益影子研究失败：{exc}", file=sys.stderr)
        return 2
    print("\n".join(str(path) for path in paths))
    return 0
```

`build_parser()` creates only the five declared subcommands. `dispatch_stage()` maps each subcommand directly to its Task 5-7 builder and writer, returning the written JSON/Markdown paths. The CLI delegates calculations to pure/runtime modules and only prints artifact paths. It does not catch unexpected programming errors.

- [ ] **Step 4: Write end-to-end injected CLI tests**

Run all five stages against deterministic in-memory inputs and a temporary output directory. Prove empty freeze and empty forward screen return 0, malformed lineage returns 2 with a concise Chinese error, a repeated test returns 2 without changing bytes, and settlement writes a second file without changing its screen.

- [ ] **Step 5: Document the capability and irreversible test gate**

Add a manual section to `docs/CAPABILITIES.md` and an entry to `docs/PROJECT_LAYOUT.md`. Include command examples, four profiles, 1 万元 target-notional sizing, 630-session split, zero-share/no-trade status, old `TWO_R` isolation, no scheduling, and this warning immediately above the real test command:

```text
同一 freeze identity 的 test 只能执行一次。代码验收不得顺手运行真实测试段；只有用户明确确认开始冻结测试时才执行。
```

- [ ] **Step 6: Run focused feature tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_five_day_return_profiles.py \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_execution.py \
  tests/unit/test_five_day_return_validation.py \
  tests/unit/test_five_day_return_report.py \
  tests/unit/test_research_five_day_return_shadow_cli.py
```

- [ ] **Step 7: Run the complete buy-point regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point*.py \
  tests/unit/test_review_buy_point*.py \
  tests/unit/test_generate_buy_point_observations_cli.py \
  tests/unit/test_backtest_buy_point_selection_cli.py
```

Expected: zero failures, including every old `TWO_R`, case-revision, threshold, gate, resistance, and structure-stop test.

- [ ] **Step 8: Verify scope and forbidden writes**

```bash
git diff --check
git status --short
rg -n "send_to_lark|notify|schedule|advisor_memory|portfolio_positions|INSERT|UPDATE|DELETE" \
  stock_ai/buy_point_selection/five_day_return_*.py \
  scripts/analysis/research_five_day_return_shadow.py
```

Review every match. Imports or calls that can notify, schedule, mutate holdings/memory, or write SQL are forbidden. SQL `SELECT` and read-only repository calls are allowed.

- [ ] **Step 9: Commit Task 8**

```bash
git add scripts/analysis/research_five_day_return_shadow.py \
  tests/unit/test_research_five_day_return_shadow_cli.py \
  docs/CAPABILITIES.md docs/PROJECT_LAYOUT.md
git commit -m "feat(stock-ai): expose five-day return research"
```

**Final checkpoint:** Report focused and full regression counts, changed files, the five manual commands, and confirm that no real one-shot test artifact, schedule, notification, holding, order, or advisor-memory mutation was created.

---

## Execution Order and Stop Conditions

Execute Tasks 1 through 8 in order. Stop after every checkpoint for review, matching the user's requirement to proceed step by step instead of running the full implementation at once.

Do not proceed past a task when its focused tests fail, when an old `TWO_R` regression changes, when an unplanned file is modified, or when any artifact contains nonzero executable shares. Do not run a real `test` stage during implementation verification; injected fixtures prove the one-shot mechanism without consuming the historical test identity.
