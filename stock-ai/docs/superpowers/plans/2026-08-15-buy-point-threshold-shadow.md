# Buy-Point Threshold Shadow Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-share, full-universe threshold-shadow workflow that tests 48 single-boundary setup relaxations, freezes only precision-qualified profiles on two research windows, and evaluates the frozen profiles once on the August holdout.

**Architecture:** A pure `threshold_shadow_research.py` module owns profile construction, shadow setup generation, point-in-time replay, and zero-share candidates. A separate `threshold_shadow_evaluation.py` module owns outcome wrappers, profile metrics, qualification, immutable freeze models, and daily Top-5 selection. `threshold_shadow_report.py` serializes stage-specific immutable artifacts, while one CLI orchestrates `research`, `freeze`, and `test` using the existing read-only case input loader and v5 recall lineage.

**Tech Stack:** Python 3.11, frozen dataclasses, `Decimal`, existing buy-point gates/detectors/planner/simulator, SQLAlchemy-backed read-only case inputs, deterministic JSON/Markdown, pytest.

## Global Constraints

- Rule version remains exactly `buy-point-selection-3.1.0`.
- Generate exactly 48 profiles: 16 supported fields times literal rates `0.10`, `0.25`, and `0.50`.
- Each profile changes exactly one numeric `SelectionPolicy` field.
- Structural and hard-coded conditions remain unrelaxed.
- Production `patterns.py`, default `SelectionPolicy`, gates, planning, sizing, validation, holdings, decision memory, notifications, and orders remain unchanged.
- Signal generation uses point-in-time data only; future bars participate only in outcome evaluation.
- The two research windows are July 20–24 and July 27–31, 2026; the one-time holdout is August 3–7, 2026.
- A profile requires at least 10 triggered resolved outcomes, positive mean net return, positive-net-return rate at least 50%, and stop-first rate no greater than 40%.
- The frozen daily basket contains zero to five deduplicated stocks and never fills from failed profiles.
- Existing v5 files remain immutable; the new schema is exactly `buy-point-threshold-shadow-v1`.
- Every shadow setup, candidate, plan wrapper, and report row is `CASE_ANALYSIS_ONLY / NO-TRADE` with `executable_shares=0`.
- Incomplete announcement coverage blocks promotion even when case evidence is generated.
- MySQL access is read-only; `192.168.1.13:3306` is a runtime override and is never committed.
- Generated research artifacts remain ignored by Git.
- Use RED-GREEN tests for every behavior change and commit only scoped files.
- Run project commands from `/Users/huan.yu/dev/tools-workspace/stock-ai`; Git
  commits use the repository root only when escalation is required.

## File Map

- Create `stock_ai/buy_point_selection/threshold_shadow_research.py`: profile matrix, diagnostic matching, shadow setup generation, full-universe replay, rejection audit, and candidate deduplication primitives.
- Create `stock_ai/buy_point_selection/threshold_shadow_evaluation.py`: outcome wrappers, primary metrics, profile qualification/ranking, frozen profile model/hash, Top-5 selection, and auxiliary recall comparison.
- Create `stock_ai/buy_point_selection/threshold_shadow_report.py`: v1 payloads, identities, Markdown, exclusive-or-verify writes, and artifact loaders.
- Create `scripts/analysis/review_buy_point_threshold_shadows.py`: `research`, `freeze`, and `test` CLI orchestration plus v5 lineage and input fingerprint validation.
- Modify `stock_ai/buy_point_selection/recall_research.py`: expose all six setup-window diagnostics and the launch quiet-price metric without changing the existing closest-template API.
- Modify `docs/CAPABILITIES.md`: document the manual research command and its non-trading boundary.
- Create `tests/unit/test_buy_point_threshold_shadow_research.py`.
- Create `tests/unit/test_buy_point_threshold_shadow_evaluation.py`.
- Create `tests/unit/test_buy_point_threshold_shadow_report.py`.
- Create `tests/unit/test_review_buy_point_threshold_shadows_cli.py`.
- Modify `tests/unit/test_buy_point_recall_research.py` for all-window diagnostic parity.

---

### Task 1: Build the frozen 48-profile matrix and all-window diagnostics

**Files:**
- Create: `stock_ai/buy_point_selection/threshold_shadow_research.py`
- Modify: `stock_ai/buy_point_selection/recall_research.py`
- Create: `tests/unit/test_buy_point_threshold_shadow_research.py`
- Modify: `tests/unit/test_buy_point_recall_research.py`

**Interfaces:**
- Consumes: `SelectionPolicy`, `SetupType`, signal-time `BuyPointBar` rows, and the existing three production detector functions.
- Produces: `ThresholdProfile`, `ThresholdShadowSetup`, `build_threshold_profiles(policy=None)`, `profile_matrix_hash(profiles)`, `diagnose_setup_windows(code, signal_date, bars, policy=None)`, and `generate_threshold_shadow_setups(code, signal_date, bars, profiles, formal_policy=None)`.

- [ ] **Step 1: Write the failing literal profile-matrix test**

Add a test that imports the wished-for API and asserts exact cardinality, identity, direction, and values:

