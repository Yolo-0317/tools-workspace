# Structure Stop-Anchor Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, manual, zero-share research workflow that compares three fixed stop-anchor variants over eight retrospective five-session blocks, freezes only qualified profiles, and supports separate forward screens and settlements without changing production selection rules.

**Architecture:** Add four focused research modules beside the existing gate-shadow workflow: pure anchor/profile math, bounded replay, evaluation/freezing, and immutable reporting. A manual CLI orchestrates research, freeze, screen, and settle stages using existing read-only MySQL, point-in-time holdings/reference inputs, local confirmed-calendar semantics, production gates, and execution costs. Production `models.py`, `patterns.py`, `gates.py`, `planning.py`, selectors, holdings, memory, scheduling, notifications, and orders remain untouched.

**Tech Stack:** Python 3.11, frozen dataclasses, `Decimal`, SQLAlchemy/PyMySQL read-only queries, existing buy-point domain modules, JSON/Markdown immutable artifacts, pytest.

## Global Constraints

- Schema is exactly `buy-point-structure-stop-shadow-v1`.
- Status is always `CASE_ANALYSIS_ONLY`; trade permission is always `NO-TRADE`; recursive executable shares are always `0`.
- Profiles are exactly `STRUCTURE_STOP:RECENT_SETUP_LOW`, `STRUCTURE_STOP:DYNAMIC_SUPPORT`, and `STRUCTURE_STOP:ATR_1_5` in that order.
- Production rule version remains `buy-point-selection-3.1.0`.
- Do not modify `stock_ai/buy_point_selection/models.py`, `patterns.py`, `gates.py`, or `planning.py`.
- The primary cohort has all production gates passing and exactly one baseline price failure: `RISK_DISTANCE_OUT_OF_RANGE`.
- Gate-plus-risk rows are diagnostic-only and can never qualify, freeze, rank, or screen.
- Trigger price, formal dynamic risk lower bound, 5% risk upper bound, 2R target, production resistance, risk budget, two-session plan validity, five-session result horizon, and execution costs remain unchanged.
- ATR profile uses exactly `1.5 * ATR14`; no alternate multipliers are generated.
- Eight calendar-derived blocks are retrospective and observed, not an independent holdout.
- Empty research candidates, empty freeze, and empty forward screen are valid.
- No scheduler, notification, holding, personal/decision memory, database write, or order path is added.
- Generated artifacts remain ignored under `output/research/buy_point_structure_stops/`.
- Work in scoped commits and preserve unrelated dirty-worktree changes.

---

### Task 1: Define the exact stop profiles and point-in-time anchor math

**Files:**
- Create: `stock_ai/buy_point_selection/structure_stop_shadow.py`
- Create: `tests/unit/test_buy_point_structure_stop_shadow.py`

**Interfaces:**
- Consumes: `BuyPointBar`, `DetectedSetup`, `SelectionPolicy`, `SetupType`, `PricePlan`, `RiskBudget`, `PlanDecision`, `atr14`, `nearest_resistance_above`, and `structure_id`.
- Produces: `StructureStopProfile`, `StructureStopAnchor`, `build_structure_stop_profiles()`, `validate_structure_stop_profiles()`, `structure_stop_profile_hash()`, `recent_setup_low()`, `dynamic_support_anchor()`, and `build_structure_stop_plan()`.

- [ ] **Step 1: Write failing exact-profile tests**

Add tests that require this literal tuple and reject missing, reordered, duplicated, or forged entries:

```python
def test_structure_stop_profile_matrix_is_exact() -> None:
    profiles = build_structure_stop_profiles()
    assert tuple(value.profile_id for value in profiles) == (
        "STRUCTURE_STOP:RECENT_SETUP_LOW",
        "STRUCTURE_STOP:DYNAMIC_SUPPORT",
        "STRUCTURE_STOP:ATR_1_5",
    )
    assert len(structure_stop_profile_hash(profiles)) == 64
    with pytest.raises(ValueError, match="profile matrix"):
        validate_structure_stop_profiles(tuple(reversed(profiles)))
```

- [ ] **Step 2: Run the profile test and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_structure_stop_shadow.py::test_structure_stop_profile_matrix_is_exact
```

Expected: collection fails because `structure_stop_shadow` does not exist.

- [ ] **Step 3: Implement immutable profile definitions and canonical hash**

Use these exact models:

```python
@dataclass(frozen=True)
class StructureStopProfile:
    profile_id: str
    anchor_kind: str
    uses_atr_buffer: bool


