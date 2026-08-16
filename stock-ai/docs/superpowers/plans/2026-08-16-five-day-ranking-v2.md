# Five-Day Ranking V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated, deterministic five-day ranking V2 that evaluates exactly twelve conservative-edge policies on train-only expanding folds, selects at most one qualified policy, and permits one separately confirmed validation trial.

**Architecture:** Extract the existing admission loop without changing V1 ranking behavior, then add a pure V2 policy/scoring/evaluation module, a separate immutable artifact module, and a manual two-command CLI. V2 reuses the existing plans, calibrations, observations, costs, execution, and admitted-only metric evaluator but has new policy and artifact identities.

**Tech Stack:** Python 3.11, frozen dataclasses, `Decimal`, canonical JSON plus SHA-256, argparse, pytest.

## Global Constraints

- Work from `/Users/huan.yu/dev/tools-workspace/stock-ai`.
- Preserve `five-day-ranking-key-v1`, every V1 artifact, and the current V1 CLI.
- Use the immutable parent `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json` only in final train acceptance.
- Keep the exact 378/126/126 split and train folds 252+63+63.
- Do not change candidate discovery, entry, stop, costs, holding period, Top-3 capacity, profiles, or `TWO_R`.
- The policy registry contains exactly twelve policies from the approved design; no runtime flags may alter it.
- Official return metrics contain only selected, triggered, capacity-admitted trades with completed entry and exit.
- Rank-band diagnostics are train-only and cannot enter official portfolio-return metrics.
- Days may select zero to three structures; never backfill after cancellation or failure to trigger.
- Do not read test outcomes or run V2 validation during implementation acceptance.
- Do not add database, network, schedule, notification, holdings, order, advisor-memory, or decision-memory writes.
- Do not use Eastmoney stock diagnosis or the deprecated Eastmoney eight-dimension framework.
- Use TDD for each production behavior and commit every task independently.
- Preserve unrelated dirty-worktree changes. Never stage `tests/unit/test_buy_point_reference_cninfo.py`, `.env`, credentials, holdings, personal memory, or generated artifacts.

## File Map

- Modify `stock_ai/buy_point_selection/five_day_return_validation.py` only to expose the existing admission loop as a reusable pure function; V1 behavior must remain byte-identical.
- Modify `tests/unit/test_five_day_return_validation.py` to prove the refactor preserves V1 selection.
- Create `stock_ai/buy_point_selection/five_day_ranking_v2.py` for the policy registry, point-in-time feature math, ranking, fold evaluation, monotonicity, and unique-winner selection.
- Create `tests/unit/test_five_day_ranking_v2.py` for all V2 pure and train-runtime behavior.
- Create `stock_ai/buy_point_selection/five_day_ranking_v2_report.py` for canonical V2 train/validation artifacts, loaders, writers, and trial identity.
- Create `tests/unit/test_five_day_ranking_v2_report.py` for artifact lineage, tamper, no-outcome, and idempotency behavior.
- Create `scripts/analysis/analyze_five_day_ranking_v2.py` for exactly two manual commands.
- Create `tests/unit/test_analyze_five_day_ranking_v2_cli.py` for CLI surface, dispatch ordering, reuse, sanitization, and no-side-effect behavior.

**Test fixture convention:** Put every named V2 fixture in the test file that
uses it. In `test_five_day_ranking_v2.py`, define `_policy(policy_id)` by
selecting from `build_five_day_v2_policies()`, `_plan(...)` by constructing the
existing `FiveDaySignalCandidate` and `FiveDaySignalPlan`, `_calibration(...)`
by constructing `FiveDayCalibration`, and `_observation_for_plan(...)` by
constructing the existing resolved `FiveDayObservation`. Define `_segment(...)`
with real `FiveDaySegmentMetrics`, `FiveDayPortfolioMetrics`,
`FiveDaySelection`, and `FiveDaySelectedSegment` values. The full-review
fixtures must construct `FiveDayResearchReview` with exactly 378 train, 126
validation, and 126 test sessions. Report tests may use `dataclasses.replace`
on those complete production dataclasses; they must not use mocks for hashes,
lineage, writers, or loaders. CLI tests may monkeypatch only the imported
builder/loader functions named in Task 8.

---

### Task 1: Extract Ranking Admission Without Changing V1

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_return_validation.py`
- Modify: `tests/unit/test_five_day_return_validation.py`

**Interfaces:**
- Consumes: `FiveDayRanking`, `Sequence[FiveDayObservation]`, and `capacity: int`.
- Produces: `admit_five_day_ranking(ranking, observations, *, capacity=3) -> FiveDaySelection`.
- Preserves: `select_five_day_portfolio(...) -> FiveDaySelection` and all V1 payload identities.

- [ ] **Step 1: Write the failing extraction-equivalence test**

```python
def test_admit_precomputed_ranking_matches_v1_selection() -> None:
    plans = tuple(_plan(START, code=f"60000{index}") for index in range(1, 5))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    observations = (
        _observation_for_plan(plans[0], net_return="0.02"),
        _not_triggered_for_plan(plans[1]),
        _observation_for_plan(plans[2], net_return="-0.01"),
        _observation_for_plan(plans[3], net_return="0.50"),
    )
    ranking = rank_five_day_plans(plans, calibrations, daily_limit=3)

    extracted = admit_five_day_ranking(ranking, observations, capacity=3)
    existing = select_five_day_portfolio(
        plans, observations, calibrations, daily_limit=3, capacity=3
    )

    assert extracted == existing
    assert extracted.funnel_counts["ADMITTED_TRADES"] == 2
    assert plans[3] not in extracted.ranking.plans
```

- [ ] **Step 2: Run the test and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_validation.py::test_admit_precomputed_ranking_matches_v1_selection -q
```

Expected: import or name failure for `admit_five_day_ranking`.

- [ ] **Step 3: Extract the admission function**

Move the existing code after `rank_five_day_plans(...)` into:

```python
def admit_five_day_ranking(
    ranking: FiveDayRanking,
    observations: Sequence[FiveDayObservation],
    *,
    capacity: int = 3,
) -> FiveDaySelection:
    if capacity < 0:
        raise ValueError("capacity must not be negative")
    by_plan = {_observation_key(value): value for value in observations}
    counts: Counter[str] = Counter(ranking.rejection_counts)
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
            existing.trade.entry_date is not None
            and existing.trade.entry_date <= entry_date
            and existing.trade.exit is not None
            and existing.trade.exit.actual_exit_date >= entry_date
            for existing in admitted
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

Then make `select_five_day_portfolio(...)` rank once and return
`admit_five_day_ranking(ranking, observations, capacity=capacity)`.

- [ ] **Step 4: Verify V1 behavior and artifact identity**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_validation.py \
  tests/unit/test_five_day_ranking_research.py \
  tests/unit/test_five_day_ranking_report.py -q
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_five_day_ranking.py \
  diagnose-train \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

Expected artifact name remains exactly
`ranking-train-d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3.json`.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock_ai/buy_point_selection/five_day_return_validation.py \
  tests/unit/test_five_day_return_validation.py
git diff --cached --check
git commit -m "refactor(stock-ai): reuse five-day admission"
```

---

### Task 2: Register the Twelve Policies and Conservative Feature Math

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v2.py`
- Create: `tests/unit/test_five_day_ranking_v2.py`

**Interfaces:**
- Produces: `V2Weights`, `FiveDayV2Policy`, `build_five_day_v2_policies()`, `five_day_v2_policy_hash(...)`, `five_day_v2_policy_set_hash()`, `shrink_five_day_edge(...)`, `relative_percentiles(...)`, and `five_day_v2_context_score(...)`.
- Constants: `V2_RANKING_VERSION = "five-day-ranking-key-v2"`, `V2_TRAIN_SCHEMA = "five-day-ranking-v2-train-v1"`, and `V2_POLICY_IDS` in the exact approved order.

- [ ] **Step 1: Write failing registry and math tests**

```python
def test_v2_registry_contains_exactly_the_preregistered_twelve() -> None:
    policies = build_five_day_v2_policies()
    assert tuple(value.policy_id for value in policies) == (
        "EDGE-K30-BASE", "EDGE-K30-STABLE_NEGATIVE",
        "EDGE-K60-BASE", "EDGE-K60-STABLE_NEGATIVE",
        "BALANCED-K30-BASE", "BALANCED-K30-STABLE_NEGATIVE",
        "BALANCED-K60-BASE", "BALANCED-K60-STABLE_NEGATIVE",
        "DOWNSIDE-K30-BASE", "DOWNSIDE-K30-STABLE_NEGATIVE",
        "DOWNSIDE-K60-BASE", "DOWNSIDE-K60-STABLE_NEGATIVE",
    )
    assert all(sum(value.weights.as_tuple()) == 100 for value in policies)
    assert len({five_day_v2_policy_hash(value) for value in policies}) == 12
    assert all(len(five_day_v2_policy_hash(value)) == 64 for value in policies)
    assert len(five_day_v2_policy_set_hash()) == 64


def test_shrinkage_and_percentiles_have_literal_boundaries() -> None:
    assert shrink_five_day_edge(Decimal("0.02"), 30, 30) == Decimal("0.01")
    assert relative_percentiles(
        (Decimal("1"), Decimal("2"), Decimal("2"), Decimal("4")),
        higher_is_better=True,
    ) == (Decimal("0"), Decimal("0.5"), Decimal("0.5"), Decimal("1"))
    assert relative_percentiles(
        (Decimal("7"),), higher_is_better=False
    ) == (Decimal("0.5"),)