```python
def test_profile_matrix_has_48_unique_single_field_relaxations() -> None:
    profiles = build_threshold_profiles()

    assert len(profiles) == 48
    assert len({value.profile_id for value in profiles}) == 48
    profile = next(
        value
        for value in profiles
        if value.policy_field == "platform_width_max"
        and value.relaxation_rate == Decimal("0.10")
    )
    assert profile == ThresholdProfile(
        profile_id="PRE_BREAKOUT:platform_width_max:UPPER:0.10",
        setup_type=SetupType.PRE_BREAKOUT,
        policy_field="platform_width_max",
        direction="UPPER",
        relaxation_rate=Decimal("0.10"),
        formal_value=Decimal("0.12"),
        shadow_value=Decimal("0.1320"),
        failure_reason="PLATFORM_WIDTH_WIDE",
        metric_name="platform_width",
    )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_threshold_shadow_research.py::test_profile_matrix_has_48_unique_single_field_relaxations
```

Expected: collection fails because `threshold_shadow_research` does not exist.

- [ ] **Step 3: Add immutable profile models and the literal field specification**

Implement frozen models with these exact fields:

```python
@dataclass(frozen=True)
class ThresholdProfile:
    profile_id: str
    setup_type: SetupType
    policy_field: str
    direction: str
    relaxation_rate: Decimal
    formal_value: Decimal
    shadow_value: Decimal
    failure_reason: str
    metric_name: str


@dataclass(frozen=True)
class ThresholdShadowSetup:
    code: str
    signal_date: date
    profile: ThresholdProfile
    setup: DetectedSetup
    actual_deviation: Decimal
    executable_shares: int = 0
```

Define one private literal table for the 16 design-approved fields. Validate that `direction` is `UPPER` or `LOWER`, the formal value is finite and positive, the profile changes only its named field under `dataclasses.replace`, and all profile IDs are unique. `profile_matrix_hash` must hash a canonical sorted JSON representation of every field above.

- [ ] **Step 4: Verify the matrix test is GREEN and add lower-bound coverage**

Add a literal assertion that `trend_return10_min` at 25% changes `0.05` to `0.0375` while every other `SelectionPolicy` field equals the formal policy. Run the entire new module and expect both tests to pass.

- [ ] **Step 5: Write failing all-window diagnostic tests**

Extend recall tests to require six rows in stable order:

```python
rows = diagnose_setup_windows("600001", SIGNAL_DATE, bars)
assert [(value.template, value.window_sessions) for value in rows] == [
    ("PRE_BREAKOUT", 30),
    ("TREND_PULLBACK", 2),
    ("TREND_PULLBACK", 3),
    ("TREND_PULLBACK", 4),
    ("FIRST_LAUNCH_PULLBACK", 1),
    ("FIRST_LAUNCH_PULLBACK", 2),
]
assert diagnose_no_setup("600001", SIGNAL_DATE, bars) == (
    rows[0],
    min(rows[1:4], key=_expected_closest_key),
    min(rows[4:6], key=_expected_closest_key),
)
```

Add a launch fixture assertion for `metrics["quiet_max_abs_gain"]` using a hand-derived literal decimal.

- [ ] **Step 6: Run the all-window test and verify RED**

Expected: import failure for `diagnose_setup_windows` or missing `quiet_max_abs_gain`.

- [ ] **Step 7: Expose all diagnostics without changing closest-template behavior**

Implement `diagnose_setup_windows` by bounding bars to `trade_date <= signal_date`, calling the existing private platform diagnostic once, trend diagnostics for 2/3/4 sessions, and launch diagnostics for 1/2 sessions. Refactor `diagnose_no_setup` to select from those six rows with its existing `(len(failures), boundary_deviation, window_sessions)` key. Add `quiet_max_abs_gain` to launch metrics and calculate `LAUNCH_QUIET_PRICE_LOUD` deviation with `_above_deviation` rather than the current Boolean `1`.

- [ ] **Step 8: Add profile admission RED tests**

Create literal fixtures proving:

- a platform whose only formal failure is width `0.13` is admitted by the 10% `platform_width_max` profile;
- the same bars are not admitted by an unrelated amount profile;
- a formal-positive platform is excluded from incremental shadows;
- a platform with width failure plus falling MA20 is excluded;
- a future bar after `signal_date` cannot change generated shadows; and
- each returned setup has `executable_shares == 0`.

- [ ] **Step 9: Implement strict diagnostic-to-profile matching**

`generate_threshold_shadow_setups` must:

1. bound and sort at most 120 bars through the signal date;
2. group profiles by setup type;
3. require the formal detector for that type to return `None`;
4. run the type-specific detector with the one-field replaced policy;
5. identify the matching formal diagnostic window from the relaxed setup's `pullback_sessions` or `quiet_sessions` metric;
6. require `failures == (profile.failure_reason,)`;
7. calculate direction-specific deviation from `profile.metric_name` and `formal_value`;
8. require a finite `0 < actual_deviation <= relaxation_rate`; and
9. sort output by `(profile_id, code)`.

Use a private detector mapping to call only `detect_pre_breakout`, `detect_trend_pullback`, or `detect_first_launch_pullback`; never call `detect_setups` with a relaxed policy.

