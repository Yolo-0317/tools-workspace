# Significant Resistance Shadow Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a signal-time, research-only comparison of legacy any-high, local-pivot, and repeated-pivot-cluster resistance to the deduplicated buy-point case review.

**Architecture:** A new pure `resistance_research.py` module computes immutable profiles from an opportunity representative and bounded bars. The CLI runtime filters eligible 2R near-miss episodes and attaches profiles to `CaseReview`; the report joins exact representative outcomes and emits an immutable v3 comparison without touching production planning or selection behavior.

**Tech Stack:** Python 3.11, frozen dataclasses, `Decimal`, pytest, existing buy-point case models, JSON/Markdown report renderer.

## Global Constraints

- Production `nearest_resistance_above`, `build_price_plan`, rule version `buy-point-selection-3.1.0`, and every formal threshold remain unchanged.
- Profiles use only the final 60 bars whose dates are on or before the representative signal date.
- Local pivots use exactly two bars on each side.
- Repeated-cluster tolerance is exactly `max(0.5 * ATR14, 0.005 * trigger_price)`.
- Repeated pivots must be at least three trading-session indexes apart.
- Missing significant resistance is a research pass; incomplete data is not a pass.
- Every profiled opportunity remains zero-share and `CASE_ANALYSIS_ONLY / NO-TRADE`.
- No database schema, scheduler, notification, memory, holding, promotion profile, or order mutation is allowed.
- Generated v3 artifacts remain ignored by Git.

---

### Task 1: Implement bounded legacy and local-pivot profiles

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/resistance_research.py`
- Create: `stock-ai/tests/unit/test_buy_point_resistance_research.py`

**Interfaces:**
- Consumes: `OpportunityEpisode`, `BuyPointBar`, `atr14`, and production `nearest_resistance_above`.
- Produces: `ResistanceVariantProfile`, `SignificantResistanceProfile`, and `analyze_significant_resistance(episode, bars)`.

- [ ] **Step 1: Write literal fixtures and the failing legacy/pivot test**

Create a 60-bar fixture with trigger 10, risk distance 1, target 12, a minor legacy high at 10.20, and a valid local pivot at 12.20. Construct a zero-share `NEAR_MISS` representative and one `OpportunityEpisode`.

```python
def test_profile_separates_any_high_from_a_two_sided_local_pivot() -> None:
    profile = analyze_significant_resistance(_episode(), _bars())
    variants = {value.variant: value for value in profile.variants}

    assert profile.complete
    assert variants["LEGACY_ANY_HIGH"].level == Decimal("10.20")
    assert variants["LEGACY_ANY_HIGH"].effective_resistance_r == Decimal("0.20")
    assert not variants["LEGACY_ANY_HIGH"].passes_two_r
    assert variants["LOCAL_PIVOT_HIGH"].level == Decimal("12.20")
    assert variants["LOCAL_PIVOT_HIGH"].effective_resistance_r == Decimal("2.20")
    assert variants["LOCAL_PIVOT_HIGH"].passes_two_r
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_resistance_research.py::test_profile_separates_any_high_from_a_two_sided_local_pivot
```

Expected: collection fails because `resistance_research` does not exist.

- [ ] **Step 3: Add immutable models and bounded-input validation**

Create the module with these public constants and models:

```python
LEGACY_ANY_HIGH = "LEGACY_ANY_HIGH"
LOCAL_PIVOT_HIGH = "LOCAL_PIVOT_HIGH"
REPEATED_PIVOT_CLUSTER = "REPEATED_PIVOT_CLUSTER"
VARIANT_ORDER = (LEGACY_ANY_HIGH, LOCAL_PIVOT_HIGH, REPEATED_PIVOT_CLUSTER)


@dataclass(frozen=True)
class ResistanceVariantProfile:
    variant: str
    level: Decimal | None
    effective_resistance_r: Decimal | None
    passes_two_r: bool
    touch_count: int


@dataclass(frozen=True)
class SignificantResistanceProfile:
    episode_id: str
    code: str
    signal_date: date
    structure_id: str
    setup_type: str
    atr14: Decimal
    tolerance: Decimal
    complete: bool
    variants: tuple[ResistanceVariantProfile, ...]
