# 2R Conditional Shadow and Opportunity Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add signal-time 1.5R-to-2R conditional shadow classification and overlapping-signal opportunity deduplication to the read-only short-window case review.

**Architecture:** Keep all new behavior inside the existing `buy_point_selection.case_review` research boundary. Pure functions classify conditional candidates and build deterministic episodes; the CLI runtime assembles those values from existing raw candidates and outcomes; the report emits an immutable v2 artifact while retaining every v1 audit field and raw row.

**Tech Stack:** Python 3.11, frozen dataclasses, `Decimal`, pytest, SQLAlchemy read-only runtime, existing JSON/Markdown report renderer.

## Global Constraints

- Rule version `buy-point-selection-3.1.0` and every production threshold remain unchanged.
- Conditional admission is exactly `1.5 <= effective_resistance_r < 2.0` where `effective_resistance_r = (nearest_resistance - trigger_price) / risk_distance`.
- Every conditional candidate has zero executable shares and remains `CASE_ANALYSIS_ONLY / NO-TRADE`.
- Episode construction uses signal-time candidate facts only and preserves the earliest overlapping plan.
- Raw candidates and raw outcomes remain present for audit compatibility.
- No database schema, scheduler, notification, decision-memory, holding, profile, or order mutation is allowed.
- Generated case artifacts remain ignored by Git.

---

### Task 1: Add the conditional 2R classifier

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_review.py:45-190`
- Test: `stock-ai/tests/unit/test_buy_point_case_review.py`

**Interfaces:**
- Consumes: `CaseCandidate`, `GateTrace`, `PricePlan.risk_distance`, and trace metric `nearest_resistance`.
- Produces: `ConditionalShadowDecision` and `classify_conditional_two_r_shadow(candidate, trace)`.

- [ ] **Step 1: Add a real candidate fixture and failing inclusive-boundary test**

Add imports for `CaseCandidate`, `ConditionalShadowDecision`, `DetectedSetup`, `SetupType`, and `PricePlan`, then add a local `_case_candidate` fixture that creates a zero-share `NEAR_MISS` candidate with trigger 10, invalidation 9, target 12, risk distance 1, and a configurable signal date.

```python
def _case_candidate(
    signal_date: date,
    *,
    code: str = "600001",
    valid_through: date | None = None,
    tier: str = "NEAR_MISS",
    executable_shares: int = 0,
) -> CaseCandidate:
    setup = DetectedSetup(
        code,
        SetupType.TREND_PULLBACK,
        signal_date,
        signal_date - timedelta(days=2),
        Decimal("9.99"),
        Decimal("9.10"),
        Decimal("0.40"),
        ("ORDERLY_LOW_VOLUME_PULLBACK",),
        {},
    )
    plan = PricePlan(
        f"structure-{code}-{signal_date.isoformat()}",
        code,
        setup.setup_type,
        signal_date,
        Decimal("9.80"),
        Decimal("10.00"),
        Decimal("9.00"),
        Decimal("12.00"),
        Decimal("1.00"),
        Decimal("2.00"),
        100,
        valid_through or signal_date + timedelta(days=2),
    )
    return CaseCandidate(
        code,
        signal_date,
        setup,
        plan,
        tier,
        "INSUFFICIENT_TWO_R_SPACE" if tier == "NEAR_MISS" else None,
        (Decimal("0.25"), Decimal("-0.40"), Decimal("-200000"), code),
        executable_shares,
    )


def test_conditional_two_r_shadow_accepts_inclusive_one_point_five_r() -> None:
    candidate = _case_candidate(SIGNAL)
    trace = GateTrace(
        "600001",
        SIGNAL,
        ("INSUFFICIENT_TWO_R_SPACE",),
        ("BASE", "SETUP", "SECTOR"),
        {"nearest_resistance": Decimal("11.50")},
    )

    decision = classify_conditional_two_r_shadow(candidate, trace)

    assert decision == ConditionalShadowDecision(
        True,
        "TWO_R_CONDITIONAL_SHADOW",
        Decimal("1.50"),
    )
    assert candidate.executable_shares == 0
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_case_review.py::test_conditional_two_r_shadow_accepts_inclusive_one_point_five_r
```

Expected: collection fails because `ConditionalShadowDecision` or `classify_conditional_two_r_shadow` does not exist.

- [ ] **Step 3: Implement the immutable decision and minimal classifier**

Add this frozen model and behavior near `NearMissDecision`:

```python
@dataclass(frozen=True)
class ConditionalShadowDecision:
    admitted: bool
    tier: str | None
    effective_resistance_r: Decimal | None