- [ ] **Step 10: Run profile and recall tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_threshold_shadow_research.py \
  tests/unit/test_buy_point_recall_research.py \
  tests/unit/test_buy_point_patterns.py
```

Expected: all pass and existing production-positive detector fixtures remain unchanged.

- [ ] **Step 11: Commit profile generation**

```bash
git add stock_ai/buy_point_selection/threshold_shadow_research.py \
  stock_ai/buy_point_selection/recall_research.py \
  tests/unit/test_buy_point_threshold_shadow_research.py \
  tests/unit/test_buy_point_recall_research.py
git commit -m "feat(stock-ai): generate threshold shadow setups"
```

---

### Task 2: Replay shadow candidates through every unchanged downstream gate

**Files:**
- Modify: `stock_ai/buy_point_selection/threshold_shadow_research.py`
- Modify: `tests/unit/test_buy_point_threshold_shadow_research.py`

**Interfaces:**
- Consumes: the exact input bundle used by `replay_case_signals`, a sequence of `ThresholdProfile`, and signal-time setup generation from Task 1.
- Produces: `ThresholdShadowCandidate`, `ThresholdShadowRejection`,
  `ThresholdShadowReplay`, and this interface:

```python
def replay_threshold_shadows(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
    holding_codes_by_date: Mapping[date, frozenset[str]],
    profiles: Sequence[ThresholdProfile],
    formal_policy: SelectionPolicy | None = None,
    setup_generator: Callable[
        [str, date, Sequence[BuyPointBar], Sequence[ThresholdProfile], SelectionPolicy],
        tuple[ThresholdShadowSetup, ...],
    ] = generate_threshold_shadow_setups,
) -> ThresholdShadowReplay:
```

- [ ] **Step 1: Write the failing complete-pipeline test**

Build one signal date with complete coverage, allowing market, complete sector membership, no holdings or VETO flags, a single admitted shadow setup, and a valid 2R plan. Assert:

```python
replay = replay_threshold_shadows(
    signal_dates=(SIGNAL_DATE,),
    trading_dates=TRADING_DATES,
    bars_by_code={"600001": bars},
    memberships=memberships,
    risk_flags=(),
    coverage_by_date={SIGNAL_DATE: complete_coverage},
    market_snapshots={SIGNAL_DATE: allowing_market},
    holding_codes_by_date={SIGNAL_DATE: frozenset()},
    profiles=(profile,),
    setup_generator=literal_setup_generator,
)
candidate = replay.candidates[0]
assert candidate.profile_id == profile.profile_id
assert candidate.code == "600001"
assert candidate.signal_date == SIGNAL_DATE
assert candidate.executable_shares == 0
assert candidate.status == "CASE_ANALYSIS_ONLY"
assert candidate.trade_permission == "NO-TRADE"
assert candidate.plan.maximum_shares >= 100
```

Inject `setup_generator` as a keyword-only callable in this unit test so the gate pipeline is tested independently from detector fixtures.

- [ ] **Step 2: Run the focused test and verify RED**

Expected: import failure for `replay_threshold_shadows`.

- [ ] **Step 3: Add replay models**

Implement:

```python
@dataclass(frozen=True)
class ThresholdShadowCandidate:
    code: str
    signal_date: date
    profile_id: str
    shadow_setup: ThresholdShadowSetup
    plan: PricePlan
    average_amount5_qian: Decimal
    two_r_space_buffer: Decimal
    executable_shares: int = 0
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"


@dataclass(frozen=True)
class ThresholdShadowRejection:
    code: str
    signal_date: date
    profile_id: str | None
    stage: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ThresholdShadowReplay:
    signal_dates: tuple[date, ...]
    incomplete_dates: tuple[date, ...]
    raw_setups: tuple[ThresholdShadowSetup, ...]
    candidates: tuple[ThresholdShadowCandidate, ...]
    rejections: tuple[ThresholdShadowRejection, ...]
```

Reject any candidate wrapper whose setup or candidate executable shares differ from zero.

- [ ] **Step 4: Implement point-in-time setup generation followed by unchanged gates**

Use this explicit research order without changing production code:

1. coverage and latest-bar completeness;
2. `base_gate` with point-in-time holdings and risk flags;
3. Task 1 shadow setup generation and raw-hit recording;
4. `classify_market`;
5. `anti_chase_gate` using signal-time returns and MA distances;
6. point-in-time sector membership and `sector_gate`;
7. `build_price_plan` with `CASE_RISK_BUDGET`, formal policy, and `second_trading_date_after`; and
8. 2R-space buffer as `nearest_resistance_above(trigger, bars) - target_2r`.

Use `_sector_snapshots` from the existing historical runtime exactly as
`replay_case_signals` does. Generating raw setups before applying an otherwise
complete but weak market snapshot permits market-hidden-shape diagnostics; the
market gate still prevents every such row from becoming a candidate. A relaxed
policy is used only inside Task 1 detector invocation; every gate and plan
receives the formal policy.

- [ ] **Step 5: Add one RED test per fail-closed boundary**

Add and observe failing tests for:

- market freeze preserves raw setup hits but produces no candidate and records
  a `MARKET` rejection for every profile hit;
- existing holding and VETO produce base rejections;
- anti-chase failure rejects all profiles for that code-date;
- sector missing and sector weak reject;
- insufficient 2R space rejects;
- incomplete coverage marks the date incomplete; and
- a bar after the signal date cannot affect the replay.

Assert each rejection has a literal stage and reason and that no rejected row appears in `candidates`.

- [ ] **Step 6: Implement minimal rejection auditing and deterministic sorting**

Sort raw setups by `(signal_date, code, profile_id)`, candidates by the same key, and rejections by `(signal_date, code, profile_id or "", stage, reasons)`. Record one rejection per failed code/profile where the profile is known; market/base failures may use `profile_id=None` because profile generation was never reached.

- [ ] **Step 7: Run replay and production regression tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_threshold_shadow_research.py \
  tests/unit/test_buy_point_case_review.py \
  tests/unit/test_buy_point_gates.py \
  tests/unit/test_buy_point_planning.py
```