```

Inside `analyze_significant_resistance`, sort bars by date, discard dates after the representative signal date, retain the last 60, and fail closed when the count is below 60, dates duplicate, the last date is not the signal date, any OHLC value is non-positive/non-finite, or trigger/risk/ATR is invalid.

- [ ] **Step 4: Implement legacy normalization and local-pivot detection**

Call `nearest_resistance_above(trigger, bounded)` for the legacy level and normalize `Infinity` to `None`. For indexes 2 through `len(bounded) - 3`, admit a local pivot only when its high is at least all four neighboring highs and strictly above at least one high on each side. Consider only pivot highs above trigger and select the lowest.

Set legacy touch count to one when a level exists. Set local-pivot touch count to the number of detected pivots exactly equal to the selected local-pivot level.

Use one shared converter:

```python
def _variant(variant: str, level: Decimal | None, candidate: CaseCandidate, touches: int) -> ResistanceVariantProfile:
    if level is None:
        return ResistanceVariantProfile(variant, None, None, True, 0)
    effective_r = (level - candidate.plan.trigger_price) / candidate.plan.risk_distance
    return ResistanceVariantProfile(
        variant,
        level,
        effective_r,
        level >= candidate.plan.target_2r,
        touches,
    )
```

Return a placeholder repeated-cluster variant with `level=None`, `passes_two_r=True`, and zero touches until Task 2.

- [ ] **Step 5: Verify GREEN and add point-in-time leakage tests**

Add a future bar above 20 after the signal date and assert the full profile is unchanged. Add endpoint and one-sided highs and assert neither becomes the local pivot. Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_resistance_research.py
```

Expected: all current resistance-research tests pass.

Also add an equal-double-top fixture where both equal highs satisfy the two-sided dominance rule and assert the selected local-pivot level has `touch_count == 2`.

- [ ] **Step 6: Commit bounded legacy and pivot analysis**

```bash
git add stock_ai/buy_point_selection/resistance_research.py tests/unit/test_buy_point_resistance_research.py
git commit -m "feat(stock-ai): analyze significant pivot resistance"
```

---

### Task 2: Add deterministic repeated-pivot clustering and incomplete behavior

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/resistance_research.py`
- Modify: `stock-ai/tests/unit/test_buy_point_resistance_research.py`

**Interfaces:**
- Consumes: signal-time local pivots, `ATR14`, trigger price, and trading-session indexes.
- Produces: the real `REPEATED_PIVOT_CLUSTER` variant inside `SignificantResistanceProfile`.

- [ ] **Step 1: Write the failing repeated-cluster test**

Build pivots at session indexes 10 and 20 with highs 12.10 and 12.20. Use ATR14 0.20 and trigger 10, making tolerance `max(0.10, 0.05) == 0.10`.

```python
def test_repeated_pivots_inside_tolerance_form_one_resistance_cluster() -> None:
    profile = analyze_significant_resistance(_episode(), _cluster_bars())
    repeated = next(
        value for value in profile.variants
        if value.variant == "REPEATED_PIVOT_CLUSTER"
    )
    assert profile.tolerance == Decimal("0.10")
    assert repeated.level == Decimal("12.15")
    assert repeated.touch_count == 2
    assert repeated.effective_resistance_r == Decimal("2.15")
    assert repeated.passes_two_r
```

- [ ] **Step 2: Run the test and verify RED**

Run the test from Step 1. Expected: failure because repeated level is `None`.

- [ ] **Step 3: Implement deterministic clustering**

Represent pivots internally as `(session_index, trade_date, high)`. Sort by high then date. Enumerate contiguous windows in the price-sorted list; keep windows where maximum high minus minimum high is no greater than tolerance, at least two pivots exist, and every pair of session indexes differs by at least three. Discard any qualifying window that is a strict subset of another qualifying window. Select by `(mean_high, member_dates)` and emit the first.

- [ ] **Step 4: Verify GREEN and write boundary rejection tests**

Add literal fixtures proving:

```python
def test_close_dates_or_wide_prices_do_not_form_a_repeated_cluster() -> None:
    assert _repeated_level(_bars_with_pivots(indexes=(10, 12), highs=("12.10", "12.20"))) is None
    assert _repeated_level(_bars_with_pivots(indexes=(10, 20), highs=("12.10", "12.21"))) is None


def test_lowest_qualifying_cluster_is_selected_deterministically() -> None:
    repeated = _repeated_profile(
        _bars_with_pivots(
            indexes=(10, 20, 30, 40),
            highs=("12.10", "12.20", "13.10", "13.20"),
        )
    )
    assert repeated.level == Decimal("12.15")
