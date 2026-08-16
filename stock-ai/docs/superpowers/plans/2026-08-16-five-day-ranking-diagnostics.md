# Five-Day Ranking Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate only the daily Top-N trades that the five-day strategy would actually select and admit, then produce an immutable train-only ranking and loss-attribution artifact before any corrected validation is allowed.

**Architecture:** Keep the complete `2b52de79...` research artifact as an immutable legacy parent. Add one shared selection trace in the validation module, build corrected `selected-portfolio-v2` metrics and 252+63+63 train diagnostics in a focused research module, serialize write-once train/validation artifacts in a separate report module, and expose a manual two-stage CLI. Implementation acceptance stops after `diagnose-train`.

**Tech Stack:** Python 3.11, frozen dataclasses, `Decimal`, existing five-day observations and calibration/ranking functions, deterministic JSON artifacts, argparse, pytest.

## Global Constraints

- Run implementation commands from `/Users/huan.yu/dev/tools-workspace/stock-ai`.
- The immutable parent is `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json` with `point_in_time_complete=true` and `test_outcomes_read=false`.
- Preserve the exact 378/126/126 split and never read test outcomes.
- The train diagnostic uses sessions 1-252 for initial calibration, sessions 253-315 for fold 1, and sessions 316-378 for fold 2.
- Top 1/3/5 and all attribution buckets are train-only and descriptive. The only preregistered validation policy is the current ranking key, daily Top 3, active capacity 3, and the existing four profiles.
- Corrected metric version is exactly `selected-portfolio-v2`.
- Return and risk metrics use only capacity-admitted observations with an actual entry and completed exit. Funnel counts retain rejected, overflow, cancelled, not-triggered, missing, unresolved, and capacity-rejected evidence.
- Do not backfill a lower-ranked plan after a selected plan later fails to trigger.
- Do not change candidate discovery, ranking keys, profiles, entries, stops, costs, thresholds, `TWO_R`, or formal selection policy.
- Do not add a database table, scheduler, notification, order, holdings write, executable shares, advisor memory, or personal decision-memory write.
- Do not use Eastmoney stock diagnosis or the deprecated Eastmoney eight-dimension framework.
- Do not run `validate-ranking`, `freeze`, `test`, forward screening, or settlement during implementation acceptance.
- Preserve all unrelated dirty-worktree changes. Stage only the exact files named by each task; never stage `tests/unit/test_buy_point_reference_cninfo.py` or generated artifacts.
- Use TDD for every production behavior and commit each task independently.

## Required Execution Order

Execute the numbered tasks only in this dependency order: **Task 1 -> Task 2
-> Task 3 -> Task 4 -> Task 5 -> Task 6**. Tasks 3 and 4 must not start until
Tasks 1 and 2 are committed.

---

### Task 1: Produce One Auditable Ranking and Admission Trace

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_return_validation.py:85-110,352-455,556-600`
- Modify: `tests/unit/test_five_day_return_validation.py:1-365`

**Interfaces:**
- Consumes: `FiveDaySignalPlan`, `FiveDayObservation`, `FiveDayCalibration`, `_ranking_key(...)`, `_active_structure_key(...)`, and `_observation_key(...)`.
- Produces: `FiveDayRankedPlan`, `FiveDaySelection`, an extended `FiveDayRanking.ranked`, and `select_five_day_portfolio(...)`.

- [ ] **Step 1: Add test-only observation helpers**

Add beside `_observation(...)`:

```python
def _observation_for_plan(
    plan: FiveDaySignalPlan,
    *,
    net_return: str,
) -> FiveDayObservation:
    template = _observation(plan.candidate.signal_date, net_return=net_return)
    return replace(
        template,
        plan=plan,
        trade=replace(
            template.trade,
            profile_id=plan.profile.profile_id,
            structure_id=plan.structure_id,
            code=plan.candidate.code,
            signal_date=plan.candidate.signal_date,
        ),
    )


def _not_triggered_for_plan(plan: FiveDaySignalPlan) -> FiveDayObservation:
    value = _observation_for_plan(plan, net_return="0")
    return replace(
        value,
        trade=replace(
            value.trade,
            status="NOT_TRIGGERED",
            entry_date=None,
            entry_price=None,
            stop_price=None,
            evaluation_shares=0,
            evaluation_notional=Decimal("0"),
            exit=None,
            net_pnl=Decimal("0"),
            net_return=None,
            mfe=None,
            mae=None,
        ),
    )