Expected: all pass.

- [ ] **Step 8: Commit full-universe replay**

```bash
git add stock_ai/buy_point_selection/threshold_shadow_research.py \
  tests/unit/test_buy_point_threshold_shadow_research.py
git commit -m "feat(stock-ai): replay threshold shadows"
```

---

### Task 3: Evaluate outcomes, qualify profiles, freeze ranks, and select daily Top 5

**Files:**
- Create: `stock_ai/buy_point_selection/threshold_shadow_evaluation.py`
- Create: `tests/unit/test_buy_point_threshold_shadow_evaluation.py`

**Interfaces:**
- Consumes: Task 2 candidates, complete future bars, v5 exact-date winner keys, the profile-matrix hash, training artifact identities, and risk coverage status.
- Produces: `ThresholdShadowOutcome`, `ThresholdProfileMetrics`,
  `FrozenThresholdProfile`, `ThresholdProfileFreeze`,
  `ExactRecallComparison`, and these interfaces:

```python
def evaluate_threshold_outcomes(
    candidates: Sequence[ThresholdShadowCandidate],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    *,
    outcome_cutoff: date,
    costs: ExecutionCosts | None = None,
) -> tuple[ThresholdShadowOutcome, ...]:

def aggregate_profile_metrics(
    candidate_profile_ids: Sequence[str],
    outcomes: Sequence[ThresholdShadowOutcome],
) -> tuple[ThresholdProfileMetrics, ...]:

def freeze_threshold_profiles(
    *,
    profiles: Sequence[ThresholdProfile],
    training_identities: Sequence[str],
    metrics: Sequence[ThresholdProfileMetrics],
    formal_rule_version: str,
    formal_policy_hash: str,
    profile_matrix_hash: str,
    risk_coverage_complete: bool,
) -> ThresholdProfileFreeze:

def select_frozen_daily_candidates(
    candidates: Sequence[ThresholdShadowCandidate],
    freeze: ThresholdProfileFreeze,
    *,
    maximum_per_date: int = 5,
) -> tuple[ThresholdShadowCandidate, ...]:

def compare_exact_recall(
    selected: Sequence[ThresholdShadowCandidate],
    winner_keys: Collection[tuple[date, str]],
    formal_keys: Collection[tuple[date, str]],
) -> ExactRecallComparison:
```

- [ ] **Step 1: Write the failing cost-adjusted outcome wrapper test**

Build one candidate and five literal outcome bars, then assert the wrapper preserves profile identity and the existing evaluator result:

```python
row = evaluate_threshold_outcomes(
    (candidate,),
    {"600001": bars},
    outcome_cutoff=date(2026, 7, 31),
)[0]
assert row.profile_id == candidate.profile_id
assert row.code == "600001"
assert row.outcome.net_return == expected_net_return
assert row.executable_shares == 0
```

- [ ] **Step 2: Run the test and verify RED**

Expected: module import failure.

- [ ] **Step 3: Add outcome and metric models plus evaluator adapter**

Implement:

```python
@dataclass(frozen=True)
class ThresholdShadowOutcome:
    profile_id: str
    code: str
    signal_date: date
    outcome: CaseOutcome
    executable_shares: int = 0


@dataclass(frozen=True)
class ThresholdProfileMetrics:
    profile_id: str
    candidate_count: int
    triggered: int
    resolved: int
    positive_net: int
    stop_first: int
    mean_net_return: Decimal | None
    median_net_return: Decimal | None
    positive_net_rate: Decimal | None
    stop_first_rate: Decimal | None
    mean_mfe: Decimal | None
    mean_mae: Decimal | None
    qualifies: bool
    qualification_reasons: tuple[str, ...]
```

Adapt `ThresholdShadowCandidate` to an ephemeral `CaseCandidate` and call the existing `evaluate_case_plan` with unchanged `ExecutionCosts`. Never duplicate simulator math.

- [ ] **Step 4: Write metric boundary RED tests**

Use literal outcomes to assert:

- 9 resolved triggers always fail `MINIMUM_RESOLVED_TRIGGERED`;
- 10 rows with positive mean, 5 positive-net rows, and 4 stop-first rows qualify at exact boundaries;
- mean `0`, positive rate below `0.50`, or stop-first above `0.40` each has its exact rejection reason;
- non-triggered rows count as candidates but not resolved triggers; and
- mean/median/MFE/MAE reconcile with literal decimals.

- [ ] **Step 5: Implement deterministic profile metrics and qualification**

Count candidates from the repeated `candidate_profile_ids` sequence. Aggregate
only outcomes with `trigger_date is not None` and `net_return is not None` for
resolved-trigger metrics. Define positive net literally as `net_return > 0`.
Sort values before median calculation. Produce reasons in this exact order:

```text
MINIMUM_RESOLVED_TRIGGERED
MEAN_NET_RETURN_NOT_POSITIVE
POSITIVE_NET_RATE_BELOW_HALF
STOP_FIRST_RATE_ABOVE_40_PERCENT
```

- [ ] **Step 6: Write failing immutable-freeze tests**

Assert two research identities are required and sorted, only qualifying profiles appear, ranks follow the specified total order, incomplete risk coverage sets `promotion_eligible=False`, and no qualifiers produce `profiles=()` plus `empty=True`.

Define models:

```python
@dataclass(frozen=True)
class FrozenThresholdProfile:
    profile_id: str
    rank: int
    training_metrics: ThresholdProfileMetrics


@dataclass(frozen=True)
class ThresholdProfileFreeze:
    schema: str
    training_identities: tuple[str, str]
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    profiles: tuple[FrozenThresholdProfile, ...]
    empty: bool
    risk_coverage_complete: bool
    promotion_eligible: bool
    freeze_hash: str
```

- [ ] **Step 7: Implement freeze validation and canonical hash**

Require exactly two distinct research identities and reject any metrics profile absent from the frozen 48-profile matrix. Rank qualifiers by descending mean net return, descending positive-net rate, ascending stop-first rate, ascending relaxation rate, then profile ID. Hash every model field except `freeze_hash` through canonical sorted JSON. `promotion_eligible` is always false for this case study; retain `risk_coverage_complete` so the report explicitly explains the additional announcement blocker.

- [ ] **Step 8: Write failing deduplication and Top-5 tests**

Create seven candidates on one date with duplicate codes and multiple profiles. Assert:

- profiles absent from the freeze are removed;
- duplicate stock-date rows choose lower rate, lower deviation, higher setup quality, then profile ID;
- final order uses frozen profile rank, rate, deviation, quality, 2R buffer, and code; and
- exactly five remain, all zero-share.

Also test an empty freeze returns no candidates and does not backfill.

- [ ] **Step 9: Implement selection and exact-recall comparison**

`select_frozen_daily_candidates` must validate the freeze hash before filtering and must return candidates sorted by signal date plus the design ranking. `compare_exact_recall(selected, winner_keys, formal_keys)` returns literal counts for actionable stock-date winners, formal captures, shadow captures, incremental captures, and selected non-winner rows. Joins use normalized `(signal_date, code)` only.

Use this exact immutable result model:

```python
@dataclass(frozen=True)
class ExactRecallComparison:
    actionable_winner_pairs: int
    formal_captured_pairs: int
    shadow_captured_pairs: int
    incremental_captured_pairs: int
    selected_non_winner_pairs: int
```

- [ ] **Step 10: Run evaluation tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_threshold_shadow_evaluation.py \
  tests/unit/test_buy_point_case_review.py \
  tests/unit/test_buy_point_recall_research.py
```

Expected: all pass.

- [ ] **Step 11: Commit evaluation and freeze logic**

```bash
git add stock_ai/buy_point_selection/threshold_shadow_evaluation.py \
  tests/unit/test_buy_point_threshold_shadow_evaluation.py