```

Add this context test using the test file's complete `_plan(...)` factory:

```python
def test_context_score_uses_only_the_three_literal_signal_time_inputs() -> None:
    best = _plan(
        market_status="ALLOW",
        sector_resonating=True,
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
    )
    middle = _plan(
        market_status="LIMITED",
        sector_resonating=None,
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
    )
    worst = _plan(
        market_status="LIMITED",
        sector_resonating=False,
        resistance_basis="LEVEL_BELOW_2R",
    )

    assert five_day_v2_context_score(best) == Decimal("1")
    assert five_day_v2_context_score(middle) == Decimal("0.5")
    assert five_day_v2_context_score(worst) == Decimal("0")
```

- [ ] **Step 2: Run the new test file and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v2.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement frozen policy types and exact registry**

```python
@dataclass(frozen=True)
class V2Weights:
    edge: int
    wilson: int
    positive_windows: int
    low_mae: int
    low_stop_rate: int
    context: int
    setup_quality: int

    def as_tuple(self) -> tuple[int, ...]:
        return (
            self.edge,
            self.wilson,
            self.positive_windows,
            self.low_mae,
            self.low_stop_rate,
            self.context,
            self.setup_quality,
        )


@dataclass(frozen=True)
class FiveDayV2Policy:
    policy_id: str
    ranking_version: str
    shrinkage_k: int
    gate_mode: str
    weights: V2Weights
```

Build the literal three weight templates and their Cartesian product in the
approved identity order. Reject weights not summing to 100, `k` outside
`{30, 60}`, and gates outside `{BASE, STABLE_NEGATIVE}`. Hash canonical JSON
covering the registry, formulas, gates, and tie-breaker version.

```python
def build_five_day_v2_policies() -> tuple[FiveDayV2Policy, ...]:
    templates = (
        ("EDGE", V2Weights(35, 20, 15, 10, 10, 5, 5)),
        ("BALANCED", V2Weights(25, 20, 15, 15, 15, 5, 5)),
        ("DOWNSIDE", V2Weights(20, 20, 10, 20, 20, 5, 5)),
    )
    return tuple(
        FiveDayV2Policy(
            policy_id=f"{name}-K{k}-{gate}",
            ranking_version=V2_RANKING_VERSION,
            shrinkage_k=k,
            gate_mode=gate,
            weights=weights,
        )
        for name, weights in templates
        for k in (30, 60)
        for gate in ("BASE", "STABLE_NEGATIVE")
    )


def _policy_payload(policy: FiveDayV2Policy) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "ranking_version": policy.ranking_version,
        "shrinkage_k": policy.shrinkage_k,
        "gate_mode": policy.gate_mode,
        "weights": dict(zip(
            (
                "edge", "wilson", "positive_windows", "low_mae",
                "low_stop_rate", "context", "setup_quality",
            ),
            policy.weights.as_tuple(),
            strict=True,
        )),
    }