```

Test through `analyze_significant_resistance`; `_repeated_level` and `_repeated_profile` are test-file helpers that read the public profile, not production APIs.

- [ ] **Step 5: Write failing incomplete/no-level distinction tests**

Assert 59 bars produce `complete=False` and every variant has `passes_two_r=False`. Assert 60 valid bars with no resistance above trigger produce `complete=True`, null pivot/repeated levels, and research passes for those variants.

Add a parameterized local-pivot boundary test with target 12 and literal levels 11.99, 12.00, and 12.01; expected `passes_two_r` values are false, true, and true.

- [ ] **Step 6: Implement fail-closed incomplete variants and run all tests**

For incomplete input, emit all three variants with null levels, null effective R, `passes_two_r=False`, and zero touches. Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_resistance_research.py tests/unit/test_buy_point_planning.py
```

Expected: all tests pass, proving the production planning tests remain unchanged.

- [ ] **Step 7: Commit repeated clustering**

```bash
git add stock_ai/buy_point_selection/resistance_research.py tests/unit/test_buy_point_resistance_research.py
git commit -m "feat(stock-ai): compare repeated resistance clusters"
```

---

### Task 3: Attach eligible profiles to the case runtime

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_review.py`
- Modify: `stock-ai/scripts/analysis/review_buy_point_case.py`
- Modify: `stock-ai/tests/unit/test_review_buy_point_case_cli.py`

**Interfaces:**
- Consumes: deduplicated episodes, `bars_by_code`, and `analyze_significant_resistance`.
- Produces: `_build_resistance_profiles(episodes, bars_by_code)` and `CaseReview.resistance_profiles`.

- [ ] **Step 1: Write the failing eligibility and bounded-bars test**

Create one 2R near-miss episode, one risk-distance near miss, and one strict episode. Give every code a future bar after its signal date.

```python
def test_runtime_profiles_only_deduplicated_two_r_near_miss_representatives() -> None:
    profiles = _build_resistance_profiles(
        (two_r_episode, risk_episode, strict_episode),
        bars_by_code,
    )
    assert len(profiles) == 1
    assert profiles[0].episode_id == two_r_episode.episode_id
    assert profiles[0].signal_date == two_r_episode.representative.signal_date
```

- [ ] **Step 2: Run the test and verify RED**

Run the focused CLI test. Expected: collection fails because `_build_resistance_profiles` does not exist.

- [ ] **Step 3: Implement the pure runtime adapter**

Filter representatives by tier `NEAR_MISS`, soft reason `INSUFFICIENT_TWO_R_SPACE`, and zero executable shares. Pass each eligible episode and its complete code history to `analyze_significant_resistance`; that function performs date bounding. Sort profiles by signal date, code, and episode ID.

- [ ] **Step 4: Add backward-compatible `CaseReview` storage**

Avoid a circular import by adding this type-only import to `case_review.py`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .resistance_research import SignificantResistanceProfile
```

Add the final default field:

```python
resistance_profiles: tuple["SignificantResistanceProfile", ...] = ()
```

Call `_build_resistance_profiles` after episode construction and pass the result to `CaseReview`. Existing injected fixtures must continue to construct `CaseReview` unchanged.

- [ ] **Step 5: Run runtime, case, and resistance tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_resistance_research.py \
  tests/unit/test_buy_point_case_review.py \
  tests/unit/test_review_buy_point_case_cli.py
