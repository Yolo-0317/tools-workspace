# Buy-Point Market and Sector Gate Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only, zero-share workflow that attributes exactly one market or sector gate failure, freezes only precision-qualified sector profiles, and supports immutable manual forward screening and settlement.

**Architecture:** A pure gate-shadow replay module owns the exact six-profile matrix and formal-setup-only counterfactual pipeline. A separate evaluation module owns cost-adjusted outcomes, sector-only qualification, immutable retrospective freezes, and daily Top-5 selection. A report module serializes research, freeze, screen, and settlement artifacts, while one manual CLI orchestrates point-in-time MySQL inputs and existing v5 lineage.

**Tech Stack:** Python 3.11+, frozen dataclasses, `Decimal`, existing buy-point detectors/gates/planner/evaluator, SQLAlchemy-backed read-only inputs, deterministic JSON/Markdown, pytest.

## Global Constraints

- Rule version remains exactly `buy-point-selection-3.1.0`.
- The profile matrix contains exactly two diagnostic market reasons and four research sector reasons from the approved spec.
- A candidate requires a formal production setup and exactly one supported gate failure reason.
- Threshold-shadow setups from the preceding study remain attribution-only and cannot enter this pipeline.
- Market `FREEZE` profiles are diagnostic-only and can never freeze or screen.
- Market diagnostic planning uses the unchanged planner with conservative status `LIMITED`, never `ALLOW`.
- Sector profiles require the unchanged market and anti-chase gates to pass and bypass only one matching sector reason.
- Base exclusions, incomplete facts, sector membership/sample failures, anti-chase failures, price-plan failures, and 2R failures remain hard boundaries.
- Retrospective windows are July 20–24, July 27–31, and August 3–7, 2026, with cutoffs July 31, August 7, and August 14.
- Those windows are already observed and must never be labeled an independent holdout.
- A sector profile needs at least 10 triggered resolved outcomes, positive mean net return, positive-net rate at least 50%, and stop-first rate no greater than 40%.
- Daily forward screens contain zero to five deduplicated stocks and never fill from failed, diagnostic, or unfrozen profiles.
- Every research object is `CASE_ANALYSIS_ONLY / NO-TRADE` with `executable_shares=0`.
- Existing production `models.py`, `patterns.py`, `gates.py`, `planning.py`, sizing, validation, holdings, decision memory, notifications, orders, and formal selection tables remain unchanged.
- Screen signal generation reads no future price bars; its two plan-validity dates come only from the existing confirmed local A-share calendar and fail closed when unknown.
- Screen artifacts contain no outcomes. Settlement writes a separate artifact after exactly five later sessions and cannot alter screen membership.
- MySQL access is read-only. `192.168.1.13:3306` is a runtime override and is never committed.
- Generated artifacts remain ignored by Git. No scheduler, notification, portfolio, memory, or order integration is added.
- Use RED-GREEN tests for every behavior change and commit only scoped files.

## File Map

- Create `stock_ai/buy_point_selection/gate_shadow_research.py`: profile matrix, formal-setup gate attribution, replay, candidates, rejections, and relaxed-threshold exclusion boundary.
- Create `stock_ai/buy_point_selection/gate_shadow_evaluation.py`: outcomes, profile metrics, sector-only retrospective freeze, candidate deduplication, and daily Top-5 ranking.
- Create `stock_ai/buy_point_selection/gate_shadow_report.py`: deterministic research/freeze/screen/settlement models, identities, payloads, loaders, and exclusive-or-verify writers.
- Create `scripts/analysis/review_buy_point_gate_shadows.py`: `research`, `freeze`, `screen`, and `settle` manual subcommands, v5 lineage reuse, point-in-time input fingerprints, and confirmed-calendar resolution.
- Create `tests/unit/test_buy_point_gate_shadow_research.py`.
- Create `tests/unit/test_buy_point_gate_shadow_evaluation.py`.
- Create `tests/unit/test_buy_point_gate_shadow_report.py`.
- Create `tests/unit/test_review_buy_point_gate_shadows_cli.py`.
- Modify `docs/CAPABILITIES.md`: document the manual workflow and prospective evidence boundary.

---

### Task 1: Define the exact gate profile matrix and admission primitives