@dataclass(frozen=True)
class StructureStopAnchor:
    profile: StructureStopProfile
    code: str
    signal_date: date
    anchor_price: Decimal | None
    invalidation_price: Decimal | None
    reasons: tuple[str, ...]
    executable_shares: int = 0
```

Hash the sorted-key compact JSON representation of the exact ordered profile list with SHA-256. Validation must compare dataclass equality to a newly built literal matrix.

- [ ] **Step 4: Write failing setup-aware recent-low tests**

Create three fixtures whose older lows are deliberately lower than their recent setup lows. Require:

```python
assert recent_setup_low(pre_breakout, bars) == min(
    value.low for value in bars[-10:]
)
assert recent_setup_low(trend_pullback, bars) == min(
    value.low for value in bars[-3:]
)
assert recent_setup_low(first_launch, bars) == min(
    value.low for value in bars[-2:]
)
```

The trend fixture sets `setup.metrics["pullback_sessions"] = Decimal("3")`; the first-launch fixture sets `setup.metrics["quiet_sessions"] = Decimal("2")`. Add a future bar after `analysis_date` with an extreme low and assert it never changes any result.

- [ ] **Step 5: Implement `recent_setup_low` with bounded bars**

Sort and retain only bars through `setup.analysis_date`. Require the final bounded bar to equal the analysis date. Use final 10 sessions for `PRE_BREAKOUT`, the exact integer `pullback_sessions` for `TREND_PULLBACK`, and exact integer `quiet_sessions` for `FIRST_LAUNCH_PULLBACK`. Return `None` for missing, non-integral, out-of-range, non-positive, or non-finite inputs.

- [ ] **Step 6: Write failing dynamic-support and ATR tests**

Require dynamic support to select the maximum of MA10, MA20, and recent setup low that is finite, positive, and no higher than the signal-day low. Require no valid values to produce `SUPPORT_ANCHOR_UNAVAILABLE`. Require ATR profile invalidation to equal:

```python
(trigger - Decimal("1.5") * atr14(bars)).quantize(
    Decimal("0.01"), rounding=ROUND_FLOOR
)
```

and prove no extra `0.2 * ATR14` buffer is subtracted.

- [ ] **Step 7: Implement fixed anchor calculations**

For support profiles, calculate invalidation as `floor_cent(anchor - 0.2 * ATR14)`. Reject an anchor above the signal-day low with `ANCHOR_ABOVE_SIGNAL_LOW`. For ATR profile, store the computed invalidation as the anchor price and return no support buffer.

- [ ] **Step 8: Write failing shadow-plan invariant tests**

For each profile assert:

```python
decision = build_structure_stop_plan(
    setup, bars, CASE_RISK_BUDGET, "ALLOW", profile,
    valid_through_trade_date=date(2026, 8, 19),
)
assert decision.plan.trigger_price == formal_trigger
assert decision.plan.target_2r == formal_trigger + Decimal("2") * decision.plan.risk_distance
assert decision.plan.valid_through_trade_date == date(2026, 8, 19)
```

Add boundary cases immediately below the dynamic lower risk bound, exactly at it, exactly at 5%, and immediately above 5%. Add a historical high one cent below the target and require `INSUFFICIENT_TWO_R_SPACE`.

- [ ] **Step 9: Implement `build_structure_stop_plan`**

Reuse production cent rounding, risk budget, board-lot rounding, LIMITED budget halving, `nearest_resistance_above`, `structure_id`, and the formal risk interval. Return `PlanDecision(None, exact_reasons)` on failure and a normal `PricePlan` only when every unchanged downstream check passes. The returned plan may carry a calculated `maximum_shares`, but all enclosing research models must expose zero executable shares.

- [ ] **Step 10: Run Task 1 tests and regression**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_structure_stop_shadow.py \
  tests/unit/test_buy_point_planning.py \
  tests/unit/test_buy_point_patterns.py
```

Expected: all pass and production files remain unmodified.

- [ ] **Step 11: Commit Task 1**

```bash
git add stock-ai/stock_ai/buy_point_selection/structure_stop_shadow.py \
  stock-ai/tests/unit/test_buy_point_structure_stop_shadow.py
git commit -m "feat(stock-ai): calculate structure stop shadows"
```

**Checkpoint:** Report exact passing-test count, changed paths, and confirm no replay or MySQL work has begun.

---

### Task 2: Replay isolated primary and combined-failure diagnostic cohorts