```

- [ ] **Step 2: Write the failing deterministic-trace and no-backfill test**

```python
def test_selection_trace_keeps_overflow_and_does_not_backfill() -> None:
    plans = tuple(_plan(START, code=f"60000{index}") for index in range(1, 5))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    first = _observation_for_plan(plans[0], net_return="0.02")
    not_triggered = _not_triggered_for_plan(plans[1])
    third = _observation_for_plan(plans[2], net_return="0.01")
    overflow = _observation_for_plan(plans[3], net_return="0.99")

    result = select_five_day_portfolio(
        plans,
        (first, not_triggered, third, overflow),
        calibrations,
        daily_limit=3,
        capacity=3,
    )

    assert tuple((row.rank, row.selected) for row in result.ranking.ranked) == (
        (1, True),
        (2, True),
        (3, True),
        (4, False),
    )
    assert tuple(row.plan.candidate.code for row in result.admitted) == (
        "600001",
        "600003",
    )
    assert result.funnel_counts["DAILY_CANDIDATE_LIMIT"] == 1
    assert result.funnel_counts["NOT_TRIGGERED"] == 1
    assert overflow not in result.admitted
```

- [ ] **Step 3: Run the trace test to verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_validation.py::test_selection_trace_keeps_overflow_and_does_not_backfill \
  -q
```

Expected: import failure because the new selection interfaces do not exist.

- [ ] **Step 4: Add immutable selection dataclasses**

```python
@dataclass(frozen=True)
class FiveDayRankedPlan:
    plan: FiveDaySignalPlan
    rank: int
    selected: bool


@dataclass(frozen=True)
class FiveDayRanking:
    plans: tuple[FiveDaySignalPlan, ...]
    rejection_counts: Mapping[str, int]
    ranked: tuple[FiveDayRankedPlan, ...] = ()


@dataclass(frozen=True)
class FiveDaySelection:
    ranking: FiveDayRanking
    selected_observations: tuple[FiveDayObservation, ...]
    admitted: tuple[FiveDayObservation, ...]
    funnel_counts: Mapping[str, int]
    incomplete: bool
```

Keep `FiveDayRanking.plans` as the selected-plan compatibility surface and
append the defaulted `ranked` field after `rejection_counts`, so existing
two-positional-argument test doubles remain valid.

- [ ] **Step 5: Extend ranking and implement selection once**

While building each date's unique ranked list, append every position to
`FiveDayRanking.ranked` and set `selected=rank <= daily_limit`. Add:

```python
def select_five_day_portfolio(
    plans: Sequence[FiveDaySignalPlan],
    observations: Sequence[FiveDayObservation],
    calibrations: Mapping[str, FiveDayCalibration],
    *,
    active_structure_ids: frozenset[str] = frozenset(),
    daily_limit: int = 3,
    capacity: int = 3,
) -> FiveDaySelection:
    if capacity < 0:
        raise ValueError("capacity must not be negative")
    ranking = rank_five_day_plans(
        plans,
        calibrations,
        active_structure_ids=active_structure_ids,
        daily_limit=daily_limit,
    )
    by_plan = {_observation_key(value): value for value in observations}
    counts = Counter(ranking.rejection_counts)
    selected: list[FiveDayObservation] = []
    admitted: list[FiveDayObservation] = []
    incomplete = False
    for plan in ranking.plans:
        value = by_plan.get(_plan_key(plan))
        if value is None:
            counts["MISSING_OBSERVATION"] += 1
            incomplete = True
            continue
        selected.append(value)
        if not _is_resolved(value):
            counts[value.trade.status] += 1
            incomplete = incomplete or value.trade.status == "PENDING"
            continue
        if value.trade.entry_date is None or value.trade.exit is None:
            counts["INCOMPLETE_RESOLVED_TRADE"] += 1
            incomplete = True
            continue
        entry_date = value.trade.entry_date
        active = sum(
            row.trade.entry_date is not None
            and row.trade.entry_date <= entry_date
            and row.trade.exit is not None
            and row.trade.exit.actual_exit_date >= entry_date
            for row in admitted
        )
        if active >= capacity:
            counts["PORTFOLIO_CAPACITY"] += 1
            continue
        admitted.append(value)
    counts["SELECTED_PLANS"] = len(ranking.plans)
    counts["ADMITTED_TRADES"] = len(admitted)
    return FiveDaySelection(
        ranking=ranking,
        selected_observations=tuple(selected),
        admitted=tuple(admitted),
        funnel_counts=dict(sorted(counts.items())),
        incomplete=incomplete,
    )
```