**Files:**
- Create: `stock_ai/buy_point_selection/gate_shadow_research.py`
- Create: `tests/unit/test_buy_point_gate_shadow_research.py`

**Interfaces:**
- Consumes: `DetectedSetup`, `PricePlan`, and immutable reason strings returned by production `classify_market` and `sector_gate`.
- Produces: `GateShadowProfile`, `GateShadowHit`, `GateShadowCandidate`, `GateShadowRejection`, `GateShadowReplay`, `build_gate_shadow_profiles()`, `gate_profile_matrix_hash(profiles)`, and `matching_gate_profile(gate, reasons, profiles)`.

- [ ] **Step 1: Write the failing literal profile-matrix test**

```python
def test_gate_profile_matrix_is_exact_and_market_is_diagnostic_only() -> None:
    profiles = build_gate_shadow_profiles()

    assert [value.profile_id for value in profiles] == [
        "MARKET:AMOUNT_AND_BREADTH_WEAK:DIAGNOSTIC",
        "MARKET:INDEX_AND_BREADTH_WEAK:DIAGNOSTIC",
        "SECTOR:SECTOR_AMOUNT_WEAK:BYPASS",
        "SECTOR:SECTOR_BREADTH_WEAK:BYPASS",
        "SECTOR:SECTOR_NOT_RESONATING:BYPASS",
        "SECTOR:SECTOR_RELATIVE_STRENGTH_WEAK:BYPASS",
    ]
    assert all(not value.freeze_eligible for value in profiles[:2])
    assert all(value.freeze_eligible for value in profiles[2:])
```

- [ ] **Step 2: Run the profile test and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_gate_shadow_research.py::test_gate_profile_matrix_is_exact_and_market_is_diagnostic_only
```

Expected: collection fails because `gate_shadow_research` does not exist.

- [ ] **Step 3: Implement immutable profile and replay models**

Use these public shapes:

```python
@dataclass(frozen=True)
class GateShadowProfile:
    profile_id: str
    gate: str
    failure_reason: str
    mode: str
    freeze_eligible: bool

@dataclass(frozen=True)
class GateShadowHit:
    code: str
    signal_date: date
    profile: GateShadowProfile
    setup: DetectedSetup
    market_status: str
    sector_code: str
    executable_shares: int = 0

@dataclass(frozen=True)
class GateShadowCandidate:
    hit: GateShadowHit
    plan: PricePlan
    average_amount5_qian: Decimal
    two_r_space_buffer: Decimal
    executable_shares: int = 0
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"

@dataclass(frozen=True)
class GateShadowRejection:
    code: str
    signal_date: date
    profile_id: str | None
    stage: str
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class GateShadowReplay:
    signal_dates: tuple[date, ...]
    incomplete_dates: tuple[date, ...]
    raw_hits: tuple[GateShadowHit, ...]
    candidates: tuple[GateShadowCandidate, ...]
    rejections: tuple[GateShadowRejection, ...]
```

Build the six profiles from one literal tuple and hash every profile field in canonical profile-ID order.

- [ ] **Step 4: Run the profile test and verify GREEN**

Run the entire new test module. Expected: the literal matrix and deterministic hash tests pass.

- [ ] **Step 5: Write failing exact-single-reason admission tests**

Add literal tests proving:

```python
assert matching_gate_profile(
    "SECTOR", ("SECTOR_BREADTH_WEAK",), profiles
).profile_id == "SECTOR:SECTOR_BREADTH_WEAK:BYPASS"
assert matching_gate_profile(
    "SECTOR",
    ("SECTOR_BREADTH_WEAK", "SECTOR_AMOUNT_WEAK"),
    profiles,
) is None
assert matching_gate_profile(
    "SECTOR", ("SECTOR_SAMPLE_TOO_SMALL",), profiles
) is None
assert matching_gate_profile(
    "MARKET", ("MARKET_DATA_INCOMPLETE",), profiles
) is None
```

Also assert duplicate, reordered, or forged profile sequences raise `ValueError("unsupported gate profile matrix")`.

- [ ] **Step 6: Run the admission tests and verify RED**

Expected: failure because reason matching and matrix validation are absent.

- [ ] **Step 7: Implement strict reason matching and profile validation**

Require `len(reasons) == 1`, exact gate/reason equality, and equality with the canonical six-profile tuple. Return `None` for every unsupported or hard failure. Reject any supplied matrix that is not byte-for-byte equal to `build_gate_shadow_profiles()`.

- [ ] **Step 8: Run Task 1 tests and commit**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_gate_shadow_research.py
git add stock_ai/buy_point_selection/gate_shadow_research.py \
  tests/unit/test_buy_point_gate_shadow_research.py
git commit -m "feat(stock-ai): define gate shadow profiles"
```