**Files:**
- Modify: `stock_ai/buy_point_selection/structure_stop_shadow.py`
- Modify: `tests/unit/test_buy_point_structure_stop_shadow.py`

**Interfaces:**
- Consumes: Task 1 profiles/plan builder, production gates/detectors, point-in-time reference facts, `CASE_RISK_BUDGET`, `_diagnostic_price_plan`, and `second_trading_date_after`.
- Produces: `StructureStopBaselineHit`, `StructureStopCandidate`, `StructureStopDiagnostic`, `StructureStopRejection`, `StructureStopReplay`, and `replay_structure_stop_shadows()`.

- [ ] **Step 1: Write failing primary-cohort isolation tests**

Use injected setup and sector-snapshot builders. Require a row to enter `baseline_hits` only when every production gate passes and baseline diagnostic reasons equal exactly:

```python
("RISK_DISTANCE_OUT_OF_RANGE",)
```

Parameterize rejections for `RISK_DISTANCE_OUT_OF_RANGE + INSUFFICIENT_TWO_R_SPACE`, `POSITION_BELOW_BOARD_LOT`, incomplete coverage, holdings/base failure, anti-chase failure, market failure, sector failure, and missing setup.

- [ ] **Step 2: Define replay dataclasses**

Use:

```python
@dataclass(frozen=True)
class StructureStopBaselineHit:
    code: str
    signal_date: date
    setup: DetectedSetup
    market_status: str
    sector_code: str
    baseline_reasons: tuple[str, ...]
    executable_shares: int = 0


@dataclass(frozen=True)
class StructureStopCandidate:
    hit: StructureStopBaselineHit
    profile: StructureStopProfile
    anchor: StructureStopAnchor
    plan: PricePlan
    average_amount5_qian: Decimal
    two_r_space_buffer: Decimal
    executable_shares: int = 0
    status: str = "CASE_ANALYSIS_ONLY"
    trade_permission: str = "NO-TRADE"


@dataclass(frozen=True)
class StructureStopDiagnostic:
    code: str
    signal_date: date
    gate: str
    gate_reason: str
    baseline_reason: str
    label: str = "DIAGNOSTIC_ONLY_COMBINED_FAILURE"
    executable_shares: int = 0


@dataclass(frozen=True)
class StructureStopRejection:
    code: str
    signal_date: date
    profile_id: str | None
    stage: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class StructureStopReplay:
    signal_dates: tuple[date, ...]
    incomplete_dates: tuple[date, ...]
    baseline_hits: tuple[StructureStopBaselineHit, ...]
    candidates: tuple[StructureStopCandidate, ...]
    diagnostics: tuple[StructureStopDiagnostic, ...]
    rejections: tuple[StructureStopRejection, ...]
```

`StructureStopReplay` contains signal dates, incomplete dates, baseline hits, candidates, diagnostics, and rejections as immutable tuples.

- [ ] **Step 3: Implement production-order primary replay**

Bound each code to the final 120 bars through the signal date. Apply latest-bar, coverage, market, base, setup, anti-chase, membership, and sector logic in production order. Select the highest-quality setup exactly as existing gate-shadow replay does. Call `_diagnostic_price_plan` only after all gates pass and admit baseline hits only for the exact risk-only tuple. Generate each of the three profile plans independently and preserve profile-specific downstream rejection reasons.

- [ ] **Step 4: Write failing combined-failure diagnostic tests**

Require an exact single supported market reason or exact single supported sector reason plus an exact risk-only baseline reason to create one diagnostic row. Require diagnostics never to appear in `baseline_hits` or candidates. Multi-gate reasons, a price reason other than risk distance, or any hard gate failure must remain ordinary rejections.

- [ ] **Step 5: Implement diagnostic-only attribution**

Reuse the six supported gate reasons from the committed gate-shadow matrix. For a supported market failure, pass research-only planner status `LIMITED` into `_diagnostic_price_plan`, matching the existing gate-shadow diagnostic convention; never pass production `FREEZE` through as if it were an executable plan. For a sector failure, preserve the production passing market status. Do not construct alternate stop plans for diagnostic rows. Sort diagnostics by date, code, gate, and reason. Store no outcome-dependent values.

- [ ] **Step 6: Write future-leakage and zero-share tests**

Append future price bars and future memberships to an otherwise identical fixture. Assert baseline hits, anchors, candidates, diagnostics, and ordering are unchanged. Recursively assert all hit, anchor, candidate, and diagnostic share values are zero.

