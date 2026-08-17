# Hierarchical Confidence Ranking V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated, point-in-time V3 five-day ranking experiment that uses hierarchical confidence evidence, selects zero to three plans, and fails closed unless one policy meets the unchanged formal train thresholds.

**Architecture:** Add focused evidence and feature modules, then compose them in a separate V3 ranking runtime. Persist immutable aggregate train and validation evidence through a strict report module and expose only two manual CLI stages. V1, V2, discovery, execution profiles, settlement, and production selection remain unchanged.

**Tech Stack:** Python 3.11+, frozen dataclasses, `Decimal`, standard-library hashing/JSON, pytest, existing `stock_ai.buy_point_selection` domain models.

**Approved Design:** `docs/superpowers/specs/2026-08-17-hierarchical-confidence-ranking-v3-design.md`

## Global Constraints

- Use only fields already present in the canonical parent research artifact.
- Preserve all four execution profiles, entries, stops, five-session exits, costs, structure de-duplication, capacity three, and no-backfill behavior.
- Keep V1 and V2 source, registries, hashes, commands, and artifact identities unchanged.
- Use exact V3 identities: ranking `five-day-ranking-key-v3`, train schema `five-day-ranking-v3-train-v1`, validation schema `five-day-ranking-v3-validation-v1`, formula `hierarchical-confidence-edge-v1`, features `common-point-in-time-features-v1`, and selection `absolute-edge-boundary-margin-v1`.
- Use the exact 378/126/126 split and train folds 252/63 and 315/63.
- Exclude any calibration observation resolving on or after the first evaluation session.
- The recent evidence window is the last 126 calibration sessions.
- Register exactly eight policies: `EDGE-K30`, `EDGE-K60`, `CONSISTENCY-K30`, `CONSISTENCY-K60`, `STRUCTURE-K30`, `STRUCTURE-K60`, `DOWNSIDE-K30`, `DOWNSIDE-K60`.
- Clip each feature effect to `[-0.001, +0.001]` and the combined feature adjustment to `[-0.003, +0.003]`.
- Require score at least `0.001` and selection-boundary margin at least `0.001`.
- Require at least four distinct train-fold selection fingerprints across the eight policies.
- Train qualification remains: each fold at least 15 completed admitted trades and positive net expectancy; combined at least 40 trades, net expectancy at least `0.003`, Profit Factor above `1.10`, and qualifying rank monotonicity.
- No unqualified winner fallback; no validation read without one verified train winner.
- No database, network, schedule, notification, order, holding, or personal-memory side effect.
- Generated research artifacts remain ignored and must never be staged.
- Use TDD for every production change and run the most relevant regression tests after each task.
- Do not touch the user's existing `tests/unit/test_buy_point_reference_cninfo.py` modification.

## File Structure

| File | Responsibility |
| --- | --- |
| `stock_ai/buy_point_selection/five_day_ranking_v3_evidence.py` | Hierarchy keys, bucket summaries, full/recent windows, recursive pooling, stable-negative gate |
| `stock_ai/buy_point_selection/five_day_ranking_v3_features.py` | Common point-in-time features, frozen quintile models, signed feature effects and caps |
| `stock_ai/buy_point_selection/five_day_ranking_v3.py` | Policy registry, score, zero-to-three ranking, folds, diversity, qualification, winner, validation review |
| `stock_ai/buy_point_selection/five_day_ranking_v3_report.py` | Canonical immutable train/validation payloads, writers, strict loaders |
| `scripts/analysis/analyze_five_day_ranking_v3.py` | Separate manual `diagnose-train` and `validate-ranking` CLI |
| `tests/unit/five_day_ranking_v3_fixtures.py` | Shared complete plan, observation, and 378/126/126 research fixtures |
| `tests/unit/test_five_day_ranking_v3_evidence.py` | Hierarchy, windows, shrinkage, and negative-gate tests |
| `tests/unit/test_five_day_ranking_v3_features.py` | Feature derivation, bins, sign agreement, and clipping tests |
| `tests/unit/test_five_day_ranking_v3.py` | Registry, score, selection, fold evaluation, qualification, and validation tests |
| `tests/unit/test_five_day_ranking_v3_report.py` | Identity, canonicalization, idempotency, tamper, and lineage tests |
| `tests/unit/test_analyze_five_day_ranking_v3_cli.py` | Exact command surface, dispatch ordering, reuse, and sanitized errors |

The new modules may import stable V1/V2-neutral primitives such as `FiveDayObservation`, `FiveDaySelection`, `admit_five_day_ranking`, `evaluate_five_day_selection_segment`, `_is_resolved`, and `v2_fold_specs`. They must not edit V1 or V2 modules.

## Test Helper Contracts

Every underscore-prefixed helper used below is local to its named test module and must be added in the same RED step:

- Evidence tests: `_evidence_windows` creates explicit PROFILE/SETUP/MARKET/SECTOR full and recent `V3BucketStats`; `_negative_windows` and `_stable_negative_windows` set the exact sample, edge, Profit Factor, and Wilson values passed by keyword.
- Feature tests: `_feature_model` creates one profile/setup feature bin with supplied full/recent deltas; `_seven_positive_feature_model` creates all seven sufficiently sampled same-sign bins.
- Ranking tests: `_candidate_evidence` and `_feature_adjustment` construct complete frozen dataclasses from supplied Decimal strings; `_selected_count` ranks synthetic plans with the supplied ordered scores; `_rank_with_duplicate_profiles` uses two profiles sharing one active structure; `_rank_one` returns one synthetic gate result; `_selection_with_cancelled_first_and_ranked_fourth` passes a three-plan V3 ranking plus four observations through the real `admit_five_day_ranking` and returns the selection and fourth structure ID.
- Train tests: `_complete_research_with_boundary_resolution` uses `make_v3_research_review` and places one calibration resolution exactly on each fold boundary; `_segment` returns a complete `FiveDaySelectedSegment`; `_qualifying_monotonicity` returns four 15-sample monotonic bands; `_train_review_with_fingerprints` returns all eight complete policy assessments and supplied fingerprints.
- Report tests: `_complete_v3_train_review` constructs all eight policies, 72 variants, fold models, assessments, fingerprints, and safety flags; `_nested_keys` recursively yields mapping keys.
- Validation tests: `_train_artifact(winner=...)` constructs the strict artifact dataclass from a canonical Task 7 payload; `_complete_v3_validation_review` contains a complete validation segment and frozen winner lineage.
- CLI tests: `_research_review` uses the 630-session shared fixture; `_no_winner` and `_winner_train_artifact` come from strict report payloads; `_write_existing_validation` calls the real V3 writer; `_diagnose_argv` and `_validate_argv` return complete argument tuples; `_option_strings` recursively visits parser actions.