---

### Task 2: Replay formal setups through one counterfactual gate reason

**Files:**
- Modify: `stock_ai/buy_point_selection/gate_shadow_research.py`
- Modify: `tests/unit/test_buy_point_gate_shadow_research.py`

**Interfaces:**
- Consumes: the exact point-in-time bundle accepted by `replay_case_signals`, the canonical six profiles, production `detect_setups`, gates, sector snapshots, and `build_price_plan`.
- Produces:

```python
def replay_gate_shadows(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
    holding_codes_by_date: Mapping[date, frozenset[str]],
    profiles: Sequence[GateShadowProfile],
    formal_policy: SelectionPolicy | None = None,
) -> GateShadowReplay:
```

- [ ] **Step 1: Write a failing sector single-reason pipeline test**

Create a fixture with complete point-in-time facts, an allowing market, a formal setup, a passing anti-chase result, and a sector snapshot failing only `SECTOR_BREADTH_WEAK`. Inject narrow detector/sector/planner seams only where the real fixture would be prohibitively large. Assert one raw hit, one valid candidate, zero shares, and the exact sector profile ID.

- [ ] **Step 2: Run the sector pipeline test and verify RED**

Expected: failure because `replay_gate_shadows` is missing.

- [ ] **Step 3: Implement the sector branch**

For every bounded stock-date:

1. require latest signal-date bar and complete coverage;
2. pass the unchanged base gate;
3. call production `detect_setups` and require at least one formal setup;
4. choose `max(setups, key=(quality, setup_type.value))` exactly as `replay_case_signals`;
5. require the market and anti-chase gates to pass;
6. require sector membership and snapshot;
7. match exactly one supported sector reason;
8. call the unchanged planner with the real market status; and
9. emit a zero-share candidate only when the plan succeeds.

Compute `two_r_space_buffer` as `nearest_resistance_above(trigger, bars) - target_2r` and sort every output deterministically.

- [ ] **Step 4: Verify the sector test is GREEN**

Run the focused test, then the complete gate-shadow research test module.

- [ ] **Step 5: Write failing market diagnostic tests**

Add a formal-setup fixture with `INDEX_AND_BREADTH_WEAK`, passing anti-chase and sector gates, and a valid plan under `LIMITED`. Assert:

```python
assert candidate.hit.profile.mode == "DIAGNOSTIC"
assert candidate.hit.market_status == "FREEZE"
assert planner_market_statuses == ["LIMITED"]
assert candidate.executable_shares == 0
```

Add a second test proving a market diagnostic row is rejected when the normal sector gate fails.

- [ ] **Step 6: Run market tests and verify RED**

Expected: no market branch or the production planner receives `FREEZE` and rejects.

- [ ] **Step 7: Implement the market diagnostic branch**

Match one supported market reason, then require base, formal setup, anti-chase, membership, and sector gates normally. Call `build_price_plan` with literal `LIMITED`; preserve the observed market status `FREEZE` on `GateShadowHit`. Never change the production planner.

- [ ] **Step 8: Write failing hard-boundary and leakage tests**

Add one literal test per boundary:

- no formal setup produces no raw hit;
- a supplied relaxed threshold setup cannot enter because replay calls only production `detect_setups`;
- `SECTOR_MEMBERSHIP_INCOMPLETE` and `SECTOR_SAMPLE_TOO_SMALL` cannot match;
- multiple sector reasons cannot match;
- base, anti-chase, or price-plan failure produces no candidate and an explicit rejection;
- a holding or `VETO` remains excluded;
- adding bars after the signal date cannot change hits, candidates, or ranks; and
- an incomplete signal date appears only in `incomplete_dates`.

- [ ] **Step 9: Implement fail-closed rejection auditing**