def classify_conditional_two_r_shadow(
    candidate: CaseCandidate,
    trace: GateTrace,
) -> ConditionalShadowDecision:
    reasons = tuple(dict.fromkeys(trace.failed_reasons))
    if (
        candidate.tier != "NEAR_MISS"
        or candidate.executable_shares != 0
        or reasons != ("INSUFFICIENT_TWO_R_SPACE",)
    ):
        return ConditionalShadowDecision(False, None, None)
    try:
        resistance = Decimal(str(trace.metrics["nearest_resistance"]))
        risk = candidate.plan.risk_distance
        effective_r = (resistance - candidate.plan.trigger_price) / risk
    except (KeyError, InvalidOperation, TypeError, ZeroDivisionError):
        return ConditionalShadowDecision(False, None, None)
    if not effective_r.is_finite() or risk <= 0:
        return ConditionalShadowDecision(False, None, None)
    admitted = Decimal("1.5") <= effective_r < Decimal("2")
    return ConditionalShadowDecision(
        admitted,
        "TWO_R_CONDITIONAL_SHADOW" if admitted else None,
        effective_r,
    )
```

Import `InvalidOperation` from `decimal`.

- [ ] **Step 4: Verify GREEN**

Run the focused test from Step 2. Expected: one passing test.

- [ ] **Step 5: Add failing rejection-boundary tests**

Add a parameterized test with hand-derived expected decisions for resistance `11.49`, `11.50`, and `12.00`, plus separate cases for a sector failure, two failures, a missing metric, a non-near-miss tier, and a non-zero executable share count. Assert that only resistance `11.50` is admitted and that rejected decisions never expose the conditional tier.

```python
@pytest.mark.parametrize(
    ("resistance", "expected"),
    (("11.49", False), ("11.50", True), ("12.00", False)),
)
def test_conditional_two_r_shadow_enforces_both_r_boundaries(
    resistance: str,
    expected: bool,
) -> None:
    candidate = _case_candidate(SIGNAL)
    trace = GateTrace(
        "600001",
        SIGNAL,
        ("INSUFFICIENT_TWO_R_SPACE",),
        ("BASE", "SETUP", "SECTOR"),
        {"nearest_resistance": Decimal(resistance)},
    )
    decision = classify_conditional_two_r_shadow(candidate, trace)
    assert decision.admitted is expected
    assert (decision.tier is not None) is expected


@pytest.mark.parametrize(
    ("candidate_kwargs", "reasons", "metrics"),
    (
        ({}, ("SECTOR_BREADTH_WEAK",), {"nearest_resistance": Decimal("11.50")}),
        ({}, ("INSUFFICIENT_TWO_R_SPACE", "SECTOR_BREADTH_WEAK"), {"nearest_resistance": Decimal("11.50")}),
        ({}, ("INSUFFICIENT_TWO_R_SPACE",), {}),
        ({"tier": "STRICT_SHADOW"}, ("INSUFFICIENT_TWO_R_SPACE",), {"nearest_resistance": Decimal("11.50")}),
        ({"executable_shares": 100}, ("INSUFFICIENT_TWO_R_SPACE",), {"nearest_resistance": Decimal("11.50")}),
    ),
)
def test_conditional_two_r_shadow_rejects_non_diagnostic_inputs(
    candidate_kwargs: dict[str, object],
    reasons: tuple[str, ...],
    metrics: dict[str, Decimal],
) -> None:
    candidate = _case_candidate(SIGNAL, **candidate_kwargs)
    trace = GateTrace("600001", SIGNAL, reasons, (), metrics)
    assert classify_conditional_two_r_shadow(candidate, trace).tier is None
```

- [ ] **Step 6: Run all case-review unit tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_case_review.py
```

Expected: all tests pass with no warnings.

- [ ] **Step 7: Commit the classifier**

```bash
git add stock_ai/buy_point_selection/case_review.py tests/unit/test_buy_point_case_review.py
git commit -m "feat(stock-ai): classify conditional 2R shadows"
```

---