git commit -m "feat(stock-ai): freeze precision shadow profiles"
```

---

### Task 4: Write immutable v1 research, freeze, and test artifacts

**Files:**
- Create: `stock_ai/buy_point_selection/threshold_shadow_report.py`
- Create: `tests/unit/test_buy_point_threshold_shadow_report.py`

**Interfaces:**
- Consumes: profile matrix, Task 2 replay, Task 3 outcomes/metrics/freeze/selection, formal baseline outcomes, v5 lineage, input fingerprint, and stage metadata.
- Produces: `ThresholdWindowReview`, `threshold_shadow_payload(review)`, `threshold_shadow_identity(review)`, `render_threshold_shadow_markdown(review)`, `write_threshold_shadow_revision(review, output_dir)`, `freeze_payload(freeze)`, `write_threshold_freeze(freeze, output_dir)`, `load_threshold_research_artifact(path)`, `load_threshold_freeze_artifact(path)`, and `load_threshold_test_artifact(path)`.

- [ ] **Step 1: Write the failing research-payload reconciliation test**

Construct a two-candidate `ThresholdWindowReview` and assert:

```python
payload = threshold_shadow_payload(review)
assert payload["schema"] == "buy-point-threshold-shadow-v1"
assert payload["stage"] == "research"
assert payload["status"] == "CASE_ANALYSIS_ONLY"
assert payload["trade_permission"] == "NO-TRADE"
assert len(payload["raw_setups"]) == payload["metrics"]["raw_setups"]
assert len(payload["candidates"]) == payload["metrics"]["candidates"]
assert all(value["executable_shares"] == 0 for value in payload["candidates"])
```

- [ ] **Step 2: Run the test and verify RED**

Expected: module import failure.

- [ ] **Step 3: Add stage-neutral review and deterministic serializers**

Define `ThresholdWindowReview` with literal fields for stage, dates, cutoff, v5 case identity, input fingerprint, formal rule/policy hash, profile matrix/freeze hash, profiles, replay, shadow outcomes, formal baseline candidates/outcomes, selected candidates/outcomes, exact-recall comparison, risk coverage, and test-consumed flag. Serialize every `Decimal` as a string and every date as ISO. Raw rows sort by signal date, code, and profile ID.

- [ ] **Step 4: Add identity and immutable-write RED tests**

Assert stage, dates, v5 identity, input fingerprint, policy hash, matrix/freeze hash, and evaluator/cost version all change identity. Assert a second byte-identical write verifies, while different content at the same path raises rather than overwrites.

- [ ] **Step 5: Implement canonical identities and exclusive-or-verify writes**

Use a 16-character SHA-256 identity suffix and filenames containing stage, signal range, cutoff, and identity. Use `Path.open("x")`; on `FileExistsError`, compare exact bytes and raise on mismatch. The freeze filename includes `freeze-{freeze_hash}.json` and never overwrites.

- [ ] **Step 6: Add freeze/test safety RED tests**

Assert:

- freeze payload records both research identities and can represent an empty set;
- a test review requires a validated freeze hash;
- a test payload has `test_consumed=True`;
- every selected row is zero-share;
- incomplete announcement coverage produces `promotion_eligible=False`; and
- loaders reject wrong schemas, stages, mismatched embedded hashes, duplicate training identities, or mutable test content.

- [ ] **Step 7: Implement strict loaders and Markdown**

Markdown must show profile thresholds, daily raw/deduplicated/selected counts, formal versus shadow primary metrics, auxiliary recall, qualification reasons, freeze hash, one-time test state, and these literal warnings:

```text
股票-日期样本存在重叠，不能视为相互独立。
本报告仅用于案例研究，不生成交易建议；可执行仓位为 0。
短窗口通过只能进入扩大历史验证，不能晋级正式规则。
```

- [ ] **Step 8: Run report tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_threshold_shadow_report.py
```

Expected: all pass.

- [ ] **Step 9: Commit immutable artifacts**

```bash
git add stock_ai/buy_point_selection/threshold_shadow_report.py \
  tests/unit/test_buy_point_threshold_shadow_report.py
git commit -m "feat(stock-ai): report threshold shadow evidence"
```

---

### Task 5: Add the manual research/freeze/test CLI and point-in-time lineage checks

**Files:**
- Create: `scripts/analysis/review_buy_point_threshold_shadows.py`
- Create: `tests/unit/test_review_buy_point_threshold_shadows_cli.py`
- Modify: `docs/CAPABILITIES.md`

**Interfaces:**
- Consumes: `load_mysql_case_inputs`, one v5 JSON path per research/test window, two research artifacts for freeze, and one immutable freeze artifact for test.
- Produces: subcommands `research`, `freeze`, `test`; `V5RecallLineage`; `load_v5_recall_lineage(path, expected_dates, cutoff)`; `case_input_fingerprint(inputs)`; and stage-specific v1 artifacts.

- [ ] **Step 1: Write failing parser and v5-lineage tests**

Require these exact command shapes:

```bash
review_buy_point_threshold_shadows.py research \
  --signal-start 2026-07-20 --signal-end 2026-07-24 \
  --outcome-cutoff 2026-07-31 --v5-case case.json

review_buy_point_threshold_shadows.py freeze \
  --research-artifact first.json --research-artifact second.json

review_buy_point_threshold_shadows.py test \
  --signal-start 2026-08-03 --signal-end 2026-08-07 \
  --outcome-cutoff 2026-08-14 --v5-case case.json \
  --freeze-artifact freeze.json
```

The lineage loader must require schema `buy-point-case-review-v5`, exact signal dates/cutoff, `CASE_ANALYSIS_ONLY`, `NO-TRADE`, reconciled daily winner counts, and zero executable shares. It returns the case identity, exact winner keys, and risk coverage flag.

- [ ] **Step 2: Run parser/lineage tests and verify RED**

Expected: script import failure.

- [ ] **Step 3: Implement parser, lineage model, and canonical input fingerprint**

`case_input_fingerprint` hashes canonical content for trading dates, all bounded bar fields, memberships, risk flags, reference coverage, market snapshots, point-in-time holdings, and holdings completeness. Tests must prove mapping/input order does not change the hash while a changed bar close, holding share presence, or coverage flag does.

- [ ] **Step 4: Write failing research runtime test**

Inject a fake `input_loader` and temporary v5 JSON. Assert research:

- calls the loader once;
- builds formal `replay_case_signals` baseline;
- replays all 48 shadow profiles;
- evaluates every passing profile candidate through the fifth outcome session;
- computes profile metrics and exact recall;
- writes one research artifact; and
- never mutates the fake holdings or any external state.