- [ ] **Step 7: Run Task 2 tests and regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_structure_stop_shadow.py \
  tests/unit/test_buy_point_gate_shadow_research.py \
  tests/unit/test_buy_point_case_review.py
```

- [ ] **Step 8: Commit Task 2**

```bash
git add stock-ai/stock_ai/buy_point_selection/structure_stop_shadow.py \
  stock-ai/tests/unit/test_buy_point_structure_stop_shadow.py
git commit -m "feat(stock-ai): replay structure stop cohorts"
```

**Checkpoint:** Report primary, diagnostic, and rejection behavior proven by tests. Do not start evaluation until acknowledged or explicitly told to continue.

---

### Task 3: Evaluate outcomes and freeze qualified profiles

**Files:**
- Create: `stock_ai/buy_point_selection/structure_stop_evaluation.py`
- Create: `tests/unit/test_buy_point_structure_stop_evaluation.py`

**Interfaces:**
- Consumes: `StructureStopCandidate`, `BuyPointBar`, `ExecutionCosts`, `evaluate_case_plan`, exact eight research identities, and Task 1 profile hash.
- Produces: `StructureStopOutcome`, `StructureStopMetrics`, `FrozenStructureStopProfile`, `StructureStopFreeze`, `evaluate_structure_stop_outcomes()`, `aggregate_structure_stop_metrics()`, `freeze_structure_stop_profiles()`, `validate_structure_stop_freeze()`, and `select_frozen_structure_stop_candidates()`.

- [ ] **Step 1: Write failing bounded-outcome tests**

Build deterministic triggered, not-triggered, target-first, stop-first, expiry-gain, and expiry-loss bars. Require evaluator output to match existing `case-evaluator-v1` costs and ignore bars after the explicit cutoff. Require diagnostics to be an unsupported evaluator input.

- [ ] **Step 2: Implement zero-share outcome adaptation**

Define:

```python
@dataclass(frozen=True)
class StructureStopOutcome:
    profile_id: str
    setup_type: str
    code: str
    signal_date: date
    outcome: CaseOutcome
    executable_shares: int = 0
```

Adapt each shadow candidate to `CaseCandidate` with tier `STRUCTURE_STOP_SHADOW`, evaluate only through cutoff, and sort by date, code, profile.

- [ ] **Step 3: Write failing aggregate-metric boundary tests**

Require both `setup_type="ALL"` rows per profile and setup-specific rows. Test exact boundaries: resolved 9/10, mean zero/positive, positive rate 49%/50%, stop-first 40%/41%. Null denominators must remain `None`.

- [ ] **Step 4: Implement metric aggregation**

Define the exact model below. Only `setup_type="ALL"` rows can feed freeze qualification. Use the four exact qualification rules from the spec.

```python
@dataclass(frozen=True)
class StructureStopMetrics:
    profile_id: str
    setup_type: str
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


@dataclass(frozen=True)
class FrozenStructureStopProfile:
    profile_id: str
    rank: int
    training_metrics: StructureStopMetrics
```

- [ ] **Step 5: Write failing eight-window freeze tests**

Require exactly eight distinct sorted training identities, exact formal hashes and profile hash, retrospective true, promotion false, canonical 64-character freeze hash, deterministic rank, and valid empty freeze. Reject seven or nine identities, duplicates, diagnostic IDs, setup-specific metrics used as frozen training metrics, non-qualifying profiles, tampered hash, or reordered ranks.

- [ ] **Step 6: Implement freeze and validation**

Rank qualifying profiles by descending mean net, descending positive rate, ascending stop rate, then profile ID. Define:

```python
@dataclass(frozen=True)
class StructureStopFreeze:
    schema: str
    training_identities: tuple[str, ...]
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    profiles: tuple[FrozenStructureStopProfile, ...]
    retrospective: bool
    empty: bool
    risk_coverage_complete: bool
    promotion_eligible: bool
    freeze_hash: str
```

- [ ] **Step 7: Write failing Top-5 selection tests**

Require only frozen profile candidates, deterministic profile-rank/quality/2R-buffer/amount/code ordering, code/date deduplication, maximum five per signal date, zero-share enforcement, and empty-freeze output `()` without backfill.

- [ ] **Step 8: Implement frozen selection**

Reject a non-positive maximum, nonzero shares, unsupported profiles, or diagnostic rows. Select per date without reading outcomes.

- [ ] **Step 9: Run Task 3 tests and regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_structure_stop_evaluation.py \
  tests/unit/test_buy_point_structure_stop_shadow.py \
  tests/unit/test_buy_point_gate_shadow_evaluation.py
```