- [ ] **Step 6: Make portfolio metrics consume the shared selection**

Replace the local ranking/admission sequence in
`build_five_day_portfolio_metrics(...)` with:

```python
selection = select_five_day_portfolio(plans, observations, calibrations)
accepted = selection.admitted
```

Delete `_admit_research_trades(...)` after all callers use the shared function.

- [ ] **Step 7: Run the validation unit file and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_validation.py -q
git add \
  stock_ai/buy_point_selection/five_day_return_validation.py \
  tests/unit/test_five_day_return_validation.py
git diff --cached --check
git commit -m "feat(stock-ai): trace five-day portfolio selection"
```

---

### Task 2: Calculate Corrected Metrics From Admitted Trades Only

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_return_validation.py:230-290,680-770`
- Modify: `tests/unit/test_five_day_return_validation.py`

**Interfaces:**
- Consumes: `FiveDaySelection`, `select_five_day_portfolio(...)`, `_wilson_interval(...)`, `_positive_window_ratio(...)`, and `assess_five_day_segment(...)`.
- Produces: `SELECTED_PORTFOLIO_METRIC_VERSION`, `FiveDaySelectedSegment`, and `evaluate_selected_five_day_segment(...)`.

- [ ] **Step 1: Write failing overflow-isolation and admitted-loss tests**

```python
def test_selected_metrics_ignore_daily_overflow_losses() -> None:
    plans = tuple(_plan(START, code=f"60000{index}") for index in range(1, 5))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    observations = tuple(
        _observation_for_plan(
            plan,
            net_return="0.01" if index < 3 else "-0.99",
        )
        for index, plan in enumerate(plans)
    )
    value = _selected_fixture_segment(plans, observations, calibrations)

    assert value.metrics.triggered_resolved == 3
    assert value.metrics.net_expectancy == Decimal("0.01")
    assert value.selection.funnel_counts["DAILY_CANDIDATE_LIMIT"] == 1


def test_selected_metrics_change_when_an_admitted_trade_loses() -> None:
    plans = tuple(_plan(START, code=f"60000{index}") for index in range(1, 4))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    winning = tuple(
        _observation_for_plan(plan, net_return="0.01") for plan in plans
    )
    losing = (*winning[:2], _observation_for_plan(plans[2], net_return="-0.03"))

    before = _selected_fixture_segment(plans, winning, calibrations).metrics
    after = _selected_fixture_segment(plans, losing, calibrations).metrics

    assert before.net_expectancy == Decimal("0.01")
    assert after.net_expectancy == Decimal("-0.003333333333333333333333333333")
    assert after.profit_factor == Decimal("0.6666666666666666666666666667")
```

`_selected_fixture_segment(...)` calls the new evaluator with literal
`daily_limit=3`, `capacity=3`, and minimum sample values of one.

- [ ] **Step 2: Run both tests to verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_validation.py::test_selected_metrics_ignore_daily_overflow_losses \
  tests/unit/test_five_day_return_validation.py::test_selected_metrics_change_when_an_admitted_trade_loses \
  -q
```

Expected: import failure because corrected selected metrics do not exist.

- [ ] **Step 3: Add the metric version and result type**

```python
SELECTED_PORTFOLIO_METRIC_VERSION = "selected-portfolio-v2"


@dataclass(frozen=True)
class FiveDaySelectedSegment:
    metric_version: str
    metrics: FiveDaySegmentMetrics
    portfolio: FiveDayPortfolioMetrics
    selection: FiveDaySelection