Record stages `LATEST_BAR`, `BASE`, `SETUP`, `MARKET`, `ANTI_CHASE`, `SECTOR`, and `PRICE_PLAN`. A nonmatching failed gate is a rejection, never a candidate. Ensure every raw hit and candidate has zero executable shares.

- [ ] **Step 10: Run Task 2 and production regression tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_gate_shadow_research.py \
  tests/unit/test_buy_point_gates.py \
  tests/unit/test_buy_point_patterns.py \
  tests/unit/test_buy_point_planning.py \
  tests/unit/test_buy_point_case_review.py
```

- [ ] **Step 11: Commit replay**

```bash
git add stock_ai/buy_point_selection/gate_shadow_research.py \
  tests/unit/test_buy_point_gate_shadow_research.py
git commit -m "feat(stock-ai): replay gate shadow candidates"
```

---

### Task 3: Evaluate outcomes, freeze only sector profiles, and select daily Top 5

**Files:**
- Create: `stock_ai/buy_point_selection/gate_shadow_evaluation.py`
- Create: `tests/unit/test_buy_point_gate_shadow_evaluation.py`

**Interfaces:**
- Consumes: `GateShadowCandidate`, `CaseOutcome`, the existing `evaluate_case_plan`, and the exact profile matrix.
- Produces: `GateShadowOutcome`, `GateProfileMetrics`, `FrozenGateProfile`, `GateProfileFreeze`, `evaluate_gate_shadow_outcomes`, `aggregate_gate_profile_metrics`, `freeze_sector_gate_profiles`, `validate_gate_profile_freeze`, and `select_frozen_gate_candidates`.

- [ ] **Step 1: Write the failing cost-adjusted evaluator test**

Adapt one zero-share gate candidate into the existing `CaseCandidate` evaluator and assert the resulting `GateShadowOutcome` preserves profile ID, signal date, structure ID, transaction-cost-adjusted net return, and zero shares.

- [ ] **Step 2: Run the evaluator test and verify RED**

Expected: collection failure for the missing evaluation module.

- [ ] **Step 3: Implement the outcome adapter**

```python
@dataclass(frozen=True)
class GateShadowOutcome:
    profile_id: str
    code: str
    signal_date: date
    outcome: CaseOutcome
    executable_shares: int = 0
```

Reject any nonzero-share candidate and delegate all plan simulation to `evaluate_case_plan`.

- [ ] **Step 4: Write failing literal metric-boundary tests**

Build hand-derived rows proving a sector profile qualifies at exactly 10 resolved triggers, 50% positive net, 40% stop-first, and positive mean net. Mutate each boundary independently to prove failure. Add a market profile with strong outcomes and assert `qualifies=False` with reason `DIAGNOSTIC_ONLY_MARKET_PROFILE`.

- [ ] **Step 5: Implement deterministic metrics**

```python
@dataclass(frozen=True)
class GateProfileMetrics:
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

Use triggered rows with non-`None` net return for resolved metrics. Never let a market profile qualify.

- [ ] **Step 6: Write failing three-window freeze tests**

Assert the freeze:

- requires exactly three distinct retrospective research identities;
- rejects a matrix or formal-policy mismatch;
- excludes market profiles regardless of metrics;
- ranks qualifying sector profiles by mean net, positive rate, stop rate, and profile ID; and
- writes an explicit empty set when none qualifies.

- [ ] **Step 7: Implement immutable retrospective freeze**

```python
@dataclass(frozen=True)
class FrozenGateProfile:
    profile_id: str
    rank: int
    training_metrics: GateProfileMetrics

@dataclass(frozen=True)
class GateProfileFreeze:
    schema: str
    training_identities: tuple[str, str, str]
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    profiles: tuple[FrozenGateProfile, ...]
    retrospective: bool
    empty: bool
    risk_coverage_complete: bool
    promotion_eligible: bool
    freeze_hash: str
```

Set `retrospective=True` and `promotion_eligible=False` unconditionally. Hash the canonical full freeze content.

- [ ] **Step 8: Write failing deduplication and Top-5 tests**

Create six sector candidates on one date plus duplicate profiles for one code. Assert only frozen sector profile IDs survive, one row remains per code/date, rank order is profile rank, negative setup quality, negative 2R buffer, negative average amount, then code, and the daily result contains exactly five rows.

- [ ] **Step 9: Implement candidate selection**