- [ ] **Step 10: Commit Task 3**

```bash
git add stock-ai/stock_ai/buy_point_selection/structure_stop_evaluation.py \
  stock-ai/tests/unit/test_buy_point_structure_stop_evaluation.py
git commit -m "feat(stock-ai): evaluate structure stop shadows"
```

**Checkpoint:** Report qualification-boundary evidence and whether all frozen data structures remain research-only.

---

### Task 4: Write immutable research, freeze, screen, and settlement artifacts

**Files:**
- Create: `stock_ai/buy_point_selection/structure_stop_report.py`
- Create: `tests/unit/test_buy_point_structure_stop_report.py`

**Interfaces:**
- Consumes: replay, outcomes, metrics, freeze, v5 lineage, input/policy/profile hashes, forward selected candidates, and parent screen identity.
- Produces: `StructureStopResearchReview`, `StructureStopScreenCandidate`, `StructureStopForwardScreen`, `StructureStopForwardSettlement`, `structure_stop_research_payload()`, `write_structure_stop_research_revision()`, `structure_stop_freeze_payload()`, `write_structure_stop_freeze()`, `load_structure_stop_freeze()`, `structure_stop_screen_identity()`, `structure_stop_screen_payload()`, `write_structure_stop_forward_screen()`, `load_structure_stop_forward_screen()`, `structure_stop_settlement_payload()`, `write_structure_stop_forward_settlement()`, and concise Chinese Markdown renderers.

- [ ] **Step 1: Write failing research-artifact reconciliation tests**

Require exact schema/stage/safety labels, retrospective true, evaluator/cost versions, exact three profiles, primary/diagnostic separation, row-count reconciliation, risk coverage, promotion false, and recursive zero shares. Require diagnostics absent from candidate and metric keys.

- [ ] **Step 2: Implement deterministic research serialization**

Sort profiles by matrix order and all rows by date/code/profile. Identity includes schema, stage, signal dates, cutoff, v5 case identity, input fingerprint, rule/policy/profile hashes, evaluator, and cost versions. Payload metrics must exactly equal serialized row lengths.

Use these forward lineage models:

```python
@dataclass(frozen=True)
class StructureStopScreenCandidate:
    candidate: StructureStopCandidate
    profile_rank: int


@dataclass(frozen=True)
class StructureStopForwardScreen:
    signal_date: date
    input_fingerprint: str
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    freeze_hash: str
    candidates: tuple[StructureStopScreenCandidate, ...]
    risk_coverage_complete: bool


@dataclass(frozen=True)
class StructureStopForwardSettlement:
    parent_screen_identity: str
    signal_date: date
    outcome_cutoff: date
    outcome_dates: tuple[date, ...]
    freeze_hash: str
    input_fingerprint: str
    candidates: tuple[StructureStopScreenCandidate, ...]
    outcomes: tuple[StructureStopOutcome, ...]
    risk_coverage_complete: bool
```

- [ ] **Step 3: Write failing immutable research/freeze tests**

Write the same value twice and require identical returned paths. Change risk coverage while preserving lineage and require `immutable artifact content mismatch`. Tamper with a freeze metric, rank, training identity, safety label, promotion flag, or hash and require loader failure.

- [ ] **Step 4: Implement exclusive writers and strict loaders**

Use file mode `x`; on `FileExistsError`, compare complete UTF-8 content. Write deterministic sorted-key indented JSON with one terminal newline plus Markdown. Freeze filename is `freeze-{64_hex_hash}.json`.

- [ ] **Step 5: Write failing forward-screen isolation tests**

Require stage `screen`, retrospective false, freeze/input hashes, planner version, zero to five candidates, trigger/invalidation/2R/structure/profile-rank fields, and recursive zero shares. Recursively reject keys `outcomes`, `net_return`, `mfe`, `mae`, or any future price-bar date. Reject duplicate code/date, unsupported profiles, nonzero shares, or more than five candidates.

- [ ] **Step 6: Implement screen identity and writer**

Use filename `screen_YYYYMMDD_{16_hex_identity}.json`. Identity includes formal hashes, profile matrix, freeze hash, input fingerprint, and `planner_version=price-plan-v1`.

- [ ] **Step 7: Write failing settlement-lineage tests**