```

- [ ] **Step 4: Implement one corrected segment evaluator**

```python
def evaluate_selected_five_day_segment(
    *,
    profile_id: str,
    segment: str,
    observations: Sequence[FiveDayObservation],
    trading_dates: Sequence[date],
    ranking_calibrations: Mapping[str, FiveDayCalibration],
    daily_limit: int,
    capacity: int,
    cumulative_samples: int,
    required_samples: int,
    required_cumulative_samples: int,
) -> FiveDaySelectedSegment:
    profile_values = tuple(
        value for value in observations
        if value.plan.profile.profile_id == profile_id
    )
    sessions = tuple(trading_dates)
    data_end = sessions[-1]
    cutoff = tuple(
        value for value in profile_values
        if not _is_resolved(value) or value.resolution_date <= data_end
    )
    selection = select_five_day_portfolio(
        tuple(value.plan for value in cutoff),
        cutoff,
        ranking_calibrations,
        daily_limit=daily_limit,
        capacity=capacity,
    )
    admitted = selection.admitted
    positives = tuple(value for value in admitted if value.trade.net_pnl > 0)
    gross_profit = sum((value.trade.net_pnl for value in positives), Decimal("0"))
    gross_loss = abs(sum(
        (value.trade.net_pnl for value in admitted if value.trade.net_pnl < 0),
        Decimal("0"),
    ))
    portfolio = _portfolio_metrics_from_accepted(admitted)
    wilson = _wilson_interval(len(positives), len(admitted))
    metrics = assess_five_day_segment(
        profile_id=profile_id,
        segment=segment,
        triggered_resolved=len(admitted),
        net_expectancy=_average(tuple(
            value.trade.net_return for value in admitted
            if value.trade.net_return is not None
        )),
        profit_factor=(gross_profit / gross_loss if gross_loss > 0 else None),
        profitable_wilson_lower=wilson[0],
        stop_rate=(
            Decimal(sum(value.trade.status == "STOPPED" for value in admitted))
            / Decimal(len(admitted)) if admitted else Decimal("0")
        ),
        positive_window_ratio=_positive_window_ratio(
            admitted, sessions, data_end=data_end
        ),
        maximum_drawdown=portfolio.maximum_drawdown,
        required_samples=required_samples,
        cumulative_samples=cumulative_samples,
        required_cumulative_samples=required_cumulative_samples,
    )
    if selection.incomplete:
        metrics = replace(
            metrics,
            qualifies=False,
            reasons=(*metrics.reasons, "SELECTION_INCOMPLETE"),
        )
    return FiveDaySelectedSegment(
        metric_version=SELECTED_PORTFOLIO_METRIC_VERSION,
        metrics=metrics,
        portfolio=portfolio,
        selection=selection,
    )
```

Extract `_portfolio_metrics_from_accepted(...)` from the existing portfolio
body so both legacy portfolio metrics and the corrected segment use the same
concentration and drawdown calculation.

- [ ] **Step 5: Add cancellation, unresolved, and capacity sample tests**

Create selected plans with literal `NOT_TRIGGERED`, `PENDING`, and overlapping
entries. Assert only completed admitted trades contribute to
`triggered_resolved`; assert all three reasons remain in
`selection.funnel_counts`, `selection.incomplete` is true for `PENDING`, and
an incomplete selection can never qualify even when its numeric gates pass.

- [ ] **Step 6: Run all validation tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_validation.py -q
git add \
  stock_ai/buy_point_selection/five_day_return_validation.py \
  tests/unit/test_five_day_return_validation.py
git diff --cached --check
git commit -m "fix(stock-ai): measure admitted five-day trades"
```

---

### Task 3: Build Point-in-Time Train Ranking Diagnostics

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_research.py`
- Create: `tests/unit/test_five_day_ranking_research.py`

**Interfaces:**
- Consumes: `FiveDayResearchReview`, `FiveDayObservation`, `build_five_day_calibrations(...)`, `evaluate_selected_five_day_segment(...)`, `select_five_day_portfolio(...)`, and the existing profile matrix.
- Produces: `RankingPolicy`, `TrainFold`, `RankingVariantMetrics`, `AttributionRow`, `FiveDayRankingTrainReview`, and `build_five_day_ranking_train_review(...)`.

- [ ] **Step 1: Write failing fold-boundary and train-only tests**

```python
def test_train_review_uses_exact_expanding_folds_and_no_later_dates() -> None:
    review = _complete_review_fixture()

    result = build_five_day_ranking_train_review(
        review,
        parent_research_identity="a" * 64,
    )

    assert tuple((row.calibration_dates, row.evaluation_dates) for row in result.folds) == (
        (review.split.train[:252], review.split.train[252:315]),
        (review.split.train[:315], review.split.train[315:378]),
    )
    assert result.validation_outcomes_read is False
    assert result.test_outcomes_read is False
    assert result.daily_limits == (1, 3, 5)
    assert result.registered_validation_policy.daily_limit == 3
    assert result.registered_validation_policy.capacity == 3