Helpers must use real production dataclasses and canonical hash/payload functions. Monkeypatching is limited to imported builder/loader functions in CLI ordering tests; hashes, writers, loaders, and metric calculations are never mocked.

---

### Task 1: Build Hierarchy Buckets and Frozen Evidence Windows

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3_evidence.py`
- Create: `tests/unit/five_day_ranking_v3_fixtures.py`
- Create: `tests/unit/test_five_day_ranking_v3_evidence.py`

**Interfaces:**
- Consumes: `FiveDayObservation`, `FiveDaySignalPlan`, `SetupType`, calibration trading dates.
- Produces: `V3BucketKey`, `V3BucketStats`, `V3EvidenceWindows`, and `build_v3_evidence_windows(observations, *, trading_dates)`.

- [ ] **Step 1: Create complete shared fixtures**

Create the fixture module with these exact builders and defaults:

```python
from datetime import date, timedelta
from decimal import Decimal

from stock_ai.buy_point_selection.five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
    FiveDayExit,
    FiveDayTrade,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    SIZING_VERSION,
    build_five_day_return_profiles,
    evaluation_position,
    five_day_profile_hash,
    resolve_profile_stop,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayResearchReview,
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayObservation,
    FiveDayPortfolioMetrics,
)
from stock_ai.buy_point_selection.models import (
    DetectedSetup,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.validation import (
    ChronologicalSplit,
    policy_hash,
)


def weekday_dates(count: int, start: date = date(2023, 1, 2)) -> tuple[date, ...]:
    values: list[date] = []
    current = start
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def make_v3_plan(
    signal_date: date,
    *,
    code: str = "600001",
    profile_id: str = "BREAKOUT_TRIGGER__STRUCTURE_ATR",
    setup_type: SetupType = SetupType.TREND_PULLBACK,
    market_status: str = "ALLOW",
    sector_resonating: bool = True,
    setup_quality: Decimal = Decimal("0.60"),
    structure_start: date | None = None,
    structure_high: Decimal = Decimal("11"),
    structure_low: Decimal = Decimal("9"),
    signal_close: Decimal = Decimal("10"),
    breakout_trigger: Decimal = Decimal("10.10"),
    structure_stop: Decimal = Decimal("9.70"),
    resistance_effective_r: Decimal | None = Decimal("2"),
    average_amount5_qian: Decimal = Decimal("200000"),
) -> FiveDaySignalPlan:
    profile = next(
        value for value in build_five_day_return_profiles()
        if value.profile_id == profile_id
    )
    setup = DetectedSetup(
        code=code,
        setup_type=setup_type,
        analysis_date=signal_date,
        structure_start=structure_start or signal_date - timedelta(days=10),
        structure_high=structure_high,
        structure_low=structure_low,
        quality=setup_quality,
        reasons=(),
        metrics={},
    )
    candidate = FiveDaySignalCandidate(
        code=code,
        signal_date=signal_date,
        setup=setup,
        market_status=market_status,
        sector_code="TEST",
        sector_resonating=sector_resonating,
        anti_chase_passed=True,
        average_amount5_qian=average_amount5_qian,
        valid_through_trade_date=signal_date + timedelta(days=7),
    )
    resistance_basis = (
        "NO_RELIABLE_LEVEL"
        if resistance_effective_r is None
        else "LEVEL_AT_OR_ABOVE_2R"
        if resistance_effective_r >= Decimal("2")
        else "LEVEL_BELOW_2R"
    )
    return FiveDaySignalPlan(
        candidate=candidate,
        profile=profile,
        structure_id=(
            f"{code}-{setup_type.value}-{signal_date.isoformat()}-{profile_id}"
        ),
        signal_close=signal_close,
        breakout_trigger=breakout_trigger,
        structure_stop=structure_stop,
        reference_entry=(
            breakout_trigger
            if profile.entry_kind == "BREAKOUT_TRIGGER"
            else signal_close
        ),
        resistance_basis=resistance_basis,
        resistance_effective_r=resistance_effective_r,
    )

def make_v3_observation(
    plan: FiveDaySignalPlan,
    *,
    net_return: Decimal = Decimal("0.01"),
    net_pnl: Decimal = Decimal("100"),
    status: str = "TIME_EXIT_GAIN",
    mae: Decimal = Decimal("0.02"),
    resolution_date: date | None = None,
) -> FiveDayObservation:
    resolved_on = resolution_date or plan.candidate.signal_date + timedelta(days=7)
    stop = resolve_profile_stop(
        plan.profile, plan.reference_entry, plan.structure_stop
    )
    assert stop.stop_price is not None
    position = evaluation_position(plan.reference_entry)
    exit_value = FiveDayExit(
        planned_exit_date=resolved_on,
        actual_exit_date=resolved_on,
        price=plan.reference_entry * (Decimal("1") + net_return),
        reason=status,
        fees=Decimal("0"),
        delayed=False,
    )
    trade = FiveDayTrade(
        profile_id=plan.profile.profile_id,
        structure_id=plan.structure_id,
        code=plan.candidate.code,
        signal_date=plan.candidate.signal_date,
        status=status,
        entry_date=plan.candidate.signal_date + timedelta(days=1),
        entry_price=plan.reference_entry,
        stop_price=stop.stop_price,
        evaluation_target_notional=position.evaluation_target_notional,
        evaluation_shares=position.evaluation_shares,
        evaluation_notional=position.evaluation_notional,
        entry_fees=Decimal("0"),
        exit=exit_value,
        net_pnl=net_pnl,
        net_return=net_return,
        mfe=max(net_return, Decimal("0")),
        mae=mae,
        intraday_order_ambiguous=False,
        reasons=(),
    )
    return FiveDayObservation(
        plan=plan, trade=trade, resolution_date=resolved_on
    )

def make_v3_research_review(
    observations: tuple[FiveDayObservation, ...],
) -> FiveDayResearchReview:
    sessions = weekday_dates(630)
    policy = SelectionPolicy()
    empty_portfolio = FiveDayPortfolioMetrics(
        accepted_trades=0,
        maximum_drawdown=Decimal("0"),
        maximum_stock_trade_share=Decimal("0"),
        maximum_stock_profit_share=Decimal("0"),
        maximum_sector_trade_share=Decimal("0"),
        maximum_sector_profit_share=Decimal("0"),
        top5_profit_share=Decimal("0"),
        qualifies=False,
        reasons=("NO_ACCEPTED_TRADES",),
    )
    return FiveDayResearchReview(
        split=ChronologicalSplit(
            train=sessions[:378],
            validation=sessions[378:504],
            test=sessions[504:630],
        ),
        input_fingerprint="f" * 64,
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
        sizing_version=SIZING_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        cost_version=COST_VERSION,
        observations=observations,
        train_calibrations={},
        validation_metrics=(),
        validation_portfolio=empty_portfolio,
        point_in_time_complete=True,
        test_outcomes_read=False,
    )
```

`make_v3_plan` must resolve the named profile from `build_five_day_return_profiles()`, create a complete `DetectedSetup` and `FiveDaySignalCandidate`, and keep `trade_permission="NO-TRADE"`. `make_v3_observation` must create a complete resolved `FiveDayTrade` and `FiveDayExit`. `make_v3_research_review` must construct exactly 630 weekday sessions split 378/126/126 and set `point_in_time_complete=True`, `test_outcomes_read=False`.

- [ ] **Step 2: Write failing bucket and window tests**

```python
def test_v3_builds_four_profile_isolated_hierarchy_levels() -> None:
    dates = weekday_dates(140)
    first = make_v3_observation(make_v3_plan(dates[5]))
    second = make_v3_observation(
        make_v3_plan(
            dates[6],
            profile_id="PULLBACK_RECLAIM__FIXED_3_PERCENT",
        )
    )
    windows = build_v3_evidence_windows(
        (first, second), trading_dates=dates
    )

    assert {key.level for key in windows.full} == {
        "PROFILE", "SETUP", "MARKET", "SECTOR"
    }
    assert all(
        value.key.profile_id == key.profile_id
        for key, value in windows.full.items()
    )
    assert len({key.profile_id for key in windows.full}) == 2


def test_v3_recent_window_uses_last_126_sessions_only() -> None:
    dates = weekday_dates(252)
    old = make_v3_observation(make_v3_plan(dates[10]))
    recent = make_v3_observation(make_v3_plan(dates[-10]))
    windows = build_v3_evidence_windows(
        (old, recent), trading_dates=dates
    )

    assert windows.full_dates == tuple(dates)
    assert windows.recent_dates == tuple(dates[-126:])
    assert sum(value.resolved_samples for value in windows.recent.values()
               if value.key.level == "PROFILE") == 1
```

- [ ] **Step 3: Run the tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_evidence.py -q
```

Expected: import failure for `five_day_ranking_v3_evidence`.

- [ ] **Step 4: Implement bucket summaries and windows**

Add frozen types and builders:

```python
@dataclass(frozen=True, order=True)
class V3BucketKey:
    level: str
    profile_id: str
    setup_type: SetupType | None = None
    market_status: str | None = None
    sector_resonating: bool | None = None


@dataclass(frozen=True)
class V3BucketStats:
    key: V3BucketKey
    data_end: date
    total_plans: int
    resolved_samples: int
    net_expectancy: Decimal
    profit_factor: Decimal | None
    profitable_interval: tuple[Decimal, Decimal]
    positive_window_ratio: Decimal
    mae_p75: Decimal
    stop_rate: Decimal


@dataclass(frozen=True)
class V3EvidenceWindows:
    full_dates: tuple[date, ...]
    recent_dates: tuple[date, ...]
    full: Mapping[V3BucketKey, V3BucketStats]
    recent: Mapping[V3BucketKey, V3BucketStats]
```

Implement `build_v3_evidence_windows(observations: Sequence[FiveDayObservation], *, trading_dates: Sequence[date]) -> V3EvidenceWindows`. Build PROFILE, SETUP, MARKET, and SECTOR keys for every observation. Summaries must use only `_is_resolved(value)` with `resolution_date <= data_end`, exact Decimal averages, the existing Wilson formula, Profit Factor semantics, MAE p75, stop rate, and positive 63-session windows. Reject empty or duplicate trading dates.

- [ ] **Step 5: Run Task 1 tests and relevant calibration regression**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_evidence.py \
  tests/unit/test_five_day_return_validation.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_evidence.py \
  tests/unit/five_day_ranking_v3_fixtures.py \
  tests/unit/test_five_day_ranking_v3_evidence.py
git diff --cached --check
git commit -m "feat(stock-ai): build v3 ranking evidence"
```

---

### Task 2: Resolve Recursive Evidence and Stable-Negative Gate

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_evidence.py`
- Modify: `tests/unit/test_five_day_ranking_v3_evidence.py`

**Interfaces:**
- Consumes: `V3EvidenceWindows`, `FiveDaySignalPlan`, `k in {30, 60}`.
- Produces: `V3CandidateEvidence`, `resolve_v3_candidate_evidence(plan, windows, *, shrinkage_k)`, and `v3_stable_negative(full_path, recent_path, *, shrinkage_k)`.

- [ ] **Step 1: Write failing recursive-pooling tests**

```python
def test_v3_child_edge_recursively_shrinks_to_parent() -> None:
    windows = _evidence_windows(
        profile=(100, "0.01"),
        setup=(30, "-0.01"),
        market=(0, "0"),
        sector=(0, "0"),
    )
    result = resolve_v3_candidate_evidence(
        make_v3_plan(START), windows, shrinkage_k=30
    )

    root_edge = (
        Decimal("100") / Decimal("130") * Decimal("0.01")
    )
    expected = (
        Decimal("30") / Decimal("60") * Decimal("-0.01")
        + Decimal("30") / Decimal("60") * root_edge
    )
    assert result.full_edge == expected
    assert result.edge == expected
    assert result.deepest_full_key.level == "SETUP"


@pytest.mark.parametrize("shrinkage_k", (30, 60))
def test_v3_missing_child_inherits_profile_root(shrinkage_k: int) -> None:
    windows = _evidence_windows(
        profile=(100, "0.01"),
        setup=(0, "0"),
        market=(0, "0"),
        sector=(0, "0"),
    )
    result = resolve_v3_candidate_evidence(
        make_v3_plan(START), windows, shrinkage_k=shrinkage_k
    )
    expected = (
        Decimal("100") / Decimal(100 + shrinkage_k) * Decimal("0.01")
    )
    assert result.full_edge == expected
    assert result.deepest_full_key.level == "PROFILE"


def test_v3_rejects_calibration_ending_on_signal_date() -> None:
    windows = _evidence_windows(
        profile=(100, "0.01"), data_end=START
    )
    with pytest.raises(V3EvidenceRejected, match="CALIBRATION_NOT_POINT_IN_TIME"):
        resolve_v3_candidate_evidence(
            make_v3_plan(START), windows, shrinkage_k=30
        )


def test_v3_profile_root_alone_cannot_trigger_stable_negative() -> None:
    windows = _negative_windows(profile_samples=100, child_samples=0)
    result = resolve_v3_candidate_evidence(
        make_v3_plan(START), windows, shrinkage_k=30
    )
    assert result.stable_negative is False


def test_v3_stable_negative_requires_parent_child_and_all_boundaries() -> None:
    windows = _stable_negative_windows(
        full_samples=60,
        recent_samples=30,
        full_edge="0",
        recent_edge="0",
        profit_factor="1",
        wilson_upper="0.4999",
    )
    result = resolve_v3_candidate_evidence(
        make_v3_plan(START), windows, shrinkage_k=60
    )
    assert result.stable_negative is True


@pytest.mark.parametrize(
    ("override", "value"),
    (
        ("full_samples", 59),
        ("recent_samples", 29),
        ("full_edge", "0.0001"),
        ("recent_edge", "0.0001"),
        ("profit_factor", "1.0001"),
        ("wilson_upper", "0.50"),
    ),
)
def test_v3_stable_negative_boundaries_fail_open(
    override: str, value: object
) -> None:
    inputs: dict[str, object] = {
        "full_samples": 60,
        "recent_samples": 30,
        "full_edge": "0",
        "recent_edge": "0",
        "profit_factor": "1",
        "wilson_upper": "0.4999",
    }
    inputs[override] = value
    windows = _stable_negative_windows(**inputs)
    result = resolve_v3_candidate_evidence(
        make_v3_plan(START), windows, shrinkage_k=60
    )
    assert result.stable_negative is False
```

- [ ] **Step 2: Run the targeted tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_evidence.py \
  -k "recursive or stable_negative or root_alone" -q
```

Expected: missing `resolve_v3_candidate_evidence`.

- [ ] **Step 3: Implement recursive pooling and exact gate conditions**

```python
@dataclass(frozen=True)
class V3CandidateEvidence:
    full_edge: Decimal
    recent_edge: Decimal
    edge: Decimal
    stop_rate: Decimal
    mae_p75: Decimal
    deepest_full_key: V3BucketKey
    deepest_recent_key: V3BucketKey
    stable_negative: bool
    full_trace: tuple[V3BucketStats, ...]
    recent_trace: tuple[V3BucketStats, ...]


def recursive_edge(
    path: Sequence[V3BucketStats], *, shrinkage_k: int
) -> Decimal:
    edge = Decimal("0")
    for stats in path:
        weight = Decimal(stats.resolved_samples) / Decimal(
            stats.resolved_samples + shrinkage_k
        )
        edge = weight * stats.net_expectancy + (Decimal("1") - weight) * edge
    return edge
```

Require profile full samples at least 60 or raise `V3EvidenceRejected("PROFILE_HISTORY_TOO_LOW")`. Blend full and recent edges with `n/(n+k)` reliabilities. For `stop_rate` and `mae_p75`, retain the root's raw value, recursively shrink each child value toward its parent using `n/(n+k)`, and combine the full/recent results with the same root-sample reliabilities; this avoids shrinking non-negative risk measures toward an artificial zero baseline. For stable negative, find the deepest child and immediate parent that both have full samples at least 60 and recent samples at least 30; require both levels to satisfy full/recent edge at most zero, full/recent Profit Factor at most one, and full Wilson upper below `0.50`. An absent child, unavailable Profit Factor, or equality at Wilson `0.50` must not hard-reject.

- [ ] **Step 4: Run evidence tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_evidence.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_evidence.py \
  tests/unit/test_five_day_ranking_v3_evidence.py
git diff --cached --check
git commit -m "feat(stock-ai): resolve v3 hierarchical confidence"
```

---

### Task 3: Freeze Common Features and Signed Bin Effects

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3_features.py`
- Create: `tests/unit/test_five_day_ranking_v3_features.py`

**Interfaces:**
- Consumes: calibration observations, trading dates, `FiveDaySignalPlan`, profile stop resolver, `k`.
- Produces: `V3PlanFeatures`, `V3FeatureModel`, `build_v3_feature_model(observations, *, full_dates, recent_dates)`, and `score_v3_feature_adjustment(plan, model, *, shrinkage_k)`.

- [ ] **Step 1: Write failing point-in-time feature tests**

```python
def test_v3_common_features_use_only_signal_plan_values() -> None:
    plan = make_v3_plan(
        date(2025, 1, 10),
        structure_start=date(2025, 1, 2),
        structure_high=Decimal("11"),
        structure_low=Decimal("9"),
        signal_close=Decimal("10"),
        breakout_trigger=Decimal("10.20"),
        structure_stop=Decimal("9.70"),
        resistance_effective_r=None,
    )
    value = derive_v3_plan_features(
        plan, trading_dates=weekday_dates(20, start=date(2024, 12, 23))
    )

    assert value.structure_width == Decimal("2") / Decimal("9")
    assert value.trigger_gap == Decimal("0.02")
    assert value.risk_distance == Decimal("0.03")
    assert value.resistance_effective_r is None


def test_v3_feature_effect_requires_full_recent_sign_agreement() -> None:
    model = _feature_model(full_delta="0.02", recent_delta="-0.01")
    scored = score_v3_feature_adjustment(
        make_v3_plan(START), model, shrinkage_k=30
    )
    assert scored.total == Decimal("0")


def test_v3_feature_caps_apply_per_feature_and_in_total() -> None:
    model = _seven_positive_feature_model(delta="0.02")
    scored = score_v3_feature_adjustment(
        make_v3_plan(START), model, shrinkage_k=30
    )
    assert all(abs(value) <= Decimal("0.001") for value in scored.effects.values())
    assert scored.total == Decimal("0.003")
```

- [ ] **Step 2: Run feature tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_features.py -q
```

Expected: import failure for `five_day_ranking_v3_features`.

- [ ] **Step 3: Implement features, frozen quintiles, and effects**

Create exact types:

```python
V3_FEATURE_NAMES = (
    "setup_quality", "structure_duration", "structure_width",
    "trigger_gap", "risk_distance", "resistance_effective_r",
    "log_average_amount5",
)

@dataclass(frozen=True)
class V3PlanFeatures:
    setup_quality: Decimal
    structure_duration: int
    structure_width: Decimal
    trigger_gap: Decimal
    risk_distance: Decimal
    resistance_effective_r: Decimal | None
    log_average_amount5: Decimal

@dataclass(frozen=True)
class V3FeatureEffect:
    full_samples: int
    recent_samples: int
    full_delta: Decimal
    recent_delta: Decimal

@dataclass(frozen=True)
class V3FeatureModel:
    data_end: date
    boundaries: Mapping[str, tuple[Decimal, ...]]
    effects: Mapping[tuple[str, str, str, str], V3FeatureEffect]

@dataclass(frozen=True)
class V3FeatureAdjustment:
    effects: Mapping[str, Decimal]
    total: Decimal
```

Key effects by `(profile_id, setup_type, feature_name, bin_name)`. Freeze full-window quintiles, apply them unchanged to recent observations, use a separate `MISSING` resistance bin, and compute each raw delta as `bin_net_expectancy - profile_setup_parent_expectancy`. Shrink each full/recent delta as `n / (n + k) * raw_delta`; require full/recent samples 30/15 and the same non-zero sign; then combine the two shrunk deltas as `(r_full * delta_full + r_recent * delta_recent) / (r_full + r_recent)`, where `r = n / (n + k)`. Clip each contribution to `±0.001` and the sum to `±0.003`. Use `resolve_profile_stop` for effective risk distance and reject an unresolved stop. Count structure duration from the supplied trading-date index, compute width and trigger gap with the formulas asserted above, and compute positive five-session traded amount with `Decimal.ln()` inside a fixed local Decimal context of precision 28 so identities do not depend on ambient context.

- [ ] **Step 4: Run Task 3 tests and profile regressions**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_features.py \
  tests/unit/test_five_day_return_profiles.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_features.py \
  tests/unit/test_five_day_ranking_v3_features.py
git diff --cached --check
git commit -m "feat(stock-ai): model v3 point-in-time features"
```

---

### Task 4: Register Policies and Compute Risk-Adjusted Scores

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3.py`
- Create: `tests/unit/test_five_day_ranking_v3.py`

**Interfaces:**
- Consumes: `V3CandidateEvidence`, `V3FeatureAdjustment`, plan risk distance.
- Produces: `FiveDayV3Policy`, registry/hash functions, `FiveDayV3ScoredPlan`, and `score_five_day_plan_v3(plan, *, evidence, features, policy)`.

- [ ] **Step 1: Write failing registry and formula tests**

```python
def test_v3_policy_registry_is_exact_and_hashed() -> None:
    policies = build_five_day_v3_policies()
    assert tuple(value.policy_id for value in policies) == V3_POLICY_IDS
    assert len({five_day_v3_policy_hash(value) for value in policies}) == 8
    assert len(five_day_v3_policy_set_hash()) == 64


def test_v3_score_uses_exact_consistency_and_downside_formula() -> None:
    policy = build_five_day_v3_policies()[0]
    result = score_five_day_plan_v3(
        make_v3_plan(START),
        evidence=_candidate_evidence(
            edge="0.004", full_edge="0.003", recent_edge="0.002",
            stop_rate="0.50", mae_p75="0.08"
        ),
        features=_feature_adjustment(total="0.001"),
        policy=policy,
    )
    assert result.consistency == Decimal("0.001")
    assert result.downside == Decimal("0.003")
    assert result.score == Decimal("0.0035")
```

- [ ] **Step 2: Run tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3.py \
  -k "registry or exact_consistency" -q
```

Expected: import failure for `five_day_ranking_v3`.

- [ ] **Step 3: Implement exact policy identities and score**

```python
V3_POLICY_IDS = (
    "EDGE-K30", "EDGE-K60", "CONSISTENCY-K30", "CONSISTENCY-K60",
    "STRUCTURE-K30", "STRUCTURE-K60", "DOWNSIDE-K30", "DOWNSIDE-K60",
)

@dataclass(frozen=True)
class FiveDayV3Policy:
    policy_id: str
    shrinkage_k: int
    consistency_weight: Decimal
    structure_weight: Decimal
    downside_weight: Decimal

@dataclass(frozen=True)
class FiveDayV3ScoredPlan:
    plan: FiveDaySignalPlan
    evidence: V3CandidateEvidence
    feature_adjustment: V3FeatureAdjustment
    consistency: Decimal
    downside: Decimal
    score: Decimal
    rank: int = 0
    selected: bool = False
```

Implement these formulas using `Decimal` throughout:

```python
consistency = clip(
    min(evidence.full_edge, evidence.recent_edge),
    Decimal("-0.001"),
    Decimal("0.001"),
)
downside = clip(
    Decimal("0.01") * max(evidence.stop_rate - Decimal("0.30"), Decimal("0"))
    + Decimal("0.10") * max(evidence.mae_p75 - Decimal("0.05"), Decimal("0"))
    + Decimal("0.05") * max(risk_distance - Decimal("0.05"), Decimal("0")),
    Decimal("0"),
    Decimal("0.003"),
)
score = (
    evidence.edge
    + policy.consistency_weight * consistency
    + policy.structure_weight * features.total
    - policy.downside_weight * downside
)
```

Build the exact ordered registry from these four templates, each paired first with K30 and then K60:

| Template | Consistency weight | Structure weight | Downside weight |
| --- | ---: | ---: | ---: |
| `EDGE` | `0.50` | `0.50` | `0.50` |
| `CONSISTENCY` | `1.00` | `0.50` | `0.50` |
| `STRUCTURE` | `0.50` | `1.00` | `0.50` |
| `DOWNSIDE` | `0.50` | `0.50` | `1.00` |

The policy-set hash must include all formulas, feature and selection versions, sample boundaries, clips, floor, margin, tie-breakers, and the fixed ordered registry.

- [ ] **Step 4: Run V3 score tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3.py -q
```

Expected: all current tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3.py
git diff --cached --check
git commit -m "feat(stock-ai): score hierarchical ranking v3"
```

---

### Task 5: Rank Zero to Three Plans with Boundary Reduction

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3.py`
- Modify: `tests/unit/test_five_day_ranking_v3.py`

**Interfaces:**
- Consumes: plans, frozen evidence windows/model, policy, active structure IDs.
- Produces: `FiveDayV3RankingResult` and `rank_five_day_plans_v3(plans, windows, feature_model, *, policy, active_structure_ids)` containing a reusable `FiveDayRanking`.

- [ ] **Step 1: Write failing floor, margin, and no-backfill ranking tests**

```python
def test_v3_daily_selection_can_return_zero_one_two_or_three() -> None:
    assert _selected_count(scores=("0.0009",)) == 0
    assert _selected_count(scores=("0.006", "0.004", "0.0035", "0.003")) == 1
    assert _selected_count(scores=("0.006", "0.004", "0.0029", "0.0025")) == 2
    assert _selected_count(scores=("0.006", "0.004", "0.002", "0")) == 3


def test_v3_duplicate_structure_collapses_before_boundary_check() -> None:
    result = _rank_with_duplicate_profiles()
    assert len(result.ranking.plans) == 1
    assert result.ranking.rejection_counts["DUPLICATE_ACTIVE_STRUCTURE"] == 1


def test_v3_stable_negative_is_recorded_before_scoring() -> None:
    result = _rank_one(stable_negative=True)
    assert result.ranking.plans == ()
    assert result.ranking.rejection_counts == {"STABLE_NEGATIVE": 1}


def test_v3_later_admission_rejection_never_backfills() -> None:
    selection, fourth_structure_id = (
        _selection_with_cancelled_first_and_ranked_fourth()
    )
    assert selection.funnel_counts["NOT_TRIGGERED"] == 1
    assert fourth_structure_id not in {
        value.plan.structure_id for value in selection.selected_observations
    }
```

- [ ] **Step 2: Run targeted ranking tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3.py \
  -k "daily_selection or duplicate_structure or stable_negative" -q
```

Expected: missing `rank_five_day_plans_v3` behavior.

- [ ] **Step 3: Implement ranking and iterative boundary selection**

Use this selection kernel after deterministic sort and structure collapse:

```python
eligible = [row for row in structures if row.score >= Decimal("0.001")]
count = min(3, len(eligible))
while count > 1 and count < len(eligible):
    if eligible[count - 1].score - eligible[count].score >= Decimal("0.001"):
        break
    count -= 1
selected = tuple(eligible[:count])
```

Record below-floor rows as `ABSOLUTE_EDGE_TOO_LOW` and rows removed by a failed boundary as `BOUNDARY_MARGIN_TOO_LOW`. Keep ranked traces for all safety-admitted structures. Use this exact sort order: score descending, base edge descending, `min(full_edge, recent_edge)` descending, downside ascending, setup quality descending, normalized code ascending, and profile ID ascending. Do not add a backfill path.

- [ ] **Step 4: Run ranking and shared admission regressions**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_return_validation.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3.py
git diff --cached --check
git commit -m "feat(stock-ai): select zero to three v3 plans"
```

---

### Task 6: Evaluate Train Folds, Diversity, Qualification, and Winner

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3.py`
- Modify: `tests/unit/test_five_day_ranking_v3.py`

**Interfaces:**
- Consumes: canonical `FiveDayResearchReview`, parent identity, Tasks 1-5 builders.
- Produces: `FiveDayRankingV3TrainReview`, policy assessments, and `build_five_day_ranking_v3_train_review(research, *, parent_research_identity)`.

- [ ] **Step 1: Write failing point-in-time fold and diversity tests**

```python
def test_v3_train_excludes_resolution_on_evaluation_boundary() -> None:
    research = _complete_research_with_boundary_resolution()
    review = build_five_day_ranking_v3_train_review(
        research, parent_research_identity="a" * 64
    )
    assert [fold.excluded_unresolved_calibration_rows for fold in review.folds] == [1, 1]
    assert [len(fold.calibration_dates) for fold in review.folds] == [252, 315]
    assert [len(fold.evaluation_dates) for fold in review.folds] == [63, 63]


def test_v3_degenerate_policy_fingerprints_block_every_winner() -> None:
    review = _train_review_with_fingerprints(("same",) * 8)
    finalized = finalize_five_day_ranking_v3_train(review)
    assert finalized.status == "POLICY_SET_DEGENERATE"
    assert finalized.winner_policy_id is None
    assert finalized.validation_eligible is False


def test_v3_policy_qualification_uses_unchanged_hard_thresholds() -> None:
    assessment = assess_five_day_v3_policy(
        policy=build_five_day_v3_policies()[0],
        fold1=_segment(samples=15, edge="0.0001"),
        fold2=_segment(samples=15, edge="0.0001"),
        combined=_segment(samples=40, edge="0.003", profit_factor="1.1001"),
        monotonicity=_qualifying_monotonicity(),
    )
    assert assessment.qualifies is True
```

- [ ] **Step 2: Run targeted train tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3.py \
  -k "train_excludes or degenerate_policy or unchanged_hard" -q
```

Expected: missing train review and assessment functions.

- [ ] **Step 3: Implement fold evaluation and immutable train review**

Add types for fold, variant, rank bands, monotonicity, policy assessment, fingerprint groups, and train review. Reuse `v2_fold_specs`, `admit_five_day_ranking`, `evaluate_five_day_selection_segment`, `build_v2_rank_bands`, `assess_v2_rank_monotonicity`, and `combine_v2_selections` without editing V2.

For each fold, freeze windows and feature models from calibration observations before creating evaluation plans. Evaluate every policy for diagnostic Top-1, formal zero-to-three, and diagnostic Top-5. Official assessments use only formal selections. Combine non-overlapping fold selections without reranking.

Also build `validation_evidence_windows` and `validation_feature_model` from the complete 378-session train segment, using only observations resolved before the first validation session. Store both raw frozen models in `FiveDayRankingV3TrainReview`; they are required by Task 7's train artifact and Task 8's validation builder. They are policy-neutral and retain raw counts/deltas so the verified winner's K30 or K60 can be applied later without recalibration.

Implement exact qualification reasons and deterministic winner order. Before winner selection, fingerprint the ordered formal selected structure keys across both folds and require at least four distinct values. Status is one of `TRAIN_CANDIDATE_SELECTED`, `NO_TRAIN_CANDIDATE`, or `POLICY_SET_DEGENERATE`; every status retains `validation_outcomes_read=False`, `test_outcomes_read=False`, `promotion_eligible=False`, and `trade_permission="NO-TRADE"`.

- [ ] **Step 4: Run V3 train tests and V2 regression**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v2.py -q
```

Expected: all pass and V2 tests unchanged.

- [ ] **Step 5: Commit Task 6**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3.py
git diff --cached --check
git commit -m "feat(stock-ai): evaluate hierarchical ranking v3"
```

---

### Task 7: Persist Strict Immutable V3 Train Evidence

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3_report.py`
- Create: `tests/unit/test_five_day_ranking_v3_report.py`

**Interfaces:**
- Consumes: `FiveDayRankingV3TrainReview` from Task 6.
- Produces: `FiveDayRankingV3TrainArtifact`, canonical train payload, exclusive writer, and strict train loader.

- [ ] **Step 1: Write failing train artifact tests**

```python
def test_v3_train_writer_is_byte_idempotent_and_aggregate_only(tmp_path) -> None:
    review = _complete_v3_train_review()
    first = write_five_day_ranking_v3_train(review, tmp_path)
    before = first.read_bytes()
    second = write_five_day_ranking_v3_train(review, tmp_path)
    loaded = load_five_day_ranking_v3_train(first)

    assert first == second
    assert first.read_bytes() == before
    assert loaded.artifact_identity in first.name
    assert not {"observations", "selected_observations"}.intersection(
        _nested_keys(json.loads(before))
    )


def test_v3_train_loader_rejects_registry_or_lineage_tamper(tmp_path) -> None:
    path = write_five_day_ranking_v3_train(
        _complete_v3_train_review(), tmp_path
    )
    payload = json.loads(path.read_text())
    payload["policy_set_hash"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid ranking v3 train artifact"):
        load_five_day_ranking_v3_train(path)
```

- [ ] **Step 2: Run train report tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_report.py -q
```

Expected: import failure for `five_day_ranking_v3_report`.

- [ ] **Step 3: Implement canonical train payload, writer, and loader**

Create `FiveDayRankingV3TrainArtifact` with identity, parent identities, policy-set hash, frozen hierarchy/feature payload, winner fields, eligibility, and original verified payload.

Canonical train payload must contain exactly 72 variants: eight policies times three selection modes times three segments. Sort policies by `V3_POLICY_IDS`, modes by Top-1/formal/Top-5, and folds by fold1/fold2/combined. Store hierarchy and feature summaries but never raw observations. Use exclusive create; when the path exists, accept only byte-identical content. Recompute identity, filename, registry, policy hashes, status, winner, safety flags, counts, and nested-key exclusions in strict loaders.

- [ ] **Step 4: Run train report and V2 artifact regressions**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_report.py \
  tests/unit/test_five_day_ranking_v2_report.py \
  tests/unit/test_five_day_ranking_report.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit Task 7**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_report.py \
  tests/unit/test_five_day_ranking_v3_report.py
git diff --cached --check
git commit -m "feat(stock-ai): persist ranking v3 train evidence"
```

---

### Task 8: Freeze and Persist One Winner for Validation

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3.py`
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_report.py`
- Modify: `tests/unit/test_five_day_ranking_v3.py`
- Modify: `tests/unit/test_five_day_ranking_v3_report.py`

**Interfaces:**
- Consumes: verified `FiveDayRankingV3TrainArtifact`, canonical parent, frozen hierarchy and feature payload from train.
- Produces: `FiveDayRankingV3ValidationReview`, validation payload/writer/loader, `build_five_day_ranking_v3_validation_review(research, train, *, parent_research_identity)`, and `v3_validation_trial_identity(train_identity, winner_policy_hash)`.

- [ ] **Step 1: Write failing validation-lock tests**

```python
def test_v3_validation_rejects_no_winner_before_outcome_use() -> None:
    with pytest.raises(ValueError, match="unique train winner"):
        build_five_day_ranking_v3_validation_review(
            _research_review(), _train_artifact(winner=False),
            parent_research_identity="a" * 64,
        )


def test_v3_validation_uses_frozen_train_evidence_only(monkeypatch) -> None:
    train = _train_artifact(winner=True)
    monkeypatch.setattr(
        v3, "build_v3_evidence_windows",
        lambda *args, **kwargs: pytest.fail("validation must not recalibrate"),
    )
    review = build_five_day_ranking_v3_validation_review(
        _research_review(), train, parent_research_identity="a" * 64
    )
    assert review.winner_policy_hash == train.winner_policy_hash
    assert review.validation_outcomes_read is True
    assert review.test_outcomes_read is False
```

- [ ] **Step 2: Write failing validation conflict test**

```python
def test_v3_validation_writer_never_overwrites_conflict(tmp_path) -> None:
    review = _complete_v3_validation_review()
    path = write_five_day_ranking_v3_validation(review, tmp_path)
    path.write_text("{}\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="artifact conflict"):
        write_five_day_ranking_v3_validation(review, tmp_path)
    assert path.read_bytes() == before
```

- [ ] **Step 3: Run validation tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3_report.py \
  -k "validation_" -q
```

Expected: missing V3 validation builder and writer.

- [ ] **Step 4: Implement frozen validation and immutable evidence**

Require exact winner policy/hash, policy-set hash, parent identity, input fingerprint, split, and train evidence payload. In `five_day_ranking_v3.py`, import `FiveDayRankingV3TrainArtifact` only under `TYPE_CHECKING` and use a quoted annotation, matching the V2 dependency direction; the report module may import ranking dataclasses at runtime, but ranking must not import the report module at runtime. Rehydrate hierarchy and feature models from the verified train artifact; never rebuild them from validation outcomes. Rank only validation plans, admit through capacity three, and evaluate existing formal validation thresholds: validation samples 30, cumulative samples 70, positive expectancy, Profit Factor above `1.10`, Wilson lower at least `0.45`, stop rate at most `0.40`, positive-window ratio at least `0.60`, maximum drawdown at most `0.10`, and existing portfolio concentration limits.

Derive trial identity from schema, train artifact identity, and winner policy hash. Add canonical validation payload, exclusive writer, and strict loader that requires expected train identity and policy hash. Keep `promotion_eligible=False` and `trade_permission="NO-TRADE"` even when validation qualifies for later test design.

- [ ] **Step 5: Run V3 validation and V2 report regressions**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3_report.py \
  tests/unit/test_five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2_report.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit Task 8**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3.py \
  stock_ai/buy_point_selection/five_day_ranking_v3_report.py \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3_report.py
git diff --cached --check
git commit -m "feat(stock-ai): validate frozen ranking v3 winner"
```

---

### Task 9: Expose the Separate Manual V3 CLI

**Files:**
- Create: `scripts/analysis/analyze_five_day_ranking_v3.py`
- Create: `tests/unit/test_analyze_five_day_ranking_v3_cli.py`

**Interfaces:**
- Consumes: canonical parent loader and V3 builders/loaders/writers.
- Produces: exactly `diagnose-train` and `validate-ranking` commands.

- [ ] **Step 1: Write failing parser and train-only tests**

```python
def test_v3_parser_exposes_only_two_manual_stages() -> None:
    parser = cli.build_parser()
    subparsers = next(
        action for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert tuple(subparsers.choices) == (
        "diagnose-train", "validate-ranking"
    )
    assert {"--database-url", "--freeze", "--test", "--forward", "--notify"}.isdisjoint(
        _option_strings(parser)
    )


def test_v3_diagnose_train_writes_no_later_artifact(tmp_path) -> None:
    parent = write_five_day_research(_research_review(), tmp_path)
    assert cli.main((
        "diagnose-train", "--research-artifact", str(parent),
        "--output-dir", str(tmp_path),
    )) == 0
    assert len(tuple(tmp_path.glob("ranking-v3-train-*.json"))) == 1
    assert tuple(tmp_path.glob("ranking-v3-validation-*.json")) == ()
```

- [ ] **Step 2: Write failing validation ordering and error tests**

```python
def test_v3_no_winner_stops_before_loading_parent(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_five_day_ranking_v3_train", lambda _: _no_winner())
    monkeypatch.setattr(
        cli, "load_five_day_research",
        lambda _: pytest.fail("parent outcomes must not be read"),
    )
    assert cli.main(_validate_argv()) == 2


def test_v3_existing_validation_reuses_before_loading_parent(monkeypatch, tmp_path) -> None:
    train = _winner_train_artifact()
    existing = _write_existing_validation(train, tmp_path)
    monkeypatch.setattr(cli, "load_five_day_ranking_v3_train", lambda _: train)
    monkeypatch.setattr(
        cli, "load_five_day_research",
        lambda _: pytest.fail("parent outcomes must not be reread"),
    )
    assert cli.main(_validate_argv(tmp_path)) == 0
    assert existing.is_file()


def test_v3_cli_sanitizes_dependency_details(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli, "dispatch_command",
        lambda _: (_ for _ in ()).throw(ValueError("mysql://user:secret@host/raw")),
    )
    assert cli.main(_diagnose_argv()) == 2
    assert capsys.readouterr().err == "五日排名V3诊断失败\n"
```

- [ ] **Step 3: Run CLI tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_analyze_five_day_ranking_v3_cli.py -q
```

Expected: script import failure.

- [ ] **Step 4: Implement exact CLI with train-first validation**

Use `Path`-typed required artifact/output arguments. Diagnose loads and verifies the canonical parent, derives its identity with `five_day_research_payload`, builds train review, and writes one train artifact. Validation strictly loads train first; no winner or `POLICY_SET_DEGENERATE` raises before checking the parent path. Derive validation trial path and strictly reuse an existing artifact before loading the parent. Catch only `OSError`, `RuntimeError`, `TypeError`, and `ValueError`, print the exact sanitized line, and return 2.

- [ ] **Step 5: Run CLI and report tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_analyze_five_day_ranking_v3_cli.py \
  tests/unit/test_five_day_ranking_v3_report.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit Task 9**

```bash
git add scripts/analysis/analyze_five_day_ranking_v3.py \
  tests/unit/test_analyze_five_day_ranking_v3_cli.py
git diff --cached --check
git commit -m "feat(stock-ai): expose ranking v3 diagnostics"
```

---

### Task 10: Verify Regressions and Run V3 Train Diagnosis Only

**Files:**
- Read: `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
- Generate but never stage: `output/research/buy_point_five_day_returns/ranking-v3-train-<identity>.json`

**Interfaces:**
- Consumes: committed V3 implementation and immutable canonical parent.
- Produces: one ignored train-only evidence artifact and a descriptive comparison report.

- [ ] **Step 1: Run the complete relevant regression suite**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_profiles.py \
  tests/unit/test_five_day_return_execution.py \
  tests/unit/test_five_day_return_validation.py \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py \
  tests/unit/test_five_day_ranking_research.py \
  tests/unit/test_five_day_ranking_report.py \
  tests/unit/test_five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2_report.py \
  tests/unit/test_analyze_five_day_ranking_cli.py \
  tests/unit/test_analyze_five_day_ranking_v2_cli.py \
  tests/unit/test_five_day_ranking_v3_evidence.py \
  tests/unit/test_five_day_ranking_v3_features.py \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3_report.py \
  tests/unit/test_analyze_five_day_ranking_v3_cli.py \
  tests/unit/test_research_five_day_return_shadow_cli.py -q
```

Expected: zero failures.

- [ ] **Step 2: Snapshot the output directory and run only V3 train**

```bash
find output/research/buy_point_five_day_returns -maxdepth 1 -type f -print | sort
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking_v3.py diagnose-train \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

Expected: exactly one `ranking-v3-train-<identity>.json` path and no validation path.

- [ ] **Step 3: Verify the artifact with the strict loader**

Assert parent identity, input fingerprint, eight policies, 72 variants, 252/315 calibration sessions, 63/63 evaluation sessions, complete point-in-time cutoffs, frozen hierarchy and feature versions, admitted-only metric counts, at least four fingerprints or terminal `POLICY_SET_DEGENERATE`, false validation/test read flags, false promotion, `NO-TRADE`, and either one winner or a valid terminal no-winner status.

- [ ] **Step 4: Prove idempotency and side-effect boundaries**

Hash the train file, rerun the identical diagnose command, and require the same path and file hash. Require no V3 validation, test, freeze, forward, settlement, holding, memory, notification, or staged research artifact. Strictly load the existing V1 and V2 artifacts and confirm their identities remain `d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3` and `99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22`.

- [ ] **Step 5: Report and stop**

Report retained universe by hierarchy, hard-gate counts, stable-negative counts, feature coverage, all eight fingerprints, Top-1/formal/Top-5 fold and combined metrics, rank bands, funnels, all qualification reasons, winner or terminal status, and descriptive V1/V2 comparison. Label all evidence train-only. Do not run `validate-ranking`; request explicit user confirmation only if one unique train winner exists.

No commit is required for Task 10 because generated evidence is ignored and must not be staged.