Require exact parent identity, freeze hash, candidate keys/ranks unchanged, exactly one outcome per screen candidate, exactly five ordered result sessions, zero shares, and a separate file. Change one code, profile, rank, cutoff, or freeze hash and require validation failure. Assert original screen bytes remain unchanged.

- [ ] **Step 8: Implement separate settlement artifact**

Use filename `settlement_YYYYMMDD_cutoff-YYYYMMDD_{16_hex_identity}.json`. Include resolved metrics and explicit non-promotion language. Never open the parent screen for writing.

- [ ] **Step 9: Run Task 4 tests and regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_structure_stop_report.py \
  tests/unit/test_buy_point_structure_stop_evaluation.py \
  tests/unit/test_buy_point_structure_stop_shadow.py \
  tests/unit/test_buy_point_gate_shadow_report.py
```

- [ ] **Step 10: Commit Task 4**

```bash
git add stock-ai/stock_ai/buy_point_selection/structure_stop_report.py \
  stock-ai/tests/unit/test_buy_point_structure_stop_report.py
git commit -m "feat(stock-ai): record structure stop evidence"
```

**Checkpoint:** Report immutable artifact schemas and prove forward screens contain no result fields.

---

### Task 5: Add manual research and freeze orchestration

**Files:**
- Create: `scripts/analysis/review_buy_point_structure_stops.py`
- Create: `tests/unit/test_review_buy_point_structure_stops_cli.py`

**Interfaces:**
- Consumes: `load_mysql_case_inputs`, `load_v5_recall_lineage`, `case_input_fingerprint`, local trading dates, eight v5 case artifacts, eight structure-stop research artifacts, and Task 1–4 APIs.
- Produces: parser stages `research`, `freeze`, `screen`, `settle`; `derive_structure_stop_windows()`; `build_structure_stop_research_review()`; `build_structure_stop_freeze_from_artifacts()`; and exit code 2 on fail-closed validation.

- [ ] **Step 1: Write failing parser and calendar-block tests**

Require all four manual stages. Inject a confirmed date sequence of 80 sessions ending 2026-08-14 and require eight blocks, each with five signal and five result dates, the final signal block ending 2026-08-07, and final cutoff 2026-08-14. Remove one date and require failure instead of weekday inference.

- [ ] **Step 2: Implement parser and `derive_structure_stop_windows`**

Research accepts explicit start, end, cutoff, and v5 path. Freeze accepts exactly eight repeated `--research-artifact` arguments. Screen accepts signal date and freeze path. Settle accepts screen path and cutoff. Calendar derivation uses only sorted confirmed dates supplied by the read-only runtime.

- [ ] **Step 3: Write failing research-builder tests**

Inject one `CaseReviewInputs` loader and assert one call, exact signal/result sessions, complete holdings, all three profiles over the full universe, formal strict baseline for exact-date recall, explicit announcement coverage, and no external writes. Assert combined diagnostics do not affect metrics.

- [ ] **Step 4: Implement `build_structure_stop_research_review`**

Load inputs once, validate the requested block against the eight derived blocks, load exact v5 lineage, run structure-stop replay, evaluate every primary candidate, aggregate overall and setup metrics, rebuild formal strict candidates for recall comparison, and return a retrospective review.

- [ ] **Step 5: Write failing freeze reconstruction tests**

Use eight real-format payload fixtures. Reject duplicate identities, a wrong block, changed versions/hashes, nonzero shares, candidate/outcome mismatch, diagnostics counted as candidates, edited summary metrics, or a reported qualifier not reproduced from raw rows. Require a valid empty freeze.

- [ ] **Step 6: Implement `build_structure_stop_freeze_from_artifacts`**

Strictly reconstruct candidate profile/setup IDs and outcomes, recompute each artifact's metrics, aggregate all eight raw windows, use only `setup_type="ALL"` metrics for qualification, and create the canonical freeze. Do not trust serialized `qualifies` booleans without recomputation.

- [ ] **Step 7: Write main exit-code tests**

Inject loaders/writers. Require `0` plus both output paths for valid empty research/freeze, and `2` with a concise Chinese error for incomplete lineage, missing holdings, or immutable mismatch. Assert no scheduler or database writer is imported.

- [ ] **Step 8: Run Task 5 tests and regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_review_buy_point_structure_stops_cli.py \
  tests/unit/test_buy_point_structure_stop_report.py \
  tests/unit/test_buy_point_structure_stop_evaluation.py \
  tests/unit/test_buy_point_structure_stop_shadow.py \
  tests/unit/test_review_buy_point_gate_shadows_cli.py
```