Validate the freeze, reject market profile IDs, deduplicate deterministically, cap each date at five, and enforce zero shares. An empty freeze returns an empty tuple.

- [ ] **Step 10: Run and commit evaluation**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_gate_shadow_evaluation.py \
  tests/unit/test_buy_point_gate_shadow_research.py \
  tests/unit/test_buy_point_case_review.py
git add stock_ai/buy_point_selection/gate_shadow_evaluation.py \
  tests/unit/test_buy_point_gate_shadow_evaluation.py
git commit -m "feat(stock-ai): freeze sector gate shadows"
```

---

### Task 4: Write immutable research, freeze, screen, and settlement artifacts

**Files:**
- Create: `stock_ai/buy_point_selection/gate_shadow_report.py`
- Create: `tests/unit/test_buy_point_gate_shadow_report.py`

**Interfaces:**
- Consumes: gate profiles, replay, outcomes, metrics, freeze, selected screen candidates, v5 lineage, policy/input hashes, and a parent screen identity.
- Produces: `GateResearchReview`, `GateForwardScreen`, `GateForwardSettlement`, payload/render/write functions for all four stages, and strict stage loaders.

- [ ] **Step 1: Write a failing research-payload reconciliation test**

Require schema `buy-point-gate-shadow-v1`, stage `research`, both safety labels, `retrospective=true`, evaluator/cost versions, six profiles, exact row counts, explicit risk coverage, promotion false, and recursive zero-share values.

- [ ] **Step 2: Run the research report test and verify RED**

Expected: collection failure for missing report module.

- [ ] **Step 3: Implement research models and serializers**

Define a frozen `GateResearchReview` containing signal dates, cutoff, v5 identity, input fingerprint, formal hashes, profile matrix, replay, outcomes, metrics, exact recall, and risk coverage. Sort profiles, hits, candidates, outcomes, and rejections by stable date/code/profile keys before serialization.

- [ ] **Step 4: Write failing freeze artifact tests**

Assert freeze payloads preserve three training identities, `retrospective=true`, market-profile exclusion, empty-set truth, zero shares, risk coverage, promotion false, and a 64-character canonical hash. Tampering with any field must make the loader fail.

- [ ] **Step 5: Implement freeze serializer, loader, and writer**

Write deterministic JSON plus concise Chinese Markdown. Use exclusive create and byte-for-byte verification on rerun. Never overwrite different content.

- [ ] **Step 6: Write failing screen isolation tests**

Build a `GateForwardScreen` and assert:

- stage is `screen` and `retrospective=false`;
- the freeze hash and signal input fingerprint are present;
- candidate count is between zero and five;
- candidate rows contain trigger, invalidation, 2R target, structure, profile rank, and zero shares;
- no `outcome`, `net_return`, `mfe`, `mae`, or future bar date appears anywhere; and
- a market profile or duplicate code/date is rejected.

- [ ] **Step 7: Implement screen identity and immutable writer**

The identity must include schema, stage, signal date, formal hashes, profile matrix, freeze hash, input fingerprint, and planner version. Use a filename beginning `screen_YYYYMMDD_`.

- [ ] **Step 8: Write failing settlement lineage tests**

Require `GateForwardSettlement` to link the exact parent screen identity, preserve the screen candidate keys and ranks, contain exactly one outcome per screen candidate, use exactly five outcome sessions, retain zero shares, and reject any membership or freeze-hash change.

- [ ] **Step 9: Implement separate settlement artifact**

Do not modify the screen file. Serialize a new
`settlement_YYYYMMDD_cutoff-YYYYMMDD_{16-hex-identity}.json` and Markdown
companion with resolved outcome metrics and explicit non-promotion language.

- [ ] **Step 10: Run and commit artifact tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_gate_shadow_report.py \
  tests/unit/test_buy_point_gate_shadow_evaluation.py \
  tests/unit/test_buy_point_gate_shadow_research.py
git add stock_ai/buy_point_selection/gate_shadow_report.py \
  tests/unit/test_buy_point_gate_shadow_report.py
git commit -m "feat(stock-ai): report gate shadow evidence"
```

---

### Task 5: Add the manual research, freeze, screen, and settle CLI