- [ ] **Step 5: Implement the research stage**

Resolve actual trading dates from inputs, fail closed unless every signal date has complete holdings and exactly five outcome sessions, rebuild the formal strict baseline, call Task 2 replay with all profiles, evaluate Task 3 outcomes, and write Task 4 artifacts. `risk_coverage_complete` requires announcement completeness for every signal date; incomplete announcements remain explicit and set promotion eligibility false.

- [ ] **Step 6: Write failing freeze-stage tests**

Use two research payload fixtures and assert freeze rejects:

- fewer or more than two artifacts;
- duplicated research identity;
- wrong signal windows or cutoffs;
- different policy, matrix, evaluator, or fee versions;
- overlapping/incorrect stage lineage; and
- raw outcomes that do not reconcile with profile metrics.

Assert valid inputs aggregate raw profile outcomes across both windows before qualification and produce either ranked profiles or an explicit empty freeze.

- [ ] **Step 7: Implement freeze orchestration**

Load and verify both research artifacts, require the exact July windows,
reconstruct the repeated candidate profile-ID sequence and every raw
`ThresholdShadowOutcome`, call `aggregate_profile_metrics` across the combined
rows, call `freeze_threshold_profiles`, and write the immutable freeze JSON plus
a concise Markdown companion.

- [ ] **Step 8: Write failing one-time test-stage tests**

Assert test:

- requires the exact August window and cutoff;
- rejects missing or mismatched freeze/profile/matrix hashes;
- generates candidates only for frozen profile IDs;
- applies deterministic deduplication and daily Top 5;
- evaluates only selected candidates for primary basket metrics while preserving raw frozen-profile hits for audit;
- sets `test_consumed=True`; and
- verifies an identical rerun but rejects different content at the same identity.

- [ ] **Step 9: Implement the test stage and manual capability documentation**

Wire the frozen profile list into Task 2 replay, Task 3 selection/evaluation, and Task 4 test report. Add a `docs/CAPABILITIES.md` section with the three commands, explicit manual-only status, and `NO-TRADE` warning. Do not add cron, launchd, scheduler, notification, or database writes.

- [ ] **Step 10: Run CLI and integration tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py \
  tests/unit/test_buy_point_threshold_shadow_research.py \
  tests/unit/test_buy_point_threshold_shadow_evaluation.py \
  tests/unit/test_buy_point_threshold_shadow_report.py \
  tests/unit/test_review_buy_point_case_cli.py
```

Expected: all pass.

- [ ] **Step 11: Commit the manual workflow**

```bash
git add scripts/analysis/review_buy_point_threshold_shadows.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py \
  docs/CAPABILITIES.md
git commit -m "feat(stock-ai): run frozen threshold shadow research"
```

---

### Task 6: Run full regression and the three immutable LAN cases

**Files:**
- Verify only; generated files under `output/research/buy_point_threshold_shadows/` remain ignored.

**Interfaces:**
- Consumes: the committed CLI, the three v5 JSON artifacts, `.env` MySQL credentials with host/port overridden in memory to `192.168.1.13:3306`, and existing BaoStock/Eastmoney reference fallbacks.
- Produces: two research artifacts, one freeze artifact, one holdout artifact, Markdown companions, and a final evidence summary. No tracked data file is produced.

- [ ] **Step 1: Run the complete relevant regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_threshold_shadow_research.py \
  tests/unit/test_buy_point_threshold_shadow_evaluation.py \
  tests/unit/test_buy_point_threshold_shadow_report.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py \
  tests/unit/test_buy_point_recall_research.py \
  tests/unit/test_buy_point_resistance_research.py \
  tests/unit/test_buy_point_case_report.py \
  tests/unit/test_buy_point_case_review.py \
  tests/unit/test_review_buy_point_case_cli.py \
  tests/unit/test_buy_point_historical_replay.py \
  tests/unit/test_buy_point_historical_replay_runtime.py \
  tests/unit/test_buy_point_reference_baostock.py \
  tests/unit/test_buy_point_gates.py \
  tests/unit/test_buy_point_patterns.py \
  tests/unit/test_buy_point_planning.py \
  tests/unit/test_buy_point_validation.py
```

Expected: all pass with no warnings.

- [ ] **Step 2: Compile touched Python modules and prove production files unchanged**

```bash
PYTHONPATH=. .venv/bin/python -m py_compile \
  stock_ai/buy_point_selection/threshold_shadow_research.py \
  stock_ai/buy_point_selection/threshold_shadow_evaluation.py \
  stock_ai/buy_point_selection/threshold_shadow_report.py \
  scripts/analysis/review_buy_point_threshold_shadows.py

git diff --exit-code b626bce..HEAD -- \
  stock_ai/buy_point_selection/patterns.py \
  stock_ai/buy_point_selection/planning.py \
  stock_ai/buy_point_selection/models.py
```

Expected: no diff for the three production files.

- [ ] **Step 3: Run the two research windows against the LAN database**

Load `.env`, parse `MYSQL_URL` with SQLAlchemy, replace only host and port in a
task-specific shell variable without printing it, then invoke:

```bash
BUY_POINT_SHADOW_MYSQL_URL="$(.venv/bin/python -c "import os; from dotenv import load_dotenv; from sqlalchemy.engine import make_url; load_dotenv('.env'); print(make_url(os.environ['MYSQL_URL']).set(host='192.168.1.13', port=3306).render_as_string(hide_password=False))")"
MYSQL_URL="$BUY_POINT_SHADOW_MYSQL_URL" PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_threshold_shadows.py research \
  --signal-start 2026-07-20 --signal-end 2026-07-24 \
  --outcome-cutoff 2026-07-31 \
  --v5-case output/research/buy_point_cases/20260720_20260724_cutoff-20260731_da99d57b7b78fc3e.json

MYSQL_URL="$BUY_POINT_SHADOW_MYSQL_URL" PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_threshold_shadows.py research \
  --signal-start 2026-07-27 --signal-end 2026-07-31 \
  --outcome-cutoff 2026-08-07 \
  --v5-case output/research/buy_point_cases/20260727_20260731_cutoff-20260807_38b1bdbe2cf95faa.json
```

Expected: two deterministic v1 research JSON/Markdown revisions. Do not print the URL or credentials.

- [ ] **Step 4: Audit research artifacts before freezing**

Assert with `jq` or a small read-only audit:

- schema/stage/status/trade permission are exact;
- profile matrix contains 48 profiles and its hash matches both windows;
- all signal dates and five-session outcomes are complete;
- raw candidates, outcomes, profile metrics, and exact recall reconcile;
- every executable share field equals zero;
- both v5 identities and input fingerprints are present; and
- announcement risk incompleteness remains explicit.

- [ ] **Step 5: Freeze exactly the two research artifacts**

Resolve the paths printed in Step 3 with task-specific variables, require one
match for each exact window, and then freeze them:

```bash
BUY_POINT_SHADOW_RESEARCH_ONE="$(rg --files output/research/buy_point_threshold_shadows | rg '/research_20260720_20260724_cutoff-20260731_[0-9a-f]{16}\.json$' | sort | tail -n 1)"
BUY_POINT_SHADOW_RESEARCH_TWO="$(rg --files output/research/buy_point_threshold_shadows | rg '/research_20260727_20260731_cutoff-20260807_[0-9a-f]{16}\.json$' | sort | tail -n 1)"
test -n "$BUY_POINT_SHADOW_RESEARCH_ONE"
test -n "$BUY_POINT_SHADOW_RESEARCH_TWO"
PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_threshold_shadows.py freeze \
  --research-artifact "$BUY_POINT_SHADOW_RESEARCH_ONE" \
  --research-artifact "$BUY_POINT_SHADOW_RESEARCH_TWO"
```

Record whether the result contains qualified profiles or an explicit empty set. Do not alter thresholds if it is empty.

- [ ] **Step 6: Run the one-time August holdout**

```bash
BUY_POINT_SHADOW_MYSQL_URL="$(.venv/bin/python -c "import os; from dotenv import load_dotenv; from sqlalchemy.engine import make_url; load_dotenv('.env'); print(make_url(os.environ['MYSQL_URL']).set(host='192.168.1.13', port=3306).render_as_string(hide_password=False))")"
BUY_POINT_SHADOW_FREEZE="$(rg --files output/research/buy_point_threshold_shadows | rg '/freeze-[0-9a-f]{64}\.json$' | sort | tail -n 1)"
test -n "$BUY_POINT_SHADOW_FREEZE"
MYSQL_URL="$BUY_POINT_SHADOW_MYSQL_URL" PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_threshold_shadows.py test \
  --signal-start 2026-08-03 --signal-end 2026-08-07 \
  --outcome-cutoff 2026-08-14 \
  --v5-case output/research/buy_point_cases/20260803_20260807_cutoff-20260814_1476b69b11fda315.json \
  --freeze-artifact "$BUY_POINT_SHADOW_FREEZE"
```

Expected: one immutable test revision with `test_consumed=true`, zero to five selected candidates per signal date, and no writes outside ignored research outputs.

- [ ] **Step 7: Perform the final holdout audit**

Verify:

- frozen profile hash exactly matches the test report;
- only frozen profile IDs appear;
- every daily selected count is at most five;
- selected rows deduplicate `(signal_date, code)`;
- all selected outcomes reconcile with primary metrics;
- formal and shadow recall joins are exact-date;
- all research objects have zero executable shares;
- status remains `CASE_ANALYSIS_ONLY / NO-TRADE`; and
- `promotion_eligible` remains false.

Summarize qualified fields/rates, candidate counts, trigger/resolution counts, mean/median net return, positive-net rate, stop-first rate, MFE/MAE, incremental 5% recall, and formal-baseline comparison. If the freeze is empty, report that as the valid result.

- [ ] **Step 8: Run fresh completion verification and inspect scoped Git state**

Re-run the complete test command from Step 1, run `git diff --check`, confirm the new/touched scoped files are clean, and confirm unrelated dirty workspace files were neither staged nor modified by this task.

No final code commit is needed in this task unless verification reveals a test-backed correction. Any correction must repeat RED-GREEN and receive its own scoped commit.