### Task 2: Build deterministic opportunity episodes

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_review.py:70-210`
- Test: `stock-ai/tests/unit/test_buy_point_case_review.py`

**Interfaces:**
- Consumes: `Sequence[CaseCandidate]` and the representative plan's `valid_through_trade_date`.
- Produces: `OpportunityEpisode`, `ConditionalShadowOpportunity`, `build_opportunity_episodes(candidates)`, and `build_conditional_two_r_shadow(episodes, traces)`.

- [ ] **Step 1: Write failing overlap and expiry tests**

Use `dataclasses.replace` on `_case_candidate` to create signals on August 3, August 4, and August 6. Give the August 3 representative a validity date of August 5.

```python
def test_overlapping_same_code_signals_form_one_opportunity_episode() -> None:
    first = _case_candidate(date(2026, 8, 3), valid_through=date(2026, 8, 5))
    overlapping = _case_candidate(date(2026, 8, 4), valid_through=date(2026, 8, 6))

    episodes = build_opportunity_episodes((overlapping, first))

    assert len(episodes) == 1
    assert episodes[0].representative == first
    assert episodes[0].member_signal_dates == (
        date(2026, 8, 3),
        date(2026, 8, 4),
    )


def test_same_code_signal_after_representative_validity_starts_new_episode() -> None:
    first = _case_candidate(date(2026, 8, 3), valid_through=date(2026, 8, 5))
    later = _case_candidate(date(2026, 8, 6), valid_through=date(2026, 8, 10))

    assert len(build_opportunity_episodes((first, later))) == 2
```

- [ ] **Step 2: Run both tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_case_review.py::test_overlapping_same_code_signals_form_one_opportunity_episode \
  tests/unit/test_buy_point_case_review.py::test_same_code_signal_after_representative_validity_starts_new_episode
```

Expected: collection fails because the episode model and builder are absent.

- [ ] **Step 3: Implement episode models, identity, and grouping**

Add frozen `OpportunityEpisode` and `ConditionalShadowOpportunity` dataclasses exactly as specified in the design. Build the episode ID from this payload:

```python
payload = ":".join(
    (
        representative.code,
        representative.signal_date.isoformat(),
        representative.plan.structure_id,
    )
)
episode_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

Sort candidates by signal date, normalized code, ranking key, tier, and structure ID. Maintain only the latest episode per code; append a candidate to it when `candidate.signal_date <= representative.plan.valid_through_trade_date`, otherwise start a new episode. Store unique sorted member dates and tiers. Collapse exact duplicates identified by code, signal date, tier, and structure ID.

- [ ] **Step 4: Verify GREEN and add separation tests**

Run the focused tests, then add tests proving different codes never merge and a setup-type or tier change still merges while the representative plan is active. Expected: all episode tests pass.

```python
def test_different_codes_never_share_an_episode() -> None:
    first = _case_candidate(date(2026, 8, 3), code="600001")
    second = _case_candidate(date(2026, 8, 4), code="600002")
    assert len(build_opportunity_episodes((first, second))) == 2


def test_tier_change_does_not_split_an_active_same_code_episode() -> None:
    first = _case_candidate(date(2026, 8, 3), valid_through=date(2026, 8, 5))
    second = _case_candidate(
        date(2026, 8, 4),
        valid_through=date(2026, 8, 6),
        tier="STRICT_SHADOW",
    )
    episodes = build_opportunity_episodes((first, second))
    assert len(episodes) == 1
    assert episodes[0].member_tiers == ("NEAR_MISS", "STRICT_SHADOW")


def test_setup_type_change_does_not_split_an_active_same_code_episode() -> None:
    first = _case_candidate(date(2026, 8, 3), valid_through=date(2026, 8, 5))
    second = _case_candidate(date(2026, 8, 4), valid_through=date(2026, 8, 6))
    changed_setup = replace(second.setup, setup_type=SetupType.PRE_BREAKOUT)
    changed_plan = replace(second.plan, setup_type=SetupType.PRE_BREAKOUT)
    second = replace(second, setup=changed_setup, plan=changed_plan)
    assert len(build_opportunity_episodes((first, second))) == 1


def test_exact_duplicate_candidate_is_recorded_once() -> None:
    candidate = _case_candidate(date(2026, 8, 3))
    episodes = build_opportunity_episodes((candidate, candidate))
    assert len(episodes) == 1
    assert episodes[0].member_signal_dates == (date(2026, 8, 3),)