**Files:**
- Create: `scripts/analysis/review_buy_point_gate_shadows.py`
- Create: `tests/unit/test_review_buy_point_gate_shadows_cli.py`
- Modify: `docs/CAPABILITIES.md`

**Interfaces:**
- Consumes: `load_mysql_case_inputs`, `load_v5_recall_lineage`, `case_input_fingerprint`, three v5 artifacts, three gate research artifacts, one freeze artifact, one screen artifact, and the confirmed local A-share calendar.
- Produces: subcommands `research`, `freeze`, `screen`, and `settle`; `load_mysql_gate_screen_inputs(signal_date, confirmed_plan_dates)`; `load_mysql_gate_settlement_inputs(signal_date, outcome_cutoff)`; stage builders; immutable output paths; and exit code 2 for fail-closed validation errors.

- [ ] **Step 1: Write failing parser and window tests**

Require these exact shapes:

```bash
review_buy_point_gate_shadows.py research \
  --signal-start 2026-07-20 --signal-end 2026-07-24 \
  --outcome-cutoff 2026-07-31 --v5-case case.json

review_buy_point_gate_shadows.py freeze \
  --research-artifact first.json \
  --research-artifact second.json \
  --research-artifact third.json

review_buy_point_gate_shadows.py screen \
  --signal-date 2026-08-17 --freeze-artifact freeze.json

review_buy_point_gate_shadows.py settle \
  --screen-artifact screen.json --outcome-cutoff 2026-08-24
```

Assert research accepts only the three approved retrospective windows and freeze requires all three exact, distinct identities.

- [ ] **Step 2: Run parser/window tests and verify RED**

Expected: script import failure.

- [ ] **Step 3: Implement parser and shared lineage validation**

Reuse `load_v5_recall_lineage` and `case_input_fingerprint` from `review_buy_point_threshold_shadows.py`. Validate exact schema/status/trade permission, full holdings, exactly five outcome sessions for research, and matching policy/evaluator/cost/profile hashes before aggregation.

- [ ] **Step 4: Write failing research builder test**

Inject one `CaseReviewInputs` loader and assert the builder calls it once, replays all six profiles across the full universe, evaluates every candidate, rebuilds the formal strict baseline for exact recall, reports announcement incompleteness, and never mutates holdings or external state.

- [ ] **Step 5: Implement `build_gate_research_review`**

Load once, validate dates and holdings, call `replay_gate_shadows`, evaluate outcomes through cutoff, aggregate reason metrics, compare exact-date v5 recall, and return `GateResearchReview`. Mark the artifact retrospective and non-promotable.

- [ ] **Step 6: Write failing freeze orchestration tests**

Use three real-format payload fixtures. Reject duplicate identities, wrong windows, changed hashes/versions, market metrics included as frozen rows, candidate/outcome mismatch, edited summary metrics, and nonzero shares. Assert valid raw rows are aggregated before qualification and can produce an explicit empty freeze.

- [ ] **Step 7: Implement `build_gate_freeze_from_artifacts`**

Strictly reconstruct every candidate profile ID and `GateShadowOutcome`, recompute per-window metrics, aggregate all three windows, exclude market profiles in `freeze_sector_gate_profiles`, and write the immutable freeze pair.

- [ ] **Step 8: Write failing confirmed-calendar and screen tests**

Using a temporary calendar seam, assert two confirmed trading dates after August 17 are August 18 and 19, while an unknown weekday fails closed without refreshing or writing the calendar cache. Inject a signal-date input loader and assert `screen` uses bars only through the signal date, consumes only frozen sector profiles, deduplicates Top 5, and writes no outcome fields.

- [ ] **Step 9: Implement `build_gate_forward_screen`**

Implement `load_mysql_gate_screen_inputs` directly on the existing read-only
`_trade_dates`, `_load_daily_bars`, `_load_market_aggregates`,
`SQLReferenceRepository`, `_load_holdings_by_date`, and benchmark snapshot
helpers so it does not inherit `load_mysql_case_inputs`' requirement for two
future price-bar dates. Read MySQL bars only through the completed signal date.
Resolve the next two plan-validity dates with
`trading_day_status(day, refresh=False)`; do not call Tushare or write the
calendar cache. Append confirmed future dates only to the in-memory
trading-date sequence used by the planner. Reject a signal date on or before
August 7, an unconfirmed signal date, incomplete holdings/reference facts, a
market profile in the freeze, or future price bars in the signal panel.