def five_day_v2_policy_hash(policy: FiveDayV2Policy) -> str:
    return hashlib.sha256(
        json.dumps(
            _policy_payload(policy),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def five_day_v2_policy_set_hash() -> str:
    payload = {
        "policies": [
            _policy_payload(value) for value in build_five_day_v2_policies()
        ],
        "formula_version": "conservative-percentile-v1",
        "tie_breaker_version": "score-edge-quality-code-profile-v1",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
```

- [ ] **Step 4: Implement and verify pure feature functions**

Implement the exact shrinkage and percentile formulas from the design. Reject
negative sample counts, non-positive `k`, and an empty percentile input.
Implement context scoring with `Decimal` only.

```python
def shrink_five_day_edge(
    expectancy: Decimal,
    sample_count: int,
    shrinkage_k: int,
) -> Decimal:
    if sample_count < 0 or shrinkage_k <= 0:
        raise ValueError("invalid shrinkage inputs")
    return (
        Decimal(sample_count)
        / Decimal(sample_count + shrinkage_k)
        * expectancy
    )


def relative_percentiles(
    values: Sequence[Decimal],
    *,
    higher_is_better: bool,
) -> tuple[Decimal, ...]:
    if not values:
        raise ValueError("percentile input must not be empty")
    if len(values) == 1:
        return (Decimal("0.5"),)
    denominator = Decimal(len(values) - 1)
    return tuple(
        (
            Decimal(sum(other < value for other in values))
            + Decimal(sum(other == value for other in values) - 1)
            * Decimal("0.5")
        ) / denominator
        if higher_is_better
        else (
            Decimal(sum(other > value for other in values))
            + Decimal(sum(other == value for other in values) - 1)
            * Decimal("0.5")
        ) / denominator
        for value in values
    )


def five_day_v2_context_score(plan: FiveDaySignalPlan) -> Decimal:
    market = Decimal("1") if plan.candidate.market_status == "ALLOW" else Decimal("0")
    sector = (
        Decimal("1")
        if plan.candidate.sector_resonating is True
        else Decimal("0")
        if plan.candidate.sector_resonating is False
        else Decimal("0.5")
    )
    resistance = (
        Decimal("1")
        if plan.resistance_basis == "LEVEL_AT_OR_ABOVE_2R"
        else Decimal("0.5")
        if plan.resistance_basis == "NO_RELIABLE_LEVEL"
        else Decimal("0")
    )
    return (market + sector + resistance) / Decimal("3")
```

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v2.py -q
```

- [ ] **Step 5: Commit Task 2**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2.py
git diff --cached --check
git commit -m "feat(stock-ai): register conservative ranking policies"
```

---

### Task 3: Score, Collapse, Rank, and Abstain

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v2.py`
- Modify: `tests/unit/test_five_day_ranking_v2.py`

**Interfaces:**
- Consumes: `Sequence[FiveDaySignalPlan]`, `Mapping[str, FiveDayCalibration]`, and one `FiveDayV2Policy`.
- Produces: `V2ScoreComponents`, `FiveDayV2ScoredPlan`, `FiveDayV2RankingResult`, and `rank_five_day_plans_v2(...) -> FiveDayV2RankingResult`.
- `FiveDayV2RankingResult.ranking` is an existing `FiveDayRanking`, consumable by `admit_five_day_ranking(...)` from Task 1.

- [ ] **Step 1: Write failing eligibility and gate tests**

```python
def test_v2_base_gate_rejects_nonpositive_edge_and_weak_profit_factor() -> None:
    result = rank_five_day_plans_v2(
        (negative_edge_plan, weak_pf_plan, eligible_plan),
        calibrations,
        policy=_policy("EDGE-K30-BASE"),
    )
    assert result.ranking.plans == (eligible_plan,)
    assert result.ranking.rejection_counts == {
        "NON_POSITIVE_SHRUNK_EDGE": 1,
        "PROFIT_FACTOR_NOT_ABOVE_ONE": 1,
    }


def test_v2_stable_negative_gate_is_literal_and_unknown_is_not_false() -> None:
    result = rank_five_day_plans_v2(
        (nonresonating, first_launch_pullback, unknown_sector, allowed),
        calibrations,
        policy=_policy("BALANCED-K60-STABLE_NEGATIVE"),
    )
    assert result.ranking.plans == (unknown_sector, allowed)
    assert result.ranking.rejection_counts["STABLE_NEGATIVE_SECTOR"] == 1
    assert result.ranking.rejection_counts["STABLE_NEGATIVE_SETUP"] == 1
```

- [ ] **Step 2: Run the gate tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v2.py \
  -k "base_gate or stable_negative_gate" -q
```

- [ ] **Step 3: Implement point-in-time eligibility and scoring**

Resolve calibrations with `resolve_five_day_calibration(...)`. Apply active-
structure, calibration-date, edge, Profit Factor, and gate-mode checks before
building the seven percentile vectors. Use `Decimal` for every component and
the final score.

```python
@dataclass(frozen=True)
class V2ScoreComponents:
    edge: Decimal
    wilson: Decimal
    positive_windows: Decimal
    low_mae: Decimal
    low_stop_rate: Decimal
    context: Decimal
    setup_quality: Decimal


@dataclass(frozen=True)
class FiveDayV2ScoredPlan:
    plan: FiveDaySignalPlan
    calibration: FiveDayCalibration
    shrunk_edge: Decimal
    components: V2ScoreComponents
    score: Decimal
    rank: int
    selected: bool


@dataclass(frozen=True)
class FiveDayV2RankingResult:
    policy: FiveDayV2Policy
    ranking: FiveDayRanking
    scored: tuple[FiveDayV2ScoredPlan, ...]


def _passes_v2_gate(
    plan: FiveDaySignalPlan,
    calibration: FiveDayCalibration,
    policy: FiveDayV2Policy,
) -> tuple[bool, str | None]:
    edge = shrink_five_day_edge(
        calibration.net_expectancy,
        calibration.triggered_resolved,
        policy.shrinkage_k,
    )
    if edge <= 0:
        return False, "NON_POSITIVE_SHRUNK_EDGE"
    if calibration.profit_factor is None or calibration.profit_factor <= 1:
        return False, "PROFIT_FACTOR_NOT_ABOVE_ONE"
    if policy.gate_mode == "STABLE_NEGATIVE":
        if plan.candidate.sector_resonating is False:
            return False, "STABLE_NEGATIVE_SECTOR"
        if plan.candidate.setup.setup_type is SetupType.FIRST_LAUNCH_PULLBACK:
            return False, "STABLE_NEGATIVE_SETUP"
    return True, None
```

- [ ] **Step 4: Write failing structure-collapse, Top-3, and tie tests**

```python
def test_v2_keeps_one_profile_per_structure_and_never_fills_to_three() -> None:
    result = rank_five_day_plans_v2(
        (same_structure_low, same_structure_high, only_other_structure),
        calibrations,
        policy=_policy("EDGE-K30-BASE"),
        daily_limit=3,
    )
    assert result.ranking.plans == (same_structure_high, only_other_structure)
    assert result.ranking.rejection_counts["DUPLICATE_ACTIVE_STRUCTURE"] == 1
    assert len(result.ranking.plans) == 2


def test_v2_ties_follow_edge_quality_code_and_profile() -> None:
    first = rank_five_day_plans_v2(plans, calibrations, policy=policy)
    second = rank_five_day_plans_v2(
        tuple(reversed(plans)), calibrations, policy=policy
    )
    assert tuple(row.plan for row in first.scored) == (
        plan_600001_profile_a,
        plan_600001_profile_b,
        plan_600002,
    )
    assert first == second
```

- [ ] **Step 5: Implement collapse and deterministic ranking**

Score all eligible variants for one date. Sort them with the literal key
`(-score, -shrunk_edge, -setup_quality, normalized_code, profile_id)` and keep
the first row per existing `_active_structure_key`. Apply the same key to the
structure winners, preserve every ranked row, select only the first
`daily_limit`, and count overflow.

```python
def _v2_sort_key(value: FiveDayV2ScoredPlan) -> tuple[object, ...]:
    return (
        -value.score,
        -value.shrunk_edge,
        -value.components.setup_quality,
        normalize_code6(value.plan.candidate.code),
        value.plan.profile.profile_id,
    )


def _score_signal_date(
    rows: Sequence[tuple[FiveDaySignalPlan, FiveDayCalibration, Decimal]],
    policy: FiveDayV2Policy,
) -> tuple[FiveDayV2ScoredPlan, ...]:
    raw = tuple(
        (
            edge,
            calibration.profitable_interval[0],
            calibration.positive_window_ratio,
            calibration.mae_p75,
            calibration.stop_rate,
            five_day_v2_context_score(plan),
            Decimal(plan.candidate.setup.quality),
        )
        for plan, calibration, edge in rows
    )
    percentiles = tuple(
        relative_percentiles(
            tuple(value[index] for value in raw),
            higher_is_better=index not in (3, 4),
        )
        for index in range(7)
    )
    weights = policy.weights.as_tuple()
    scored = tuple(
        FiveDayV2ScoredPlan(
            plan=plan,
            calibration=calibration,
            shrunk_edge=edge,
            components=V2ScoreComponents(
                edge=percentiles[0][index],
                wilson=percentiles[1][index],
                positive_windows=percentiles[2][index],
                low_mae=percentiles[3][index],
                low_stop_rate=percentiles[4][index],
                context=percentiles[5][index],
                setup_quality=percentiles[6][index],
            ),
            score=sum(
                (
                    Decimal(weight) * percentiles[component][index]
                    for component, weight in enumerate(weights)
                ),
                Decimal("0"),
            ),
            rank=0,
            selected=False,
        )
        for index, (plan, calibration, edge) in enumerate(rows)
    )
    return tuple(sorted(scored, key=_v2_sort_key))


def rank_five_day_plans_v2(
    plans: Sequence[FiveDaySignalPlan],
    calibrations: Mapping[str, FiveDayCalibration],
    *,
    policy: FiveDayV2Policy,
    active_structure_ids: frozenset[str] = frozenset(),
    daily_limit: int = 3,
) -> FiveDayV2RankingResult:
    if daily_limit < 0:
        raise ValueError("daily_limit must not be negative")
    rejections: Counter[str] = Counter()
    eligible_by_date: dict[
        date,
        list[tuple[FiveDaySignalPlan, FiveDayCalibration, Decimal]],
    ] = {}
    for plan in plans:
        if plan.structure_id in active_structure_ids:
            rejections["EXISTING_ACTIVE_STRUCTURE"] += 1
            continue
        calibration = resolve_five_day_calibration(
            calibrations,
            profile_id=plan.profile.profile_id,
            setup_type=plan.candidate.setup.setup_type,
            market_status=plan.candidate.market_status,
            sector_resonating=plan.candidate.sector_resonating,
        )
        if calibration is None:
            rejections["INSUFFICIENT_CALIBRATION"] += 1
            continue
        if calibration.data_end >= plan.candidate.signal_date:
            rejections["CALIBRATION_NOT_POINT_IN_TIME"] += 1
            continue
        edge = shrink_five_day_edge(
            calibration.net_expectancy,
            calibration.triggered_resolved,
            policy.shrinkage_k,
        )
        passed, reason = _passes_v2_gate(plan, calibration, policy)
        if not passed:
            assert reason is not None
            rejections[reason] += 1
            continue
        eligible_by_date.setdefault(
            plan.candidate.signal_date, []
        ).append((plan, calibration, edge))

    selected: list[FiveDaySignalPlan] = []
    traces: list[FiveDayRankedPlan] = []
    scored_rows: list[FiveDayV2ScoredPlan] = []
    for signal_date in sorted(eligible_by_date):
        variants = _score_signal_date(eligible_by_date[signal_date], policy)
        seen: set[tuple[object, ...]] = set()
        structures: list[FiveDayV2ScoredPlan] = []
        for row in variants:
            key = _active_structure_key(row.plan)
            if key in seen:
                rejections["DUPLICATE_ACTIVE_STRUCTURE"] += 1
                continue
            seen.add(key)
            structures.append(row)
        for position, row in enumerate(
            sorted(structures, key=_v2_sort_key), start=1
        ):
            chosen = position <= daily_limit
            ranked_row = replace(row, rank=position, selected=chosen)
            scored_rows.append(ranked_row)
            traces.append(
                FiveDayRankedPlan(
                    plan=row.plan,
                    rank=position,
                    selected=chosen,
                )
            )
            if chosen:
                selected.append(row.plan)
        rejections["DAILY_CANDIDATE_LIMIT"] += max(
            0, len(structures) - daily_limit
        )
    return FiveDayV2RankingResult(
        policy=policy,
        ranking=FiveDayRanking(
            plans=tuple(selected),
            rejection_counts=dict(
                sorted((key, value) for key, value in rejections.items() if value)
            ),
            ranked=tuple(traces),
        ),
        scored=tuple(scored_rows),
    )
```

- [ ] **Step 6: Verify and commit Task 3**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v2.py \
  tests/unit/test_five_day_return_validation.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2.py
git diff --cached --check
git commit -m "feat(stock-ai): rank conservative five-day plans"
```

---

### Task 4: Assess Rank Evidence and Select a Unique Train Winner

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v2.py`
- Modify: `tests/unit/test_five_day_ranking_v2.py`

**Interfaces:**
- Produces: `V2RankBandMetrics`, `V2MonotonicityAssessment`, `FiveDayV2PolicyAssessment`, `build_v2_rank_bands(...)`, `assess_v2_rank_monotonicity(...)`, `assess_five_day_v2_policy(...)`, and `select_five_day_v2_winner(...)`.
- Consumes: fold and combined Top-3 `FiveDaySelectedSegment` values plus triggered-completed rank-band observations.

- [ ] **Step 1: Write failing monotonicity tests**

```python
def test_monotonicity_accepts_the_exact_two_bps_tolerance() -> None:
    result = assess_v2_rank_monotonicity(
        _bands(rank1="0.004", rank2_3="0.006", rank4_5="0.008", rank6="0"),
        admitted_top3_expectancy=Decimal("0.003"),
    )
    assert result.qualifies is True
    assert result.reasons == ()


def test_monotonicity_fails_small_bands_and_top3_below_rank6() -> None:
    result = assess_v2_rank_monotonicity(
        _bands(
            rank1="0.01", rank2_3="0", rank4_5="-0.01",
            rank6="0.004", rank1_n=14,
        ),
        admitted_top3_expectancy=Decimal("0.003"),
    )
    assert result.qualifies is False
    assert result.reasons == (
        "RANK_BAND_SAMPLES_TOO_LOW",
        "TOP3_NOT_ABOVE_RANK6_PLUS",
    )


def test_rank_bands_use_triggered_completed_trace_not_admission() -> None:
    bands = build_v2_rank_bands(
        (
            _scored(plan_rank1, rank=1),
            _scored(plan_rank4, rank=4),
            _scored(plan_rank6, rank=6),
        ),
        (
            _observation_for_plan(plan_rank1, net_return="0.01"),
            _not_triggered_for_plan(plan_rank4),
            _observation_for_plan(plan_rank6, net_return="-0.01"),
        ),
    )
    assert tuple(value.triggered_completed for value in bands) == (1, 0, 0, 1)
    assert bands[0].net_expectancy == Decimal("0.01")
    assert bands[3].net_expectancy == Decimal("-0.01")
```

- [ ] **Step 2: Verify RED and implement monotonicity**

Use only triggered completed observations, require 15 per band, and use
`Decimal("0.002")` tolerance. Keep the assessment separate from official
admitted-trade metrics.

```python
@dataclass(frozen=True)
class V2RankBandMetrics:
    band: str
    triggered_completed: int
    net_expectancy: Decimal


@dataclass(frozen=True)
class V2MonotonicityAssessment:
    bands: tuple[V2RankBandMetrics, ...]
    qualifies: bool
    reasons: tuple[str, ...]


def _v2_plan_key(plan: FiveDaySignalPlan) -> tuple[date, str, str, str]:
    return (
        plan.candidate.signal_date,
        normalize_code6(plan.candidate.code),
        plan.structure_id,
        plan.profile.profile_id,
    )


def build_v2_rank_bands(
    scored: Sequence[FiveDayV2ScoredPlan],
    observations: Sequence[FiveDayObservation],
) -> tuple[V2RankBandMetrics, ...]:
    by_plan = {_v2_plan_key(value.plan): value for value in observations}
    returns: dict[str, list[Decimal]] = {
        "RANK_1": [],
        "RANK_2_3": [],
        "RANK_4_5": [],
        "RANK_6_PLUS": [],
    }
    for row in scored:
        observation = by_plan.get(_v2_plan_key(row.plan))
        if (
            observation is None
            or not _is_resolved(observation)
            or observation.trade.net_return is None
        ):
            continue
        band = (
            "RANK_1" if row.rank == 1
            else "RANK_2_3" if row.rank <= 3
            else "RANK_4_5" if row.rank <= 5
            else "RANK_6_PLUS"
        )
        returns[band].append(observation.trade.net_return)
    return tuple(
        V2RankBandMetrics(
            band=band,
            triggered_completed=len(values),
            net_expectancy=(
                sum(values, Decimal("0")) / Decimal(len(values))
                if values else Decimal("0")
            ),
        )
        for band, values in returns.items()
    )


def assess_v2_rank_monotonicity(
    bands: Sequence[V2RankBandMetrics],
    *,
    admitted_top3_expectancy: Decimal,
) -> V2MonotonicityAssessment:
    by_band = {value.band: value for value in bands}
    reasons: list[str] = []
    if any(value.triggered_completed < 15 for value in bands):
        reasons.append("RANK_BAND_SAMPLES_TOO_LOW")
    tolerance = Decimal("0.002")
    if (
        by_band["RANK_1"].net_expectancy + tolerance
        < by_band["RANK_2_3"].net_expectancy
    ):
        reasons.append("RANK_1_BELOW_RANK_2_3")
    if (
        by_band["RANK_2_3"].net_expectancy + tolerance
        < by_band["RANK_4_5"].net_expectancy
    ):
        reasons.append("RANK_2_3_BELOW_RANK_4_5")
    if admitted_top3_expectancy <= by_band["RANK_6_PLUS"].net_expectancy:
        reasons.append("TOP3_NOT_ABOVE_RANK6_PLUS")
    return V2MonotonicityAssessment(
        bands=tuple(bands),
        qualifies=not reasons,
        reasons=tuple(reasons),
    )
```

- [ ] **Step 3: Write failing qualification and winner-order tests**

```python
def test_policy_requires_both_positive_folds_and_combined_edge() -> None:
    result = assess_five_day_v2_policy(
        policy=_policy("EDGE-K30-BASE"),
        fold1=_segment(samples=15, expectancy="0.001"),
        fold2=_segment(samples=25, expectancy="0"),
        combined=_segment(
            samples=40, expectancy="0.003", profit_factor="1.11"
        ),
        monotonicity=_passing_monotonicity(),
    )
    assert result.qualifies is False
    assert "FOLD_2_NON_POSITIVE_EXPECTANCY" in result.reasons


def test_winner_maximizes_worst_fold_before_combined_expectancy() -> None:
    high_combined = _assessment(
        policy_id="EDGE-K30-BASE",
        fold1_expectancy="0.001",
        fold2_expectancy="0.004",
        combined_expectancy="0.005",
    )
    high_worst_fold = _assessment(
        policy_id="BALANCED-K30-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
    )
    winner = select_five_day_v2_winner((high_combined, high_worst_fold))
    assert winner is not None
    assert winner.policy.policy_id == "BALANCED-K30-BASE"


def test_winner_uses_samples_drawdown_then_registered_policy_order() -> None:
    fewer_samples = _assessment(
        policy_id="EDGE-K30-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
        combined_samples=40,
        maximum_drawdown="0.07",
    )
    more_samples = _assessment(
        policy_id="EDGE-K60-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
        combined_samples=41,
        maximum_drawdown="0.09",
    )
    lower_drawdown = _assessment(
        policy_id="BALANCED-K60-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
        combined_samples=41,
        maximum_drawdown="0.08",
    )
    later_policy = _assessment(
        policy_id="DOWNSIDE-K60-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
        combined_samples=41,
        maximum_drawdown="0.08",
    )
    winner = select_five_day_v2_winner(
        (fewer_samples, later_policy, lower_drawdown, more_samples)
    )
    assert winner is not None
    assert winner.policy.policy_id == "BALANCED-K60-BASE"
```

Add literal boundary coverage:

```python
@pytest.mark.parametrize(
    ("overrides", "reason"),
    (
        ({"fold1_samples": 14}, "FOLD_1_SAMPLES_TOO_LOW"),
        ({"fold2_samples": 14}, "FOLD_2_SAMPLES_TOO_LOW"),
        ({"combined_samples": 39}, "COMBINED_SAMPLES_TOO_LOW"),
        ({"combined_expectancy": "0.0029"}, "COMBINED_EDGE_TOO_LOW"),
        ({"combined_profit_factor": "1.10"}, "PROFIT_FACTOR_NOT_ABOVE_1_10"),
    ),
)
def test_v2_policy_qualification_boundaries(
    overrides: dict[str, object], reason: str
) -> None:
    result = assess_five_day_v2_policy(
        **_qualifying_assessment_inputs(**overrides)
    )
    assert result.qualifies is False
    assert reason in result.reasons


def test_v2_policy_accepts_inclusive_and_exclusive_boundaries() -> None:
    result = assess_five_day_v2_policy(
        **_qualifying_assessment_inputs(
            fold1_samples=15,
            fold2_samples=15,
            combined_samples=40,
            combined_expectancy="0.0030",
            combined_profit_factor="1.1001",
        )
    )
    assert result.qualifies is True
```

- [ ] **Step 4: Implement assessment and unique selection**

Return `None` when no assessment qualifies. Never relax a threshold or select
an unqualified fallback.

```python
@dataclass(frozen=True)
class FiveDayV2PolicyAssessment:
    policy: FiveDayV2Policy
    fold1: FiveDaySelectedSegment
    fold2: FiveDaySelectedSegment
    combined: FiveDaySelectedSegment
    monotonicity: V2MonotonicityAssessment
    worst_fold_expectancy: Decimal
    qualifies: bool
    reasons: tuple[str, ...]


def assess_five_day_v2_policy(
    *,
    policy: FiveDayV2Policy,
    fold1: FiveDaySelectedSegment,
    fold2: FiveDaySelectedSegment,
    combined: FiveDaySelectedSegment,
    monotonicity: V2MonotonicityAssessment,
) -> FiveDayV2PolicyAssessment:
    reasons: list[str] = []
    for label, value in (("FOLD_1", fold1), ("FOLD_2", fold2)):
        if value.selection.incomplete:
            reasons.append(f"{label}_INCOMPLETE")
        if value.metrics.triggered_resolved < 15:
            reasons.append(f"{label}_SAMPLES_TOO_LOW")
        if value.metrics.net_expectancy <= 0:
            reasons.append(f"{label}_NON_POSITIVE_EXPECTANCY")
    if combined.selection.incomplete:
        reasons.append("COMBINED_INCOMPLETE")
    if combined.metrics.triggered_resolved < 40:
        reasons.append("COMBINED_SAMPLES_TOO_LOW")
    if combined.metrics.net_expectancy < Decimal("0.003"):
        reasons.append("COMBINED_EDGE_TOO_LOW")
    if (
        combined.metrics.profit_factor is None
        or combined.metrics.profit_factor <= Decimal("1.10")
    ):
        reasons.append("PROFIT_FACTOR_NOT_ABOVE_1_10")
    reasons.extend(monotonicity.reasons)
    return FiveDayV2PolicyAssessment(
        policy=policy,
        fold1=fold1,
        fold2=fold2,
        combined=combined,
        monotonicity=monotonicity,
        worst_fold_expectancy=min(
            fold1.metrics.net_expectancy,
            fold2.metrics.net_expectancy,
        ),
        qualifies=not reasons,
        reasons=tuple(reasons),
    )


def select_five_day_v2_winner(
    assessments: Sequence[FiveDayV2PolicyAssessment],
) -> FiveDayV2PolicyAssessment | None:
    qualified = tuple(value for value in assessments if value.qualifies)
    if not qualified:
        return None
    return min(
        qualified,
        key=lambda value: (
            -value.worst_fold_expectancy,
            -value.combined.metrics.net_expectancy,
            -value.combined.metrics.triggered_resolved,
            value.combined.metrics.maximum_drawdown,
            V2_POLICY_IDS.index(value.policy.policy_id),
        ),
    )
```

- [ ] **Step 5: Verify and commit Task 4**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v2.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2.py
git diff --cached --check
git commit -m "feat(stock-ai): qualify conservative rankings"
```

---

### Task 5: Build the Complete Train-Only V2 Review

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v2.py`
- Modify: `tests/unit/test_five_day_ranking_v2.py`

**Interfaces:**
- Produces: `FiveDayV2Fold`, `FiveDayV2VariantReview`, `FiveDayRankingV2TrainReview`, `v2_fold_specs(...)`, and `build_five_day_ranking_v2_train_review(research, *, parent_research_identity) -> FiveDayRankingV2TrainReview`.
- The review contains all twelve policies, fold and combined Top-1/3/5 segments, rank bands, funnels, assessments, policy-set hash, and `winner_policy_id: str | None`.
- `FiveDayRankingV2TrainReview.status` is exactly
  `TRAIN_CANDIDATE_SELECTED` when a winner exists and `NO_TRAIN_CANDIDATE`
  otherwise.

- [ ] **Step 1: Write the failing fold and train-only test**

```python
def test_v2_train_review_uses_exact_folds_and_all_twelve_policies() -> None:
    result = build_five_day_ranking_v2_train_review(
        _complete_review_fixture(),
        parent_research_identity="a" * 64,
    )
    assert tuple(len(value.calibration_dates) for value in result.folds) == (
        252, 315,
    )
    assert tuple(len(value.evaluation_dates) for value in result.folds) == (
        63, 63,
    )
    assert len(result.assessments) == 12
    assert len(result.variants) == 12 * 3 * 3
    assert result.policy_set_hash == five_day_v2_policy_set_hash()
    assert result.validation_outcomes_read is False
    assert result.test_outcomes_read is False
```

- [ ] **Step 2: Run the exact test and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v2.py::test_v2_train_review_uses_exact_folds_and_all_twelve_policies -q
```

- [ ] **Step 3: Implement the expanding-fold runtime**

For each fold, use only calibration candidates resolving before evaluation
start. Build existing calibrations, run all twelve policies for Top 1, 3, and
5, pass each precomputed ranking to `admit_five_day_ranking`, and evaluate it
with `evaluate_five_day_selection_segment`. Combine only the two non-
overlapping evaluation selections. Build rank bands from each policy's full
scored trace, assess policies, and select at most one winner.

```python
@dataclass(frozen=True)
class FiveDayV2Fold:
    fold_id: str
    calibration_dates: tuple[date, ...]
    evaluation_dates: tuple[date, ...]
    calibration_data_end: date
    excluded_unresolved_calibration_rows: int


@dataclass(frozen=True)
class FiveDayV2VariantReview:
    fold_id: str
    policy_id: str
    daily_limit: int
    scored: tuple[FiveDayV2ScoredPlan, ...]
    segment: FiveDaySelectedSegment


@dataclass(frozen=True)
class FiveDayRankingV2TrainReview:
    schema: str
    ranking_version: str
    parent_research_identity: str
    parent_input_fingerprint: str
    split: ChronologicalSplit
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    sizing_version: str
    evaluator_version: str
    cost_version: str
    policy_set_hash: str
    policies: tuple[FiveDayV2Policy, ...]
    folds: tuple[FiveDayV2Fold, ...]
    variants: tuple[FiveDayV2VariantReview, ...]
    assessments: tuple[FiveDayV2PolicyAssessment, ...]
    winner_policy_id: str | None
    winner_policy_hash: str | None
    winner_train_samples: int
    status: str
    validation_eligible: bool
    validation_outcomes_read: bool
    test_outcomes_read: bool
    promotion_eligible: bool
    trade_permission: str


def v2_fold_specs(train_dates: Sequence[date]) -> tuple[FiveDayV2Fold, ...]:
    dates = tuple(train_dates)
    if len(dates) != 378:
        raise ValueError("ranking v2 requires exactly 378 train sessions")
    return (
        FiveDayV2Fold(
            fold_id="train-fold-1",
            calibration_dates=dates[:252],
            evaluation_dates=dates[252:315],
            calibration_data_end=dates[251],
            excluded_unresolved_calibration_rows=0,
        ),
        FiveDayV2Fold(
            fold_id="train-fold-2",
            calibration_dates=dates[:315],
            evaluation_dates=dates[315:378],
            calibration_data_end=dates[314],
            excluded_unresolved_calibration_rows=0,
        ),
    )


def combine_v2_selections(
    selections: Sequence[FiveDaySelection],
) -> FiveDaySelection:
    ranking_counts: Counter[str] = Counter()
    funnel_counts: Counter[str] = Counter()
    for selection in selections:
        ranking_counts.update(selection.ranking.rejection_counts)
        funnel_counts.update(selection.funnel_counts)
    return FiveDaySelection(
        ranking=FiveDayRanking(
            plans=tuple(
                plan for selection in selections
                for plan in selection.ranking.plans
            ),
            rejection_counts=dict(sorted(ranking_counts.items())),
            ranked=tuple(
                row for selection in selections
                for row in selection.ranking.ranked
            ),
        ),
        selected_observations=tuple(
            row for selection in selections
            for row in selection.selected_observations
        ),
        admitted=tuple(
            row for selection in selections for row in selection.admitted
        ),
        funnel_counts=dict(sorted(funnel_counts.items())),
        incomplete=any(selection.incomplete for selection in selections),
    )


if len(parent_research_identity) != 64 or any(
    value not in "0123456789abcdef" for value in parent_research_identity
):
    raise ValueError("parent research identity must be a sha256 digest")
if not research.point_in_time_complete or research.test_outcomes_read:
    raise ValueError("base research review is incomplete or test-tainted")
if tuple(
    len(values)
    for values in (
        research.split.train,
        research.split.validation,
        research.split.test,
    )
) != (378, 126, 126):
    raise ValueError("ranking v2 requires the 378/126/126 split")
train_dates = tuple(research.split.train)
train_set = frozenset(train_dates)
train_observations = tuple(
    value for value in research.observations
    if value.plan.candidate.signal_date in train_set
)
folds: list[FiveDayV2Fold] = []
for base_fold in v2_fold_specs(train_dates):
    calibration_candidates = tuple(
        value for value in train_observations
        if value.plan.candidate.signal_date in base_fold.calibration_dates
    )
    boundary = base_fold.evaluation_dates[0]
    folds.append(replace(
        base_fold,
        excluded_unresolved_calibration_rows=sum(
            not _is_resolved(value) or value.resolution_date >= boundary
            for value in calibration_candidates
        ),
    ))
variants: list[FiveDayV2VariantReview] = []
for fold in folds:
    boundary = fold.evaluation_dates[0]
    calibration_observations = tuple(
        value
        for value in train_observations
        if value.plan.candidate.signal_date in fold.calibration_dates
        and _is_resolved(value)
        and value.resolution_date < boundary
    )
    calibrations = build_five_day_calibrations(
        calibration_observations,
        trading_dates=fold.calibration_dates,
    )
    evaluation_observations = tuple(
        value
        for value in train_observations
        if value.plan.candidate.signal_date in fold.evaluation_dates
    )
    for policy in build_five_day_v2_policies():
        for daily_limit in (1, 3, 5):
            ranked = rank_five_day_plans_v2(
                tuple(value.plan for value in evaluation_observations),
                calibrations,
                policy=policy,
                daily_limit=daily_limit,
            )
            selection = admit_five_day_ranking(
                ranked.ranking,
                evaluation_observations,
                capacity=3,
            )
            variants.append(
                FiveDayV2VariantReview(
                    fold_id=fold.fold_id,
                    policy_id=policy.policy_id,
                    daily_limit=daily_limit,
                    scored=ranked.scored,
                    segment=evaluate_five_day_selection_segment(
                        profile_id="GLOBAL",
                        segment=fold.fold_id,
                        selection=selection,
                        trading_dates=fold.evaluation_dates,
                        cumulative_samples=len(selection.admitted),
                        required_samples=0,
                        required_cumulative_samples=0,
                    ),
                )
            )

for policy in build_five_day_v2_policies():
    for daily_limit in (1, 3, 5):
        fold_values = tuple(
            value for value in variants
            if value.policy_id == policy.policy_id
            and value.daily_limit == daily_limit
            and value.fold_id in ("train-fold-1", "train-fold-2")
        )
        combined_selection = combine_v2_selections(
            tuple(value.segment.selection for value in fold_values)
        )
        variants.append(
            FiveDayV2VariantReview(
                fold_id="train-combined",
                policy_id=policy.policy_id,
                daily_limit=daily_limit,
                scored=tuple(
                    row for value in fold_values for row in value.scored
                ),
                segment=evaluate_five_day_selection_segment(
                    profile_id="GLOBAL",
                    segment="train-combined",
                    selection=combined_selection,
                    trading_dates=tuple(
                        day for fold in folds for day in fold.evaluation_dates
                    ),
                    cumulative_samples=len(combined_selection.admitted),
                    required_samples=0,
                    required_cumulative_samples=0,
                ),
            )
        )

assessments: list[FiveDayV2PolicyAssessment] = []
for policy in build_five_day_v2_policies():
    top3 = {
        value.fold_id: value
        for value in variants
        if value.policy_id == policy.policy_id and value.daily_limit == 3
    }
    band_rows = tuple(
        row
        for fold_id in ("train-fold-1", "train-fold-2")
        for row in top3[fold_id].scored
    )
    bands = build_v2_rank_bands(band_rows, train_observations)
    monotonicity = assess_v2_rank_monotonicity(
        bands,
        admitted_top3_expectancy=(
            top3["train-combined"].segment.metrics.net_expectancy
        ),
    )
    assessments.append(
        assess_five_day_v2_policy(
            policy=policy,
            fold1=top3["train-fold-1"].segment,
            fold2=top3["train-fold-2"].segment,
            combined=top3["train-combined"].segment,
            monotonicity=monotonicity,
        )
    )
winner = select_five_day_v2_winner(assessments)
return FiveDayRankingV2TrainReview(
    schema=V2_TRAIN_SCHEMA,
    ranking_version=V2_RANKING_VERSION,
    parent_research_identity=parent_research_identity,
    parent_input_fingerprint=research.input_fingerprint,
    split=research.split,
    formal_rule_version=research.formal_rule_version,
    formal_policy_hash=research.formal_policy_hash,
    profile_matrix_hash=research.profile_matrix_hash,
    sizing_version=research.sizing_version,
    evaluator_version=research.evaluator_version,
    cost_version=research.cost_version,
    policy_set_hash=five_day_v2_policy_set_hash(),
    policies=build_five_day_v2_policies(),
    folds=tuple(folds),
    variants=tuple(variants),
    assessments=tuple(assessments),
    winner_policy_id=(winner.policy.policy_id if winner else None),
    winner_policy_hash=(
        five_day_v2_policy_hash(winner.policy) if winner else None
    ),
    winner_train_samples=(
        winner.combined.metrics.triggered_resolved if winner else 0
    ),
    status=(
        "TRAIN_CANDIDATE_SELECTED" if winner else "NO_TRAIN_CANDIDATE"
    ),
    validation_eligible=winner is not None,
    validation_outcomes_read=False,
    test_outcomes_read=False,
    promotion_eligible=False,
    trade_permission="NO-TRADE",
)
```

- [ ] **Step 4: Add leakage, incompleteness, and no-winner tests**

```python
def test_v2_train_excludes_calibration_outcome_at_fold_start() -> None:
    result = build_five_day_ranking_v2_train_review(
        _review_with_boundary_resolution(),
        parent_research_identity="a" * 64,
    )
    assert result.folds[0].excluded_unresolved_calibration_rows == 1
    assert (
        result.folds[0].calibration_data_end
        < result.folds[0].evaluation_dates[0]
    )


def test_v2_train_records_no_candidate_without_validation_eligibility() -> None:
    result = build_five_day_ranking_v2_train_review(
        _all_losing_review_fixture(),
        parent_research_identity="a" * 64,
    )
    assert result.winner_policy_id is None
    assert result.status == "NO_TRAIN_CANDIDATE"
    assert all(not value.qualifies for value in result.assessments)


def test_v2_train_rejects_incomplete_policy_and_never_reads_later_splits() -> None:
    research = _review_with_incomplete_train_selection()
    result = build_five_day_ranking_v2_train_review(
        research,
        parent_research_identity="a" * 64,
    )
    affected = next(
        value
        for value in result.assessments
        if value.policy.policy_id == "EDGE-K30-BASE"
    )
    later_dates = frozenset((*research.split.validation, *research.split.test))
    assert affected.qualifies is False
    assert any("INCOMPLETE" in reason for reason in affected.reasons)
    assert all(
        row.plan.candidate.signal_date not in later_dates
        for variant in result.variants
        for row in variant.scored
    )
```

- [ ] **Step 5: Verify and commit Task 5**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v2.py \
  tests/unit/test_five_day_return_validation.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2.py
git diff --cached --check
git commit -m "feat(stock-ai): evaluate ranking v2 on train"
```

---

### Task 6: Persist Immutable V2 Train Evidence

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v2_report.py`
- Create: `tests/unit/test_five_day_ranking_v2_report.py`

**Interfaces:**
- Produces: `FiveDayRankingV2TrainArtifact`, `five_day_ranking_v2_train_payload(...)`, `write_five_day_ranking_v2_train(...)`, and `load_five_day_ranking_v2_train(...)`.
- Filename: `ranking-v2-train-<artifact-identity>.json`.
- `FiveDayRankingV2TrainArtifact` exposes `artifact_identity`,
  `parent_research_identity`, `parent_input_fingerprint`, `policy_set_hash`,
  `winner_policy_id: str | None`, `winner_policy_hash: str | None`,
  `validation_eligible: bool`, and the verified aggregate `payload`.

- [ ] **Step 1: Write the failing canonical-artifact test**

```python
def test_v2_train_artifact_is_canonical_complete_and_outcome_safe(
    tmp_path,
) -> None:
    review = _v2_train_review_fixture()
    payload = five_day_ranking_v2_train_payload(review)
    path = write_five_day_ranking_v2_train(review, tmp_path)
    before = path.read_bytes()

    assert payload["schema"] == "five-day-ranking-v2-train-v1"
    assert payload["ranking_version"] == "five-day-ranking-key-v2"
    assert len(payload["policies"]) == 12
    assert len(payload["variants"]) == 108
    assert payload["validation_outcomes_read"] is False
    assert payload["test_outcomes_read"] is False
    assert payload["promotion_eligible"] is False
    assert "observations" not in _nested_keys(payload)
    assert write_five_day_ranking_v2_train(review, tmp_path) == path
    assert path.read_bytes() == before
```

- [ ] **Step 2: Run and verify module-import RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v2_report.py -q
```

- [ ] **Step 3: Implement payload, exclusive writer, and strict loader**

Hash all aggregate content and lineage. Store deterministic plan keys,
scores, components, ranks, selection, admission, funnels, bands, assessments,
and winner identity, but no raw observations. A no-winner artifact remains
valid evidence with `validation_eligible=false`.

```python
def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _primitive(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {
            field.name: _primitive(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _primitive(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_primitive(item) for item in value]
    if isinstance(value, (date, Decimal, Enum)):
        return value.value if isinstance(value, Enum) else str(value)
    return value


def _write_exclusive_or_verify(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("immutable ranking v2 artifact content mismatch")


def _v2_train_content(
    review: FiveDayRankingV2TrainReview,
) -> dict[str, object]:
    content = _primitive(review)
    if not isinstance(content, dict):
        raise TypeError("train review must serialize to an object")
    return content


def five_day_ranking_v2_train_payload(
    review: FiveDayRankingV2TrainReview,
) -> dict[str, object]:
    content = _v2_train_content(review)
    if (
        content["validation_outcomes_read"] is not False
        or content["test_outcomes_read"] is not False
        or content["promotion_eligible"] is not False
        or len(content["policies"]) != 12
        or len(content["variants"]) != 108
    ):
        raise ValueError("ranking v2 train artifact safety mismatch")
    return {**content, "artifact_identity": _sha256(content)}


@dataclass(frozen=True)
class FiveDayRankingV2TrainArtifact:
    artifact_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    policy_set_hash: str
    winner_policy_id: str | None
    winner_policy_hash: str | None
    winner_train_samples: int
    validation_eligible: bool
    payload: Mapping[str, object]


def write_five_day_ranking_v2_train(
    review: FiveDayRankingV2TrainReview,
    output_dir: Path,
) -> Path:
    payload = five_day_ranking_v2_train_payload(review)
    path = output_dir / f"ranking-v2-train-{payload['artifact_identity']}.json"
    content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    _write_exclusive_or_verify(path, content)
    return path


def load_five_day_ranking_v2_train(
    path: Path,
    *,
    expected_parent_research_identity: str | None = None,
) -> FiveDayRankingV2TrainArtifact:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        identity = payload["artifact_identity"]
        content = {
            key: value for key, value in payload.items()
            if key != "artifact_identity"
        }
        winner_id = payload["winner_policy_id"]
        policies = payload["policies"]
        winner = next(
            (value for value in policies if value["policy_id"] == winner_id),
            None,
        )
        expected_winner_hash = _sha256(winner) if winner is not None else None
        valid = (
            identity == _sha256(content)
            and path.name == f"ranking-v2-train-{identity}.json"
            and payload["schema"] == V2_TRAIN_SCHEMA
            and payload["ranking_version"] == V2_RANKING_VERSION
            and payload["policy_set_hash"] == five_day_v2_policy_set_hash()
            and len(policies) == 12
            and len(payload["variants"]) == 108
            and payload["winner_policy_hash"] == expected_winner_hash
            and payload["validation_eligible"] is (winner_id is not None)
            and payload["validation_outcomes_read"] is False
            and payload["test_outcomes_read"] is False
            and payload["promotion_eligible"] is False
            and (
                expected_parent_research_identity is None
                or payload["parent_research_identity"]
                == expected_parent_research_identity
            )
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        valid = False
    if not valid:
        raise ValueError("five-day ranking v2 train artifact is invalid")
    return FiveDayRankingV2TrainArtifact(
        artifact_identity=identity,
        parent_research_identity=payload["parent_research_identity"],
        parent_input_fingerprint=payload["parent_input_fingerprint"],
        policy_set_hash=payload["policy_set_hash"],
        winner_policy_id=winner_id,
        winner_policy_hash=payload["winner_policy_hash"],
        winner_train_samples=int(payload["winner_train_samples"]),
        validation_eligible=payload["validation_eligible"],
        payload=payload,
    )
```

- [ ] **Step 4: Add recomputed-hash tamper tests**

```python
@pytest.mark.parametrize(
    ("mutate", "rehash"),
    (
        (
            lambda value: value["policies"][0]["weights"].update(edge=34),
            True,
        ),
        (
            lambda value: value["variants"][0]["segment"]["metrics"].update(
                net_expectancy="9"
            ),
            False,
        ),
        (lambda value: value.update(parent_research_identity="b" * 64), True),
        (lambda value: value.update(winner_policy_id="NOT-REGISTERED"), True),
        (lambda value: value.update(validation_eligible=False), True),
        (lambda value: value.update(test_outcomes_read=True), True),
    ),
)
def test_v2_train_loader_rejects_rehashed_semantic_tampering(
    tmp_path: Path,
    mutate: Callable[[dict[str, object]], object],
    rehash: bool,
) -> None:
    payload = five_day_ranking_v2_train_payload(_v2_train_review_fixture())
    mutate(payload)
    content = {
        key: value for key, value in payload.items()
        if key != "artifact_identity"
    }
    if rehash:
        payload["artifact_identity"] = _sha256(content)
    path = tmp_path / f"ranking-v2-train-{payload['artifact_identity']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        ValueError, match="five-day ranking v2 train artifact is invalid"
    ):
        load_five_day_ranking_v2_train(
            path,
            expected_parent_research_identity="a" * 64,
        )
```

- [ ] **Step 5: Verify and commit Task 6**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v2_report.py \
  tests/unit/test_five_day_ranking_v2.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v2_report.py \
  tests/unit/test_five_day_ranking_v2_report.py
git diff --cached --check
git commit -m "feat(stock-ai): persist ranking v2 train evidence"
```

---

### Task 7: Add the Unique-Winner One-Shot Validation Artifact

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v2.py`
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v2_report.py`
- Modify: `tests/unit/test_five_day_ranking_v2.py`
- Modify: `tests/unit/test_five_day_ranking_v2_report.py`

**Interfaces:**
- Produces: `FiveDayRankingV2ValidationReview`, `build_five_day_ranking_v2_validation_review(research, train, *, parent_research_identity)`, `v2_validation_trial_identity(...)`, `write_five_day_ranking_v2_validation(...)`, and `load_five_day_ranking_v2_validation(...)`.
- Filename: `ranking-v2-validation-<trial-identity>.json`.

- [ ] **Step 1: Write failing no-winner and policy-lock tests**

```python
def test_v2_validation_requires_exactly_one_frozen_train_winner() -> None:
    with pytest.raises(ValueError, match="unique train winner"):
        build_five_day_ranking_v2_validation_review(
            _base_research_fixture(),
            _train_artifact_without_winner(),
            parent_research_identity="a" * 64,
        )


def test_v2_validation_rejects_changed_winner_policy_before_outcomes() -> None:
    changed = replace(
        _qualified_train_artifact(),
        winner_policy_id="DOWNSIDE-K60-STABLE_NEGATIVE",
    )
    with pytest.raises(ValueError, match="winner policy or lineage"):
        build_five_day_ranking_v2_validation_review(
            _base_research_fixture(),
            changed,
            parent_research_identity="a" * 64,
        )
```

- [ ] **Step 2: Verify RED and implement winner-only validation**

Load the exact policy from the verified train payload. Build calibrations only
from train observations resolved before validation starts. Rank and admit only
that policy at Top 3 and capacity 3. Evaluate existing formal segment and
portfolio thresholds unchanged. Set validation-read true and test-read false;
expose no freeze or production eligibility.

```python
@dataclass(frozen=True)
class FiveDayRankingV2ValidationReview:
    schema: str
    trial_identity: str
    parent_train_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    winner_policy_id: str
    winner_policy_hash: str
    validation_dates: tuple[date, ...]
    segment: FiveDaySelectedSegment
    qualifies_for_test_design: bool
    reasons: tuple[str, ...]
    validation_outcomes_read: bool
    test_outcomes_read: bool
    promotion_eligible: bool
    trade_permission: str


def v2_validation_trial_identity(
    train_identity: str,
    winner_policy_hash: str,
) -> str:
    return _sha256({
        "schema": "five-day-ranking-v2-validation-v1",
        "parent_train_identity": train_identity,
        "winner_policy_hash": winner_policy_hash,
    })


def build_five_day_ranking_v2_validation_review(
    research: FiveDayResearchReview,
    train: FiveDayRankingV2TrainArtifact,
    *,
    parent_research_identity: str,
) -> FiveDayRankingV2ValidationReview:
    if (
        not train.validation_eligible
        or train.winner_policy_id is None
        or train.winner_policy_hash is None
    ):
        raise ValueError("ranking v2 validation requires a unique train winner")
    policy = next(
        (
            value for value in build_five_day_v2_policies()
            if value.policy_id == train.winner_policy_id
        ),
        None,
    )
    if (
        policy is None
        or five_day_v2_policy_hash(policy) != train.winner_policy_hash
        or train.parent_research_identity != parent_research_identity
        or train.parent_input_fingerprint != research.input_fingerprint
        or train.payload["split"] != {
            "train": [value.isoformat() for value in research.split.train],
            "validation": [
                value.isoformat() for value in research.split.validation
            ],
            "test": [value.isoformat() for value in research.split.test],
        }
        or not research.point_in_time_complete
        or research.test_outcomes_read
    ):
        raise ValueError("ranking v2 winner policy or lineage mismatch")
    validation_start = research.split.validation[0]
    validation_end = research.split.validation[-1]
    train_dates = frozenset(research.split.train)
    validation_dates = frozenset(research.split.validation)
    calibration_rows = tuple(
        value for value in research.observations
        if value.plan.candidate.signal_date in train_dates
        and _is_resolved(value)
        and value.resolution_date < validation_start
    )
    calibrations = build_five_day_calibrations(
        calibration_rows,
        trading_dates=research.split.train,
    )
    observations = tuple(
        value for value in research.observations
        if value.plan.candidate.signal_date in validation_dates
        and (not _is_resolved(value) or value.resolution_date <= validation_end)
    )
    ranked = rank_five_day_plans_v2(
        tuple(value.plan for value in observations),
        calibrations,
        policy=policy,
        daily_limit=3,
    )
    selection = admit_five_day_ranking(
        ranked.ranking,
        observations,
        capacity=3,
    )
    prior_samples = train.winner_train_samples
    segment = evaluate_five_day_selection_segment(
        profile_id="GLOBAL",
        segment="validation",
        selection=selection,
        trading_dates=research.split.validation,
        cumulative_samples=prior_samples + len(selection.admitted),
        required_samples=30,
        required_cumulative_samples=70,
    )
    reasons = tuple((*segment.metrics.reasons, *segment.portfolio.reasons))
    return FiveDayRankingV2ValidationReview(
        schema="five-day-ranking-v2-validation-v1",
        trial_identity=v2_validation_trial_identity(
            train.artifact_identity,
            train.winner_policy_hash,
        ),
        parent_train_identity=train.artifact_identity,
        parent_research_identity=parent_research_identity,
        parent_input_fingerprint=research.input_fingerprint,
        winner_policy_id=policy.policy_id,
        winner_policy_hash=train.winner_policy_hash,
        validation_dates=tuple(research.split.validation),
        segment=segment,
        qualifies_for_test_design=not reasons,
        reasons=reasons,
        validation_outcomes_read=True,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )
```

- [ ] **Step 3: Write failing identity and idempotency tests**

```python
def test_v2_validation_identity_is_available_before_validation_read() -> None:
    train = _qualified_train_artifact()
    first = v2_validation_trial_identity(
        train.artifact_identity, train.winner_policy_hash
    )
    second = v2_validation_trial_identity(
        train.artifact_identity, train.winner_policy_hash
    )
    assert first == second
    assert len(first) == 64


def test_v2_validation_writer_never_overwrites_a_conflict(tmp_path) -> None:
    review = _validation_review_fixture()
    path = write_five_day_ranking_v2_validation(review, tmp_path)
    before = path.read_bytes()
    assert write_five_day_ranking_v2_validation(review, tmp_path) == path
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="immutable ranking v2 artifact"):
        write_five_day_ranking_v2_validation(
            replace(review, parent_research_identity="c" * 64), tmp_path
        )
```

- [ ] **Step 4: Add loader and formal-threshold boundary tests**

```python
@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    (
        ({"validation_samples": 29}, "INSUFFICIENT_SAMPLES"),
        ({"cumulative_samples": 69}, "INSUFFICIENT_CUMULATIVE_SAMPLES"),
        ({"expectancy": "0"}, "NON_POSITIVE_EXPECTANCY"),
        ({"profit_factor": "1.10"}, "PROFIT_FACTOR_TOO_LOW"),
        ({"wilson": "0.4499"}, "WILSON_LOWER_TOO_LOW"),
        ({"stop_rate": "0.4001"}, "STOP_RATE_TOO_HIGH"),
        ({"positive_windows": "0.5999"}, "POSITIVE_WINDOW_RATIO_TOO_LOW"),
        ({"drawdown": "0.1001"}, "MAXIMUM_DRAWDOWN_TOO_HIGH"),
        ({"stock_trade_share": "0.1001"}, "STOCK_TRADE_CONCENTRATION_TOO_HIGH"),
        ({"stock_profit_share": "0.1501"}, "STOCK_PROFIT_CONCENTRATION_TOO_HIGH"),
        ({"sector_trade_share": "0.3501"}, "SECTOR_TRADE_CONCENTRATION_TOO_HIGH"),
        ({"sector_profit_share": "0.4001"}, "SECTOR_PROFIT_CONCENTRATION_TOO_HIGH"),
        ({"top5_profit_share": "0.3501"}, "TOP5_PROFIT_CONCENTRATION_TOO_HIGH"),
    ),
)
def test_v2_validation_formal_thresholds(
    overrides: dict[str, object], expected_reason: str
) -> None:
    review = build_five_day_ranking_v2_validation_review(
        _validation_research_fixture(**overrides),
        _qualified_train_artifact(),
        parent_research_identity="a" * 64,
    )
    assert review.qualifies_for_test_design is False
    assert expected_reason in review.reasons


def test_v2_validation_inclusive_boundaries_pass() -> None:
    review = build_five_day_ranking_v2_validation_review(
        _validation_research_fixture(
            validation_samples=30,
            cumulative_samples=70,
            expectancy="0.0001",
            profit_factor="1.1001",
            wilson="0.45",
            stop_rate="0.40",
            positive_windows="0.60",
            drawdown="0.10",
            stock_trade_share="0.10",
            stock_profit_share="0.15",
            sector_trade_share="0.35",
            sector_profit_share="0.40",
            top5_profit_share="0.35",
        ),
        _qualified_train_artifact(),
        parent_research_identity="a" * 64,
    )
    assert review.qualifies_for_test_design is True
```

Implement validation payload/writer/loader with `_primitive`, `_sha256`, and
`_write_exclusive_or_verify` from Task 6. The loader recomputes the payload
hash, requires the filename trial identity, verifies the supplied parent train
identity and winner-policy hash, and rejects any true `test_outcomes_read` or
`promotion_eligible` flag:

```python
def write_five_day_ranking_v2_validation(
    review: FiveDayRankingV2ValidationReview,
    output_dir: Path,
) -> Path:
    content = _primitive(review)
    if not isinstance(content, dict):
        raise TypeError("validation review must serialize to an object")
    payload = {**content, "artifact_identity": _sha256(content)}
    path = output_dir / (
        f"ranking-v2-validation-{review.trial_identity}.json"
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    _write_exclusive_or_verify(path, serialized)
    return path


def load_five_day_ranking_v2_validation(
    path: Path,
    *,
    expected_train_identity: str,
    expected_policy_hash: str,
) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        identity = payload.pop("artifact_identity")
        valid = (
            identity == _sha256(payload)
            and payload["schema"] == "five-day-ranking-v2-validation-v1"
            and payload["trial_identity"]
            == v2_validation_trial_identity(
                expected_train_identity, expected_policy_hash
            )
            and path.name
            == f"ranking-v2-validation-{payload['trial_identity']}.json"
            and payload["parent_train_identity"] == expected_train_identity
            and payload["winner_policy_hash"] == expected_policy_hash
            and payload["validation_outcomes_read"] is True
            and payload["test_outcomes_read"] is False
            and payload["promotion_eligible"] is False
            and payload["trade_permission"] == "NO-TRADE"
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        valid = False
    if not valid:
        raise ValueError("five-day ranking v2 validation artifact is invalid")
    return {**payload, "artifact_identity": identity}
```

- [ ] **Step 5: Verify and commit Task 7**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2_report.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v2.py \
  stock_ai/buy_point_selection/five_day_ranking_v2_report.py \
  tests/unit/test_five_day_ranking_v2.py \
  tests/unit/test_five_day_ranking_v2_report.py
git diff --cached --check
git commit -m "feat(stock-ai): validate one ranking v2 policy"
```

---

### Task 8: Expose the Separate Manual V2 CLI

**Files:**
- Create: `scripts/analysis/analyze_five_day_ranking_v2.py`
- Create: `tests/unit/test_analyze_five_day_ranking_v2_cli.py`

**Interfaces:**
- Consumes: the existing base-research loader and Task-5 through Task-7 builders, loaders, and writers.
- Produces: exactly `diagnose-train` and `validate-ranking` subcommands.

- [ ] **Step 1: Write the failing parser and train-dispatch tests**

```python
def test_v2_parser_exposes_only_two_manual_stages() -> None:
    parser = cli.build_parser()
    subparsers = next(
        action for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert tuple(subparsers.choices) == (
        "diagnose-train", "validate-ranking",
    )
    assert {
        "--database-url", "--freeze", "--test", "--forward", "--notify",
    }.isdisjoint(_option_strings(parser))


def test_v2_diagnose_train_writes_no_later_stage_artifact(tmp_path) -> None:
    parent = write_five_day_research(_research_review_fixture(), tmp_path)
    assert cli.main((
        "diagnose-train",
        "--research-artifact", str(parent),
        "--output-dir", str(tmp_path),
    )) == 0
    assert len(tuple(tmp_path.glob("ranking-v2-train-*.json"))) == 1
    assert tuple(tmp_path.glob("ranking-v2-validation-*.json")) == ()
```

- [ ] **Step 2: Run the CLI tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_analyze_five_day_ranking_v2_cli.py -q
```

- [ ] **Step 3: Implement exact CLI and pre-read validation reuse**

Both commands require explicit artifact and output paths. `diagnose-train`
verifies the canonical parent and writes one V2 train artifact. Validation
loads train first; a no-winner train returns exit code 2 without loading the
parent. For a winner, derive the validation filename first and reuse a valid
existing artifact before loading the parent.

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    diagnose = commands.add_parser("diagnose-train")
    diagnose.add_argument("--research-artifact", type=Path, required=True)
    diagnose.add_argument("--output-dir", type=Path, required=True)
    validate = commands.add_parser("validate-ranking")
    validate.add_argument("--train-artifact", type=Path, required=True)
    validate.add_argument("--research-artifact", type=Path, required=True)
    validate.add_argument("--output-dir", type=Path, required=True)
    return parser


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise ValueError("required artifact does not exist")
    return path


def dispatch_command(args: argparse.Namespace) -> Path:
    if args.command == "diagnose-train":
        research = load_five_day_research(
            _require_file(args.research_artifact)
        )
        parent_identity = str(
            five_day_research_payload(research)["artifact_identity"]
        )
        if not research.point_in_time_complete or research.test_outcomes_read:
            raise ValueError("research artifact is not train-safe")
        review = build_five_day_ranking_v2_train_review(
            research,
            parent_research_identity=parent_identity,
        )
        return write_five_day_ranking_v2_train(review, args.output_dir)

    train = load_five_day_ranking_v2_train(
        _require_file(args.train_artifact)
    )
    if (
        not train.validation_eligible
        or train.winner_policy_id is None
        or train.winner_policy_hash is None
    ):
        raise ValueError("ranking v2 train artifact has no winner")
    trial = v2_validation_trial_identity(
        train.artifact_identity,
        train.winner_policy_hash,
    )
    validation_path = (
        args.output_dir / f"ranking-v2-validation-{trial}.json"
    )
    if validation_path.is_file():
        load_five_day_ranking_v2_validation(
            validation_path,
            expected_train_identity=train.artifact_identity,
            expected_policy_hash=train.winner_policy_hash,
        )
        return validation_path
    research = load_five_day_research(
        _require_file(args.research_artifact)
    )
    parent_identity = str(
        five_day_research_payload(research)["artifact_identity"]
    )
    if parent_identity != train.parent_research_identity:
        raise ValueError("ranking v2 parent lineage mismatch")
    review = build_five_day_ranking_v2_validation_review(
        research,
        train,
        parent_research_identity=parent_identity,
    )
    return write_five_day_ranking_v2_validation(review, args.output_dir)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        path = dispatch_command(build_parser().parse_args(argv))
    except (OSError, RuntimeError, TypeError, ValueError):
        print("五日排名V2诊断失败", file=sys.stderr)
        return 2
    print(path)
    return 0
```

- [ ] **Step 4: Add ordering, conflict, and sanitized-error tests**

```python
def test_v2_no_winner_stops_before_loading_research(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_five_day_ranking_v2_train", lambda _: _no_winner())
    monkeypatch.setattr(
        cli,
        "load_five_day_research",
        lambda _: pytest.fail("research outcomes must not be read"),
    )
    assert cli.main(_validate_argv()) == 2


def test_v2_existing_validation_reuses_before_loading_research(
    monkeypatch, tmp_path
) -> None:
    train = _qualified_train_artifact()
    path = _write_valid_existing_validation(train, tmp_path)
    monkeypatch.setattr(cli, "load_five_day_ranking_v2_train", lambda _: train)
    monkeypatch.setattr(
        cli,
        "load_five_day_research",
        lambda _: pytest.fail("research outcomes must not be reread"),
    )
    assert cli.main(_validate_argv(tmp_path)) == 0
    assert path.is_file()


def test_v2_cli_sanitizes_dependency_details(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "dispatch_command",
        lambda _: (_ for _ in ()).throw(
            ValueError("mysql://user:password@host/raw-observation")
        ),
    )
    assert cli.main(("diagnose-train", "--research-artifact", "x", "--output-dir", "y")) == 2
    assert capsys.readouterr().err == "五日排名V2诊断失败\n"
```

- [ ] **Step 5: Verify and commit Task 8**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_analyze_five_day_ranking_v2_cli.py \
  tests/unit/test_five_day_ranking_v2_report.py -q
git add scripts/analysis/analyze_five_day_ranking_v2.py \
  tests/unit/test_analyze_five_day_ranking_v2_cli.py
git diff --cached --check
git commit -m "feat(stock-ai): expose ranking v2 diagnostics"
```

---

### Task 9: Verify Regressions and Run V2 Train Diagnosis Only

**Files:**
- Read: `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
- Generate but never stage: `output/research/buy_point_five_day_returns/ranking-v2-train-<identity>.json`

**Interfaces:**
- Consumes: the committed V2 CLI and immutable parent.
- Produces: one ignored train-only V2 evidence file and a descriptive report.

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
  tests/unit/test_research_five_day_return_shadow_cli.py -q
```

- [ ] **Step 2: Snapshot output and run only V2 train**

```bash
find output/research/buy_point_five_day_returns -maxdepth 1 -type f -print | sort
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking_v2.py diagnose-train \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

- [ ] **Step 3: Verify train invariants with the strict loader**

Assert exact parent identity, policy-set hash, twelve policies, 108 variants,
252/315 calibration sessions, 63/63 evaluation sessions, complete point-in-
time coverage, admitted-only metric counts, false validation/test read flags,
false promotion, and either one winner or `NO_TRAIN_CANDIDATE`.

- [ ] **Step 4: Prove idempotency and acceptance boundaries**

Hash the V2 train file, rerun the identical command, and require the same
hash. Require no V2 validation, freeze, test, forward, settlement, holdings,
memory, or staged artifact. Confirm V1 artifact identity remains
`d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3`.

- [ ] **Step 5: Report and stop**

Report all twelve policy rejection reasons, fold and combined Top-3 results,
Top-1/5 sensitivity, rank-band evidence, funnels, the winner or
`NO_TRAIN_CANDIDATE`, and comparison with V1. Label evidence train-only and
descriptive. Do not run `validate-ranking`; request a new explicit user
confirmation if and only if a unique train winner exists.