```

- [ ] **Step 5: Write the failing cohort-builder test**

Construct one admitted 1.5R episode and one rejected 1.49R episode with their signal-date traces. Assert `build_conditional_two_r_shadow` returns only the admitted episode ID, its original zero-share candidate, and `Decimal("1.50")`.

```python
def test_conditional_cohort_contains_only_admitted_episode_representatives() -> None:
    admitted = _case_candidate(date(2026, 8, 3), code="600001")
    rejected = _case_candidate(date(2026, 8, 3), code="600002")
    episodes = build_opportunity_episodes((admitted, rejected))
    traces = {
        (date(2026, 8, 3), "600001"): GateTrace(
            "600001", date(2026, 8, 3),
            ("INSUFFICIENT_TWO_R_SPACE",), (),
            {"nearest_resistance": Decimal("11.50")},
        ),
        (date(2026, 8, 3), "600002"): GateTrace(
            "600002", date(2026, 8, 3),
            ("INSUFFICIENT_TWO_R_SPACE",), (),
            {"nearest_resistance": Decimal("11.49")},
        ),
    }
    cohort = build_conditional_two_r_shadow(episodes, traces)
    assert len(cohort) == 1
    assert cohort[0].candidate == admitted
    assert cohort[0].effective_resistance_r == Decimal("1.50")
```

- [ ] **Step 6: Implement the cohort builder and run the full case-review tests**

For each episode, fetch the representative trace by `(signal_date, code)`, skip absent traces, call `classify_conditional_two_r_shadow`, and emit only admitted `ConditionalShadowOpportunity` values sorted by episode ID.

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_case_review.py
```

Expected: all tests pass.

- [ ] **Step 7: Commit episode construction**

```bash
git add stock_ai/buy_point_selection/case_review.py tests/unit/test_buy_point_case_review.py
git commit -m "feat(stock-ai): deduplicate case opportunities"
```

---

### Task 3: Assemble episodes and exact outcomes in the CLI runtime

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_review.py:90-150,202-250`
- Modify: `stock-ai/scripts/analysis/review_buy_point_case.py:20-150`
- Test: `stock-ai/tests/unit/test_buy_point_case_review.py`
- Test: `stock-ai/tests/unit/test_review_buy_point_case_cli.py`

**Interfaces:**
- Consumes: raw replay candidates, raw `CaseOutcome` values, `build_opportunity_episodes`, and `build_conditional_two_r_shadow`.
- Produces: exact `CaseOutcome.structure_id`, `_build_case_research_layers(replay)`, `CaseReview.episodes`, and `CaseReview.conditional_two_r_shadow`.

- [ ] **Step 1: Write the failing exact-outcome identity test**

Extend the existing `evaluate_case_plan` test to assert:

```python
outcome = evaluate_case_plan(candidate, bars, outcome_cutoff=cutoff)
assert outcome.structure_id == candidate.plan.structure_id
```

Run that one test. Expected: failure because `CaseOutcome` does not expose `structure_id`.

- [ ] **Step 2: Add backward-compatible model fields and populate structure ID**

Add `structure_id: str = ""` as the final `CaseOutcome` field. Add these final `CaseReview` fields:

```python
episodes: tuple[OpportunityEpisode, ...] = ()
conditional_two_r_shadow: tuple[ConditionalShadowOpportunity, ...] = ()
```

Set `structure_id=candidate.plan.structure_id` in `evaluate_case_plan`. Run `tests/unit/test_buy_point_case_review.py`; expected: all tests pass without changing existing positional fixtures.

- [ ] **Step 3: Write the failing runtime assembly test**

In `test_review_buy_point_case_cli.py`, construct a real `CaseSignalReplay` with two manually created same-code near-miss candidates on overlapping dates and a 1.5R trace. Call `_build_case_research_layers(replay)` directly and assert it returns both raw candidates, one episode, and one conditional opportunity. This exercises the real assembly boundary without mocking price replay or the database.

```python
def test_research_layers_keep_raw_candidates_and_build_one_episode() -> None:
    first = _case_candidate(date(2026, 8, 3), valid_through=date(2026, 8, 5))
    second = _case_candidate(date(2026, 8, 4), valid_through=date(2026, 8, 6))
    trace = GateTrace(
        "600001",
        date(2026, 8, 3),
        ("INSUFFICIENT_TWO_R_SPACE",),
        (),
        {"nearest_resistance": Decimal("11.50")},
    )
    replay = CaseSignalReplay(
        {(date(2026, 8, 3), "600001"): trace},
        (),
        (),
        (first, second),
    )

    candidates, episodes, conditional = _build_case_research_layers(replay)

    assert candidates == (first, second)
    assert len(episodes) == 1
    assert len(conditional) == 1
    assert conditional[0].episode_id == episodes[0].episode_id