- [ ] **Step 9: Commit Task 5**

```bash
git add stock-ai/scripts/analysis/review_buy_point_structure_stops.py \
  stock-ai/tests/unit/test_review_buy_point_structure_stops_cli.py
git commit -m "feat(stock-ai): run structure stop research"
```

**Checkpoint:** Report exact manual research/freeze commands and stop before forward implementation.

---

### Task 6: Add bounded forward screen and settlement plus documentation

**Files:**
- Modify: `scripts/analysis/review_buy_point_structure_stops.py`
- Modify: `tests/unit/test_review_buy_point_structure_stops_cli.py`
- Modify: `docs/CAPABILITIES.md`

**Interfaces:**
- Consumes: a validated non-empty or empty freeze, local `trading_day_status(refresh=False)`, read-only signal inputs bounded through signal date, and a preserved parent screen artifact.
- Produces: `load_mysql_structure_stop_screen_inputs()`, `load_mysql_structure_stop_settlement_inputs()`, `build_structure_stop_forward_screen()`, `build_structure_stop_forward_settlement()`, and documented manual commands.

- [ ] **Step 1: Write failing confirmed-calendar and future-bar tests**

Inject local calendar statuses and require the signal session plus exact next two plan-validity sessions. A `None` status fails closed and never refreshes. Inject any bar after signal date and require `screen input contains future price bars`.

- [ ] **Step 2: Implement bounded read-only screen loader**

Use existing `_trade_dates`, `_load_daily_bars`, `_load_market_aggregates`, benchmark snapshots, `SQLReferenceRepository`, and `_load_holdings_by_date`. Query price bars only through signal date. Append the two confirmed future dates only to the in-memory trading-date tuple used for plan validity.

- [ ] **Step 3: Write failing frozen Top-5 screen tests**

Require only frozen primary profile candidates, deterministic deduplication, maximum five, zero shares, no outcomes, full formal/profile/freeze lineage, signal date after the retrospective terminal signal block, and valid empty screen. Reject diagnostics and unsupported profile IDs.

- [ ] **Step 4: Implement `build_structure_stop_forward_screen`**

Validate freeze against current policy/profile hashes, run only signal-time replay, select with Task 3 ranking, convert to ranked screen candidates, and preserve explicit risk-coverage completeness. Do not evaluate outcomes.

- [ ] **Step 5: Write failing settlement tests**

Inject a bounded loader and a real screen artifact. Require exactly five later sessions, only screen codes evaluated, candidate keys/ranks unchanged, parent identity exact, original screen bytes unchanged, and a separate settlement output. Reject early cutoff, sixth session, missing outcome, or changed freeze hash.

- [ ] **Step 6: Implement settlement loader and builder**

Load bars only from the signal history through explicit cutoff, derive exactly five later confirmed sessions, reconstruct frozen screen plans, evaluate only preserved screen candidates, and write a new settlement artifact. Identical reruns verify content.

- [ ] **Step 7: Document the full manual workflow**

Add `买点结构止损影子研究` to `docs/CAPABILITIES.md`. Include research, freeze, screen, and settle command shapes; eight-window retrospective limitation; primary versus diagnostic cohort separation; zero-share/manual semantics; valid empty outputs; and absence of scheduling, notification, holding, memory, and order writes.

- [ ] **Step 8: Run Task 6 tests and regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_review_buy_point_structure_stops_cli.py \
  tests/unit/test_buy_point_structure_stop_report.py \
  tests/unit/test_buy_point_structure_stop_evaluation.py \
  tests/unit/test_buy_point_structure_stop_shadow.py \
  tests/unit/test_review_buy_point_gate_shadows_cli.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py \
  tests/unit/test_review_buy_point_case_cli.py
```

- [ ] **Step 9: Commit Task 6**

```bash
git add stock-ai/scripts/analysis/review_buy_point_structure_stops.py \
  stock-ai/tests/unit/test_review_buy_point_structure_stops_cli.py \
  stock-ai/docs/CAPABILITIES.md
git commit -m "feat(stock-ai): observe structure stops forward"
```

**Checkpoint:** Report forward safety proofs and wait before running real historical research.

---

### Task 7: Run regression and the eight LAN research blocks one stage at a time

**Files:**
- Verify only; generated ignored artifacts are not committed.

**Interfaces:**
- Consumes: committed CLI, local `.env` credentials overridden only in process memory to `192.168.1.13:3306`, confirmed local trading dates, existing/new v5 case artifacts, and read-only reference/holdings inputs.
- Produces: eight immutable research pairs, one freeze pair, exact cohort/metric summary, and no automatic screen when freeze is empty.

- [ ] **Step 1: Run the complete buy-point regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  $(rg --files tests/unit | rg '/test_(review_)?buy_point.*\.py$')
```