- [ ] **Step 10: Write failing settlement tests**

Inject a bounded loader and a real screen artifact. Assert exactly five later sessions are required, only screen codes are evaluated, parent candidate keys/ranks remain unchanged, no candidate is added or dropped, and the screen file bytes do not change.

- [ ] **Step 11: Implement `build_gate_forward_settlement`**

Implement `load_mysql_gate_settlement_inputs` as a bounded read-only loader
through the explicit cutoff. Load and validate the screen, derive the exact
next-five-session horizon, evaluate each preserved screen plan with existing
costs, and write a separate settlement artifact. A second identical run
verifies content; different content at the same identity fails.

- [ ] **Step 12: Add manual capability documentation**

Document all four commands in `docs/CAPABILITIES.md`, including:

- retrospective research is not an independent holdout;
- market rows are diagnostic-only;
- screens and settlements are zero-share and manual;
- an empty freeze or screen is valid; and
- no scheduler, notification, holdings, memory, or order write exists.

- [ ] **Step 13: Run CLI integration tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_review_buy_point_gate_shadows_cli.py \
  tests/unit/test_buy_point_gate_shadow_report.py \
  tests/unit/test_buy_point_gate_shadow_evaluation.py \
  tests/unit/test_buy_point_gate_shadow_research.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py \
  tests/unit/test_review_buy_point_case_cli.py
```

- [ ] **Step 14: Commit the manual workflow**

```bash
git add scripts/analysis/review_buy_point_gate_shadows.py \
  tests/unit/test_review_buy_point_gate_shadows_cli.py \
  docs/CAPABILITIES.md
git commit -m "feat(stock-ai): run gate shadow research"
```

---

### Task 6: Run complete regression and the three retrospective LAN studies

**Files:**
- Verify only. Generated files under `output/research/buy_point_gate_shadows/` remain ignored.

**Interfaces:**
- Consumes: committed CLI, the three existing v5 case artifacts, `.env` credentials with host/port replaced only in process memory, and read-only MySQL/reference inputs.
- Produces: three research JSON/Markdown pairs, one retrospective freeze pair, and an evidence summary. It does not create a prospective screen before a completed post-freeze signal date exists.

- [ ] **Step 1: Run the complete relevant regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_gate_shadow_research.py \
  tests/unit/test_buy_point_gate_shadow_evaluation.py \
  tests/unit/test_buy_point_gate_shadow_report.py \
  tests/unit/test_review_buy_point_gate_shadows_cli.py \
  tests/unit/test_buy_point_threshold_shadow_research.py \
  tests/unit/test_buy_point_threshold_shadow_evaluation.py \
  tests/unit/test_buy_point_threshold_shadow_report.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py \
  tests/unit/test_buy_point_recall_research.py \
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

Expected: all tests pass. Existing Python 3.12 SQLite adapter deprecation warnings may remain, but no new warning is introduced.

- [ ] **Step 2: Compile modules and prove production rules unchanged**

```bash
PYTHONPATH=. .venv/bin/python -m py_compile \
  stock_ai/buy_point_selection/gate_shadow_research.py \
  stock_ai/buy_point_selection/gate_shadow_evaluation.py \
  stock_ai/buy_point_selection/gate_shadow_report.py \
  scripts/analysis/review_buy_point_gate_shadows.py

git diff --exit-code b036db6..HEAD -- \
  stock_ai/buy_point_selection/models.py \
  stock_ai/buy_point_selection/patterns.py \
  stock_ai/buy_point_selection/gates.py \
  stock_ai/buy_point_selection/planning.py
```

- [ ] **Step 3: Run the three research windows on LAN MySQL**

Construct the runtime URL without printing it, replacing only host and port with `192.168.1.13:3306`. Run:

```bash
BUY_POINT_GATE_SHADOW_MYSQL_URL="$(.venv/bin/python -c "import os; from dotenv import load_dotenv; from sqlalchemy.engine import make_url; load_dotenv('.env'); print(make_url(os.environ['MYSQL_URL']).set(host='192.168.1.13', port=3306).render_as_string(hide_password=False))")"