def test_fold_calibration_excludes_outcome_resolved_on_or_after_fold_start() -> None:
    review = _review_with_boundary_resolution()

    result = build_five_day_ranking_train_review(
        review,
        parent_research_identity="a" * 64,
    )

    assert result.folds[0].excluded_unresolved_calibration_rows == 1
    assert result.folds[0].calibration_data_end < result.folds[0].evaluation_dates[0]
```

- [ ] **Step 2: Run the new file to verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_research.py -q
```

Expected: module import failure.

- [ ] **Step 3: Add the fixed policy and train-review dataclasses**

```python
RANKING_RESEARCH_SCHEMA = "five-day-ranking-train-v1"
TRAIN_DAILY_LIMITS = (1, 3, 5)


@dataclass(frozen=True)
class RankingPolicy:
    ranking_key_version: str
    daily_limit: int
    capacity: int
    metric_version: str


REGISTERED_VALIDATION_POLICY = RankingPolicy(
    ranking_key_version="five-day-ranking-key-v1",
    daily_limit=3,
    capacity=3,
    metric_version=SELECTED_PORTFOLIO_METRIC_VERSION,
)


@dataclass(frozen=True)
class TrainFold:
    fold_id: str
    calibration_dates: tuple[date, ...]
    evaluation_dates: tuple[date, ...]
    calibration_data_end: date
    excluded_unresolved_calibration_rows: int


@dataclass(frozen=True)
class RankingVariantMetrics:
    fold_id: str
    scope: str
    daily_limit: int
    segment: FiveDaySelectedSegment


@dataclass(frozen=True)
class AttributionRow:
    fold_id: str
    scope: str
    dimension: str
    bucket: str
    selected_plans: int
    admitted_trades: int
    win_count: int
    loss_count: int
    stop_count: int
    gross_pnl: Decimal
    net_pnl: Decimal
    cost_drag: Decimal
    net_expectancy: Decimal


@dataclass(frozen=True)
class FiveDayRankingTrainReview:
    schema: str
    parent_research_identity: str
    parent_input_fingerprint: str
    folds: tuple[TrainFold, ...]
    daily_limits: tuple[int, ...]
    variants: tuple[RankingVariantMetrics, ...]
    attribution: tuple[AttributionRow, ...]
    quintile_boundaries: Mapping[str, Mapping[str, tuple[Decimal, ...]]]
    fold_stability: Mapping[str, str]
    registered_validation_policy: RankingPolicy
    validation_outcomes_read: bool
    test_outcomes_read: bool
```

- [ ] **Step 4: Implement the exact 252+63+63 projection**

```python
def _fold_specs(
    train_dates: Sequence[date],
) -> tuple[tuple[str, tuple[date, ...], tuple[date, ...]], ...]:
    values = tuple(train_dates)
    if len(values) != 378:
        raise ValueError("ranking diagnostics require exactly 378 train sessions")
    return (
        ("train-fold-1", values[:252], values[252:315]),
        ("train-fold-2", values[:315], values[315:378]),
    )
```

For each fold, retain only resolved calibration observations whose signal date
belongs to the calibration set and whose resolution date is strictly earlier
than the first evaluation date. Count and exclude every unresolved or
boundary-overlapping calibration observation. Pass only evaluation-date
observations into Top-N evaluation. Build calibrations with the exact
calibration-date tuple so `data_end` remains before the fold.

- [ ] **Step 5: Build per-profile and global Top-N variants**

For every fold and `daily_limit` in `(1, 3, 5)`, call
`evaluate_selected_five_day_segment(...)` once per profile. Use literal scope
values `profile:<profile-id>`.

For the `global` scope, call `select_five_day_portfolio(...)` with all profiles
competing, global structure deduplication, the same daily limit, and capacity
three. Calculate the same selected metrics from its admitted observations via
the shared metric helper extracted in Task 2.

After both folds are evaluated, build literal `train-combined` variants from
the two folds' already selected/admitted observations; do not rerank across a
fold boundary and do not add calibration-window trades. Record each
scope/limit pair as `STABLE` only when both fold expectancies have the same
positive sign and neither fold violates the configured drawdown gate;
otherwise record `UNSTABLE`. Stability remains descriptive.

- [ ] **Step 6: Build deterministic rank and loss attribution**

```python
def _rank_band(rank: int) -> str:
    if rank == 1:
        return "RANK_1"
    if rank <= 3:
        return "RANK_2_3"
    if rank <= 5:
        return "RANK_4_5"
    return "RANK_6_PLUS"
```