```

Expected: all tests pass, including future-data, incomplete-input, and read-only CLI tests.

- [ ] **Step 6: Commit runtime profiles**

```bash
git add stock_ai/buy_point_selection/case_review.py scripts/analysis/review_buy_point_case.py tests/unit/test_review_buy_point_case_cli.py
git commit -m "feat(stock-ai): attach resistance shadow profiles"
```

---

### Task 4: Render immutable v3 profiles and setup-aware comparisons

**Files:**
- Modify: `stock-ai/stock_ai/buy_point_selection/case_report.py`
- Modify: `stock-ai/tests/unit/test_buy_point_case_report.py`

**Interfaces:**
- Consumes: `CaseReview.resistance_profiles`, existing opportunity episodes, and exact raw outcomes keyed by code, signal date, tier, and structure ID.
- Produces: schema `buy-point-case-review-v3`, `resistance_profiles`, `resistance_comparison`, completeness metrics, and Markdown section `显著阻力影子对照`.

- [ ] **Step 1: Write the failing v3 identity and profile-payload test**

Construct a review with one complete profile and assert:

```python
payload = case_payload(review)
assert payload["schema"] == "buy-point-case-review-v3"
assert case_identity(review, schema="buy-point-case-review-v2") != case_identity(
    review,
    schema="buy-point-case-review-v3",
)
assert payload["resistance_profiles"][0]["variants"][0] == {
    "variant": "LEGACY_ANY_HIGH",
    "level": "10.20",
    "effective_resistance_r": "0.20",
    "passes_two_r": False,
    "touch_count": 1,
}
```

- [ ] **Step 2: Run report tests and verify RED**

Run the focused test. Expected: failure because schema is v2 and resistance payload is absent.

- [ ] **Step 3: Advance schema and serialize deterministic profiles**

Set `CASE_REPORT_SCHEMA = "buy-point-case-review-v3"`. Serialize profiles sorted by signal date, code, and episode ID; serialize variants in `VARIANT_ORDER`. Preserve every existing v2 key and meaning.

- [ ] **Step 4: Write the failing setup-aware comparison test**

Create three profiles and matching outcomes: two `FIRST_LAUNCH_PULLBACK` representatives passing pivot resistance with one triggered success, and one `TREND_PULLBACK` representative passing pivot resistance with one triggered stop. Assert the pivot comparison rows have hand-derived pass, trigger, success, stop, and mean-net values for each setup type.

```python
assert comparison[("FIRST_LAUNCH_PULLBACK", "LOCAL_PIVOT_HIGH")] == {
    "complete_profiles": 2,
    "variant_passes": 2,
    "triggered": 1,
    "resolved": 2,
    "successes": 1,
    "stop_first": 0,
    "mean_net_return": "0.06",
    "mean_mfe": "0.09",
    "mean_mae": "0.02",
    "codes": ["600001", "600002"],
    "episode_ids": ["episode-1", "episode-2"],
}
```

- [ ] **Step 5: Implement exact representative-outcome joins and comparisons**

Reuse the report's existing exact outcome key `(code, signal_date, tier, structure_id)`. For each setup type and variant, count complete profiles, then restrict trigger/outcome metrics to profiles whose variant passes. Missing outcomes remain outside resolved denominators. Mean only non-null net/MFE/MAE values. Sort comparison rows by setup type then `VARIANT_ORDER`.

- [ ] **Step 6: Add Markdown safety assertions and render the comparison**

Add a report section containing profile completeness and one compact line per setup/variant. Assert the Markdown includes:

```python
assert "## 显著阻力影子对照" in markdown
assert "假设通过仅用于研究，不能生成正式计划" in markdown
assert "CASE_ANALYSIS_ONLY" in markdown
assert "NO-TRADE" in markdown
```

- [ ] **Step 7: Run all case and resistance report tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_resistance_research.py \
  tests/unit/test_buy_point_case_report.py \
  tests/unit/test_buy_point_case_review.py \
  tests/unit/test_review_buy_point_case_cli.py
```

Expected: all tests pass and existing v2 fields remain asserted.

- [ ] **Step 8: Commit v3 reporting**

```bash
git add stock_ai/buy_point_selection/case_report.py tests/unit/test_buy_point_case_report.py
git commit -m "feat(stock-ai): report resistance shadow comparisons"
```

---

### Task 5: Verify production isolation and regenerate the LAN case

**Files:**
- Verify only: `stock-ai/stock_ai/buy_point_selection/`
- Verify only: `stock-ai/scripts/analysis/review_buy_point_case.py`
- Runtime output, ignored: `stock-ai/output/research/buy_point_cases/`

**Interfaces:**
- Consumes: completed v3 code and MySQL at `192.168.1.13:3306` through an in-memory URL host override.
- Produces: test evidence and one immutable v3 JSON/Markdown case revision; no tracked runtime artifact.

- [ ] **Step 1: Run the broader buy-point regression suite**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
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

Expected: every listed test passes without warnings.

- [ ] **Step 2: Verify production planning behavior remains byte-for-behavior compatible**

Run `tests/unit/test_buy_point_planning.py` independently and inspect `git diff` to confirm `planning.py` has no tracked modification. Run syntax compilation and `git diff --check` for all touched source files.

- [ ] **Step 3: Regenerate the August case through the LAN database**

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

Expected: exit zero and two new paths whose payload schema is `buy-point-case-review-v3`; existing v1 and v2 revisions remain unchanged.

- [ ] **Step 4: Audit compact v3 results**

Use `jq` to verify status, trade permission, incomplete dates, profile completeness, all three variants per profile, setup-aware comparison rows, and preservation of the 21 raw candidates and 16 deduplicated opportunities. Confirm every profiled candidate has zero executable shares and that TCL Technology remains one opportunity.

- [ ] **Step 5: Final tracked-file audit**

Run `git status --short` with the exact touched source and test paths. Generated reports must not be staged. If integration exposes a defect, write a failing test first, apply the smallest correction, rerun the full suite, and commit only scoped files with:

```bash
git commit -m "fix(stock-ai): correct resistance shadow integration"
```

If no correction is required, do not create an empty commit.