MYSQL_URL="$BUY_POINT_GATE_SHADOW_MYSQL_URL" PYTHONPATH=. .venv/bin/python \
  scripts/analysis/review_buy_point_gate_shadows.py research \
  --signal-start 2026-07-20 --signal-end 2026-07-24 \
  --outcome-cutoff 2026-07-31 \
  --v5-case output/research/buy_point_cases/20260720_20260724_cutoff-20260731_da99d57b7b78fc3e.json

MYSQL_URL="$BUY_POINT_GATE_SHADOW_MYSQL_URL" PYTHONPATH=. .venv/bin/python \
  scripts/analysis/review_buy_point_gate_shadows.py research \
  --signal-start 2026-07-27 --signal-end 2026-07-31 \
  --outcome-cutoff 2026-08-07 \
  --v5-case output/research/buy_point_cases/20260727_20260731_cutoff-20260807_38b1bdbe2cf95faa.json

MYSQL_URL="$BUY_POINT_GATE_SHADOW_MYSQL_URL" PYTHONPATH=. .venv/bin/python \
  scripts/analysis/review_buy_point_gate_shadows.py research \
  --signal-start 2026-08-03 --signal-end 2026-08-07 \
  --outcome-cutoff 2026-08-14 \
  --v5-case output/research/buy_point_cases/20260803_20260807_cutoff-20260814_1476b69b11fda315.json
```

- [ ] **Step 4: Audit every research artifact**

Use a read-only Python or `jq` audit to assert:

- exact schema, stage, status, trade permission, and retrospective label;
- exact six-profile matrix and identical matrix/policy/evaluator/cost hashes;
- exact signal dates, cutoff, v5 identity, and nonempty input fingerprint;
- candidate and outcome key reconciliation;
- market versus sector metrics remain separate;
- every executable-share value is zero;
- no threshold-shadow row appears in candidates; and
- announcement incompleteness remains explicit.

- [ ] **Step 5: Freeze exactly those three research artifacts**

Resolve exactly one immutable JSON for each approved window, then run:

```bash
BUY_POINT_GATE_RESEARCH_ONE="$(rg --files output/research/buy_point_gate_shadows | rg '/research_20260720_20260724_cutoff-20260731_[0-9a-f]{16}\.json$' | sort | tail -n 1)"
BUY_POINT_GATE_RESEARCH_TWO="$(rg --files output/research/buy_point_gate_shadows | rg '/research_20260727_20260731_cutoff-20260807_[0-9a-f]{16}\.json$' | sort | tail -n 1)"
BUY_POINT_GATE_RESEARCH_THREE="$(rg --files output/research/buy_point_gate_shadows | rg '/research_20260803_20260807_cutoff-20260814_[0-9a-f]{16}\.json$' | sort | tail -n 1)"
test -n "$BUY_POINT_GATE_RESEARCH_ONE"
test -n "$BUY_POINT_GATE_RESEARCH_TWO"
test -n "$BUY_POINT_GATE_RESEARCH_THREE"

PYTHONPATH=. .venv/bin/python scripts/analysis/review_buy_point_gate_shadows.py freeze \
  --research-artifact "$BUY_POINT_GATE_RESEARCH_ONE" \
  --research-artifact "$BUY_POINT_GATE_RESEARCH_TWO" \
  --research-artifact "$BUY_POINT_GATE_RESEARCH_THREE"
```

Record whether sector profiles qualify or the freeze is explicitly empty. Do not alter profile eligibility or thresholds when it is empty.

- [ ] **Step 6: Audit the retrospective freeze**

Assert three distinct training identities, matching hashes, `retrospective=true`, `promotion_eligible=false`, no market profile ID, sequential ranks, qualifying metrics for every frozen sector profile, and canonical freeze hash validation.

- [ ] **Step 7: Do not fabricate a prospective screen**

If no completed post-freeze signal date with complete inputs exists, stop after freeze and document the first eligible manual screen date. Do not run `screen` on an already observed retrospective date and do not label any retrospective row prospective.

- [ ] **Step 8: Run fresh completion verification**

Re-run Step 1, run `git diff --check`, inspect scoped Git status, and confirm ignored outputs are the only generated files. Report exact research counts, candidate counts, profile metrics, qualified sector profiles, diagnostic market results, risk-coverage status, and the earliest eligible forward-screen date.