Aggregate literal dimensions: rank band, setup type, market status, sector
resonance, resistance basis, setup-quality quintile, calibration-expectancy
quintile, profile, trade status, and gross-to-net cost drag. Derive quintile
boundaries only from the current fold and persist those boundaries in the
review. Every attribution row records gross P&L, net P&L, cost drag, wins,
losses, stops, admitted count, and expectancy. Attribution rows remain
descriptive and have no `qualifies` field.

- [ ] **Step 7: Add determinism and non-promotion tests**

Run the same review twice and assert dataclass equality. Assert rank-band rows
contain all four literal bands. Recursively inspect the train payload model and
assert it contains neither `validation_metrics`, `promotion_eligible`, nor a
test observation.

- [ ] **Step 8: Run and commit the train-research module**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_research.py \
  tests/unit/test_five_day_return_validation.py -q
git add \
  stock_ai/buy_point_selection/five_day_ranking_research.py \
  tests/unit/test_five_day_ranking_research.py
git diff --cached --check
git commit -m "feat(stock-ai): diagnose five-day rankings on train"
```

---

### Task 4: Add Immutable Train and Preregistered Validation Artifacts

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_report.py`
- Modify: `stock_ai/buy_point_selection/five_day_ranking_research.py`
- Create: `tests/unit/test_five_day_ranking_report.py`
- Modify: `tests/unit/test_five_day_ranking_research.py`

**Interfaces:**
- Consumes: `FiveDayRankingTrainReview`, existing base-research identity and fingerprint, selected metrics from Task 2, and canonical JSON hashing.
- Produces: `FiveDayRankingValidationReview`, `build_five_day_ranking_validation_review(...)`, train/validation payloads, loaders, writers, and `validation_trial_identity(...)`.

- [ ] **Step 1: Write the failing canonical train-artifact test**

```python
def test_train_artifact_is_canonical_safe_and_contains_no_validation_returns(
    tmp_path: Path,
) -> None:
    review = _ranking_train_review_fixture()
    payload = five_day_ranking_train_payload(review)
    path = write_five_day_ranking_train(review, tmp_path)

    assert payload["schema"] == "five-day-ranking-train-v1"
    assert payload["stage"] == "diagnose-train"
    assert payload["metric_version"] == "selected-portfolio-v2"
    assert payload["validation_outcomes_read"] is False
    assert payload["test_outcomes_read"] is False
    assert payload["registered_validation_policy"]["daily_limit"] == 3
    assert "validation_metrics" not in payload
    assert write_five_day_ranking_train(review, tmp_path) == path
    assert load_five_day_ranking_train(path) == review
```

- [ ] **Step 2: Run the report test to verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_report.py::test_train_artifact_is_canonical_safe_and_contains_no_validation_returns \
  -q