Expected: all buy-point tests pass. Record unrelated repository-wide collection failures separately rather than modifying out-of-scope tests.

- [ ] **Step 2: Derive and print the exact eight blocks**

After applying the in-process URL override shown in Step 4, run this read-only query through the committed helper and print JSON containing each block's five signal dates and five result dates:

```bash
PYTHONPATH=. .venv/bin/python -c '
import json, os
from datetime import date
from sqlalchemy import create_engine
from stock_ai.buy_point_selection.historical_replay_runtime import _trade_dates
from scripts.analysis.review_buy_point_structure_stops import derive_structure_stop_windows
engine = create_engine(os.environ["MYSQL_URL"], pool_pre_ping=True)
dates = _trade_dates(engine, date(2026, 5, 1), date(2026, 8, 14))
windows = derive_structure_stop_windows(dates, terminal_cutoff=date(2026, 8, 14))
print(json.dumps([{
    "signal_dates": [value.isoformat() for value in signal_dates],
    "outcome_dates": [value.isoformat() for value in outcome_dates],
} for signal_dates, outcome_dates in windows], indent=2))
'
```

Verify the final values are signal end `2026-08-07` and cutoff `2026-08-14`. Do not create research artifacts in this step.

- [ ] **Step 3: Ensure one immutable v5 artifact per block**

For each missing earlier block, run the existing case CLI once with its exact derived start/end/cutoff. Reuse the three already validated v5 artifacts for July 20–24, July 27–31, and August 3–7. Confirm every v5 artifact is `CASE_ANALYSIS_ONLY / NO-TRADE`, reconciles daily winner rows, and has zero executable shares.

- [ ] **Step 4: Run research block 1 and checkpoint**

Override only the in-process URL host/port:

```bash
set -a
source .env
set +a
MYSQL_URL="${MYSQL_URL/db.yoloworld.site:8886/192.168.1.13:3306}"
export MYSQL_URL
```

Run the first exact research command printed in Step 2 with its v5 file. Summarize baseline hits, candidates by profile, diagnostics, triggered/resolved counts, and risk coverage. Stop and report before block 2.

- [ ] **Step 5: Run research blocks 2 through 8 with one checkpoint after each**

For each block, execute one manual `research` command, validate immutable JSON, summarize counts, and report before continuing. Do not chain all eight commands. On validation failure, stop at that block and preserve all earlier immutable artifacts.

- [ ] **Step 6: Freeze only after all eight artifacts validate**

Use the eight explicit JSON paths as eight repeated `--research-artifact` arguments. Rerun the identical freeze command once to prove byte-for-byte immutability.

- [ ] **Step 7: Summarize the real freeze result**

Report for each profile: raw baseline hits, candidates, triggered/resolved, mean/median net, positive rate, stop rate, MFE/MAE, qualification reasons, and v5 winner overlap. State whether freeze is empty. Never create fallback profiles or claim profitability from an observed eight-block set.

- [ ] **Step 8: Run a fresh final regression and scoped cleanliness check**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  $(rg --files tests/unit | rg '/test_(review_)?buy_point.*\.py$')
git diff --check -- \
  stock-ai/stock_ai/buy_point_selection/structure_stop_shadow.py \
  stock-ai/stock_ai/buy_point_selection/structure_stop_evaluation.py \
  stock-ai/stock_ai/buy_point_selection/structure_stop_report.py \
  stock-ai/scripts/analysis/review_buy_point_structure_stops.py \
  stock-ai/tests/unit/test_buy_point_structure_stop_shadow.py \
  stock-ai/tests/unit/test_buy_point_structure_stop_evaluation.py \
  stock-ai/tests/unit/test_buy_point_structure_stop_report.py \
  stock-ai/tests/unit/test_review_buy_point_structure_stops_cli.py \
  stock-ai/docs/CAPABILITIES.md
```

Expected: all relevant tests pass and scoped tracked implementation paths are clean after commits.

**Final checkpoint:** Deliver exact evidence, known repository-wide unrelated failures, artifact paths, commit hashes, and the next manual action. Do not run a forward screen automatically.