```

- [ ] **Step 4: Run the runtime test and verify RED**

Run the new test only. Expected: collection fails because `_build_case_research_layers` does not exist.

- [ ] **Step 5: Integrate pure assembly after raw outcome evaluation**

Add this pure helper to `review_buy_point_case.py` and use it from `DefaultRuntime.build_review`:

```python
def _build_case_research_layers(
    replay: CaseSignalReplay,
) -> tuple[
    tuple[CaseCandidate, ...],
    tuple[OpportunityEpisode, ...],
    tuple[ConditionalShadowOpportunity, ...],
]:
    candidates = (*replay.strict_shadow, *replay.near_misses)
    episodes = build_opportunity_episodes(candidates)
    conditional = build_conditional_two_r_shadow(episodes, replay.traces)
    return candidates, episodes, conditional
```

Pass both research-layer values into `CaseReview`. Keep evaluating every raw candidate exactly once and do not call `evaluate_case_plan` again for representatives.

- [ ] **Step 6: Run runtime and case-review test files**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_case_review.py \
  tests/unit/test_review_buy_point_case_cli.py
```

Expected: all tests pass, including the existing incomplete-data and read-only CLI tests.

- [ ] **Step 7: Commit runtime integration**

```bash
git add stock_ai/buy_point_selection/case_review.py scripts/analysis/review_buy_point_case.py tests/unit/test_buy_point_case_review.py tests/unit/test_review_buy_point_case_cli.py
git commit -m "feat(stock-ai): assemble deduplicated case episodes"
```

---

### Task 4: Render immutable v2 episode and cohort metrics

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_report.py:1-220`
- Test: `stock-ai/tests/unit/test_buy_point_case_report.py`

**Interfaces:**
- Consumes: `CaseReview.episodes`, `CaseReview.conditional_two_r_shadow`, and raw outcomes keyed by code, signal date, tier, and structure ID.
- Produces: schema `buy-point-case-review-v2`, schema-aware identity, `opportunity_episodes`, `conditional_two_r_shadow`, episode metrics, and updated Markdown.

- [ ] **Step 1: Write the failing schema and immutable-identity test**

Build a review with one episode and assert:

```python
payload = case_payload(review)
assert payload["schema"] == "buy-point-case-review-v2"
assert payload["opportunity_episodes"][0]["member_signal_dates"] == [
    "2026-08-03",
    "2026-08-04",
]
assert payload["metrics"]["raw_candidates"] == 2
assert payload["metrics"]["opportunity_episodes"] == 1
```

Call `case_identity(review, schema="buy-point-case-review-v1")` and `case_identity(review, schema="buy-point-case-review-v2")`; assert the values differ because schema version participates in hashing.

- [ ] **Step 2: Run focused report tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_case_report.py
```

Expected: failures for the v1 schema and missing episode fields.

- [ ] **Step 3: Add schema-aware identity and exact outcome lookup**

Define `CASE_REPORT_SCHEMA = "buy-point-case-review-v2"` and change the signature to `case_identity(review: CaseReview, *, schema: str = CASE_REPORT_SCHEMA) -> str`. Include `schema` in the hash payload. Index raw outcomes by `(code, signal_date, tier, structure_id)`. For each episode, reuse the exact representative outcome when present; never simulate another trade.

- [ ] **Step 4: Add episode and cohort payloads**

Each episode payload must contain episode ID, representative code/date/tier/structure ID, member dates, member tiers, and either the exact outcome payload or `null`. Each conditional payload must contain episode ID, code, signal date, fixed tier `TWO_R_CONDITIONAL_SHADOW`, `effective_resistance_r`, and `executable_shares: 0`.

- [ ] **Step 5: Add episode-level metrics and failing behavioral assertions**

Compute raw and episode totals, resolved successes, triggered count, expired count, stop-first count, and mean net return from representative outcomes only. Exclude missing and `PENDING` outcomes from resolved denominators. Add tests where two successful raw rows merge into one successful episode and where a missing representative outcome contributes to episode count but not resolved count.