```

Expected: module import failure.

- [ ] **Step 3: Implement canonical hashing and the exclusive train writer**

```python
def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_exclusive_or_verify(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("immutable ranking artifact content mismatch")
```

The train payload stores aggregate diagnostics plus selected/admitted plan
keys. Its hashed lineage includes the parent research identity and input
fingerprint, exact split and fold dates, profile-matrix hash, current ranking
key version, selection-policy hash, daily limits, capacity, cost/sizing/
execution/metric/report versions, diagnostic dimensions, and the registered
validation-policy hash. Raw observations stay in the immutable parent research
artifact.

- [ ] **Step 4: Write failing validation preregistration tests**

```python
def test_validation_requires_the_registered_top_three_policy() -> None:
    train = _ranking_train_review_fixture()
    changed = replace(
        train,
        registered_validation_policy=replace(
            train.registered_validation_policy,
            daily_limit=5,
        ),
    )

    with pytest.raises(ValueError, match="registered validation policy"):
        build_five_day_ranking_validation_review(_base_review_fixture(), changed)


def test_existing_validation_artifact_is_verified_not_overwritten(
    tmp_path: Path,
) -> None:
    review = _ranking_validation_review_fixture()
    path = write_five_day_ranking_validation(review, tmp_path)
    before = path.read_bytes()

    assert write_five_day_ranking_validation(review, tmp_path) == path
    assert path.read_bytes() == before
```

- [ ] **Step 5: Implement corrected validation review**

Add `FiveDayRankingValidationReview` with parent train/research identities,
policy hash, per-profile `FiveDaySelectedSegment` values, combined portfolio,
`validation_outcomes_read=True`, and `test_outcomes_read=False`.

`build_five_day_ranking_validation_review(...)` must verify exact parents,
split, complete point-in-time coverage, unread test state, and
`REGISTERED_VALIDATION_POLICY`; build calibration only from train outcomes
resolved before validation; evaluate each profile on validation using daily
Top 3 and capacity three; count cumulative admitted samples from both train
folds plus validation; and build the global combined Top-3 portfolio from
qualifying profiles. It must not expose freeze eligibility.

- [ ] **Step 6: Derive the validation filename before reading validation**

```python
def validation_trial_identity(train_identity: str, policy_hash: str) -> str:
    return _sha256({
        "schema": "five-day-ranking-validation-v1",
        "parent_train_identity": train_identity,
        "registered_validation_policy_hash": policy_hash,
    })
```

Write to `ranking-validation-<trial-identity>.json`. This permits a caller to
verify and reuse an existing immutable artifact before loading validation
observations.

- [ ] **Step 7: Add tamper, parent-mismatch, test-leak, and idempotency tests**

Mutate one metric, parent identity, policy hash, or `test_outcomes_read`; every
loader must reject it. Repeated identical writes must remain byte stable.

- [ ] **Step 8: Run and commit artifact support**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_report.py \
  tests/unit/test_five_day_ranking_research.py -q
git add \
  stock_ai/buy_point_selection/five_day_ranking_report.py \
  stock_ai/buy_point_selection/five_day_ranking_research.py \
  tests/unit/test_five_day_ranking_report.py \
  tests/unit/test_five_day_ranking_research.py
git diff --cached --check
git commit -m "feat(stock-ai): persist ranking research trials"
```

---

### Task 5: Expose the Manual Two-Stage Diagnostics CLI

**Files:**
- Create: `scripts/analysis/analyze_five_day_ranking.py`
- Create: `tests/unit/test_analyze_five_day_ranking_cli.py`

**Interfaces:**
- Consumes: base research artifact loaders, Task 4 train/validation builders,
  immutable writers, `validation_trial_identity(...)`, and policy hashing.
- Produces: exactly two manual commands, `diagnose-train` and
  `validate-ranking`.

- [ ] **Step 1: Write failing parser and dispatch tests**

```python
def test_parser_exposes_only_the_two_manual_stages() -> None:
    parser = build_parser()
    actions = next(
        action for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert tuple(actions.choices) == ("diagnose-train", "validate-ranking")
    assert "freeze" not in actions.choices
    assert "test" not in actions.choices
    assert "forward" not in actions.choices


def test_diagnose_train_writes_no_validation_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "research-parent.json"
    parent.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "load_five_day_research", _load_parent_fixture)
    monkeypatch.setattr(cli, "build_five_day_ranking_train_review", _build_train_fixture)

    assert cli.main((
        "diagnose-train",
        "--research-artifact", str(parent),
        "--output-dir", str(tmp_path),
    )) == 0
    assert len(tuple(tmp_path.glob("ranking-train-*.json"))) == 1
    assert tuple(tmp_path.glob("ranking-validation-*.json")) == ()
```

- [ ] **Step 2: Run the CLI test to verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_analyze_five_day_ranking_cli.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement the exact parser surface**

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    diagnose = commands.add_parser("diagnose-train")
    diagnose.add_argument("--research-artifact", type=Path, required=True)
    diagnose.add_argument("--output-dir", type=Path, required=True)

    validate = commands.add_parser("validate-ranking")
    validate.add_argument("--train-artifact", type=Path, required=True)
    validate.add_argument("--research-artifact", type=Path, required=True)
    validate.add_argument("--output-dir", type=Path, required=True)
    return parser
```

Do not add database, network, date-range, freeze, test, forward, notification,
or settlement flags.

- [ ] **Step 4: Dispatch train diagnosis without reading later segments**

For `diagnose-train`, load the parent research artifact, verify its canonical
identity and input fingerprint, require complete point-in-time inputs and
`test_outcomes_read=false`, build the train review, and write exactly one
`ranking-train-<identity>.json` artifact.

- [ ] **Step 5: Dispatch validation with pre-read idempotency**

For `validate-ranking`, load and verify the train artifact first. Derive the
policy hash and validation trial identity from that artifact, then calculate
the target path. If the target exists and verifies against the parent train
identity and policy, return it before loading the base research artifact.
Otherwise load the matching parent, verify the immutable parent identities,
build the validation review once, and write it exclusively.

- [ ] **Step 6: Test mismatch and safe-reuse failures**

Add tests proving that a parent identity mismatch fails before calculation,
an existing valid validation artifact avoids calling the base-research loader,
a conflicting existing artifact is rejected, and error output contains no raw
observations or credentials.

- [ ] **Step 7: Run and commit the CLI**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_analyze_five_day_ranking_cli.py \
  tests/unit/test_five_day_ranking_report.py -q
git add \
  scripts/analysis/analyze_five_day_ranking.py \
  tests/unit/test_analyze_five_day_ranking_cli.py
git diff --cached --check
git commit -m "feat(stock-ai): expose ranking diagnostics"
```

---

### Task 6: Verify Regressions and Run Train Diagnosis Only

**Files:**
- Read: `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
- Generate, but do not stage: `output/research/buy_point_five_day_returns/ranking-train-<identity>.json`

- [ ] **Step 1: Run focused and wider five-day regression tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_profiles.py \
  tests/unit/test_five_day_return_execution.py \
  tests/unit/test_five_day_return_validation.py \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_report.py \
  tests/unit/test_five_day_ranking_research.py \
  tests/unit/test_five_day_ranking_report.py \
  tests/unit/test_analyze_five_day_ranking_cli.py \
  tests/unit/test_research_five_day_return_shadow_cli.py -q
```

- [ ] **Step 2: Run only the train command against the exact parent**

```bash
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking.py diagnose-train \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

This command must not connect to MySQL, make a network request, or create a
validation, freeze, test, forward, settlement, holdings, or memory artifact.

- [ ] **Step 3: Verify train-artifact invariants**

Use the artifact loader, not ad hoc JSON interpretation, and assert:

```python
assert tuple(len(fold.evaluation_dates) for fold in review.folds) == (63, 63)
assert tuple(len(fold.calibration_dates) for fold in review.folds) == (252, 315)
assert review.daily_limits == (1, 3, 5)
assert review.registered_validation_policy.daily_limit == 3
assert review.registered_validation_policy.capacity == 3
assert review.registered_validation_policy.metric_version == "selected-portfolio-v2"
assert review.parent_research_identity == "2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59"
assert review.validation_outcomes_read is False
assert review.test_outcomes_read is False
```

- [ ] **Step 4: Report the train-only findings**

Report fold 1, fold 2, and combined results for each profile and the global
portfolio at Top 1/3/5: admitted sample count, expectancy, profit factor,
Wilson lower bound, stop rate, positive-window ratio, maximum drawdown, and
funnel counts. Then report rank-band monotonicity and the largest deterministic
loss-attribution buckets. Compare the corrected Top-3 train result with the
immutable parent's legacy all-resolved-candidate baseline and attribute the
difference to the changed metric population, not to a rule change. Label all
conclusions descriptive and train-only; do not recommend a strategy change
yet.

- [ ] **Step 5: Prove the implementation acceptance boundary**

```bash
test -z "$(find output/research/buy_point_five_day_returns -maxdepth 1 \
  \( -name 'ranking-validation-*.json' -o -name 'freeze-*.json' \
     -o -name 'test-*.json' -o -name 'forward-*.json' \) -print)"
git status --short
```

Confirm the generated train artifact is ignored or otherwise unstaged, no
validation/test outcomes were read, and no unrelated dirty file was staged.
Stop here and present the train evidence to the user. Running
`validate-ranking` requires a new explicit confirmation after review.

## Stop Conditions

- Stop immediately if the parent research identity or input fingerprint does
  not verify, point-in-time completeness is false, or `test_outcomes_read` is
  true.
- Stop if the 378 train sessions cannot be divided exactly into 252+63+63 or
  if any calibration outcome resolves on or after its fold evaluation start.
- Stop if corrected metrics include an unselected, capacity-rejected,
  not-triggered, missing, pending, or incomplete trade.
- Stop if repeated execution changes an existing immutable artifact's bytes.
- Stop if any implementation command would read validation during
  `diagnose-train`, read test at any stage, or create a formal freeze decision.
- Stop if tests require changing candidate discovery, the ranking key, profile
  definitions, trading costs, thresholds, `TWO_R`, or the split.
- Stop if the worktree would stage `tests/unit/test_buy_point_reference_cninfo.py`,
  a generated artifact, `.env`, holdings, credentials, or personal memory.