```python
def test_episode_metrics_count_overlapping_success_once() -> None:
    payload = case_payload(_review_with_two_overlapping_successes())
    assert payload["metrics"]["raw_outcome_successes"] == 2
    assert payload["metrics"]["episode_outcome_successes"] == 1
    assert payload["metrics"]["episode_outcome_resolved"] == 1


def test_episode_without_exact_outcome_is_not_resolved() -> None:
    payload = case_payload(_review_with_episode_and_no_matching_outcome())
    assert payload["metrics"]["opportunity_episodes"] == 1
    assert payload["metrics"]["episode_outcome_resolved"] == 0
```

Implement the two named test fixtures using literal `CaseReview`, `OpportunityEpisode`, and `CaseOutcome` values in the same test file; do not calculate expected metrics with report helpers.

- [ ] **Step 6: Update Markdown and verify safety wording**

Render separate sections named `原始信号（可能重复）`, `去重交易机会`, and `1.5R—2R 条件影子组`. Assert the document still contains `CASE_ANALYSIS_ONLY`, `NO-TRADE`, and the statement that the report cannot promote rules or authorize trading.

```python
markdown = render_case_markdown(review)
assert "## 原始信号（可能重复）" in markdown
assert "## 去重交易机会" in markdown
assert "## 1.5R—2R 条件影子组" in markdown
assert "CASE_ANALYSIS_ONLY" in markdown
assert "NO-TRADE" in markdown
assert "不能用于规则晋级或交易" in markdown
```

- [ ] **Step 7: Run all report and case tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_case_report.py \
  tests/unit/test_buy_point_case_review.py \
  tests/unit/test_review_buy_point_case_cli.py
```

Expected: all tests pass and deterministic-order tests remain green.

- [ ] **Step 8: Commit the v2 report**

```bash
git add stock_ai/buy_point_selection/case_report.py tests/unit/test_buy_point_case_report.py
git commit -m "feat(stock-ai): report deduplicated shadow outcomes"
```

---

### Task 5: Verify the full research boundary and regenerate the LAN case

**Files:**
- Verify only: `stock-ai/stock_ai/buy_point_selection/`
- Verify only: `stock-ai/scripts/analysis/review_buy_point_case.py`
- Runtime output, ignored: `stock-ai/output/research/buy_point_cases/`

**Interfaces:**
- Consumes: the completed v2 implementation and MySQL at `192.168.1.13:3306` through an in-memory URL host override.
- Produces: test evidence and one immutable v2 JSON/Markdown case revision; no tracked runtime artifact.

- [ ] **Step 1: Run the broader buy-point regression suite**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
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

Expected: all tests pass with no warnings.

- [ ] **Step 2: Run syntax and diff checks**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m compileall -q \
  scripts/analysis/review_buy_point_case.py \
  stock_ai/buy_point_selection/case_review.py \
  stock_ai/buy_point_selection/case_report.py
git diff --check
```

Expected: both commands exit zero without output.

- [ ] **Step 3: Regenerate the case through the LAN database and index fallback**

Run without printing or persisting credentials:

```bash
.venv/bin/python - <<'PY'
import os
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv('.env')
url = make_url(os.environ['MYSQL_URL']).set(host='192.168.1.13', port=3306)
os.environ['MYSQL_URL'] = url.render_as_string(hide_password=False)

from scripts.analysis.review_buy_point_case import main

raise SystemExit(main([
    '--signal-start', '2026-08-03',
    '--signal-end', '2026-08-07',
    '--outcome-cutoff', '2026-08-14',
    '--output-dir', 'output/research/buy_point_cases',
]))
PY
```

Expected: exit zero and two new paths whose report payload schema is `buy-point-case-review-v2`. The existing v1 revision remains unchanged.

- [ ] **Step 4: Audit the v2 artifact with compact queries**

Use `jq` to verify schema, identity, incomplete dates, raw candidate count, episode count, conditional cohort count, raw and episode success numerators/denominators, and zero executable shares for every conditional row. Confirm the repeated TCL Technology signals appear in one episode when their plan-validity windows overlap.

- [ ] **Step 5: Confirm tracked files and commit any verification-only correction**

Run `git status --short` and verify no generated case artifact is staged. If Steps 1-4 require a code correction, repeat its failing test first, make the minimal fix, rerun the full suite, and commit only the scoped source and test files with:

```bash
git commit -m "fix(stock-ai): correct episode review integration"
```

If no correction is needed, do not create an empty commit.
