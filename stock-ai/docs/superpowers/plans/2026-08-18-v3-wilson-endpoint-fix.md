# Five-Day Ranking V3 Wilson Endpoint Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Wilson intervals use exact theoretical endpoints for zero-success and all-success samples so strict V2 attribution accepts valid extreme-ratio status metrics.

**Architecture:** Keep the existing Wilson formula, confidence level, float-square-root approximation, report containment rule, and all non-extreme outputs unchanged. Clamp only the formula result's lower endpoint to exact zero when `successes == 0` and upper endpoint to exact one when `successes == total`; verify through both the pure summary and strict artifact round-trip boundaries.

**Tech Stack:** Python 3.11, `Decimal`, pytest, Ruff, immutable V2 canonical JSON, existing read-only MySQL attribution CLI.

## Global Constraints

- Keep schema `five-day-ranking-v3-train-attribution-v2` and attribution version `dual-benchmark-exact-aggregate-v2` unchanged.
- Keep the Wilson confidence level and all non-extreme interval values unchanged.
- Do not add tolerance, ULP allowance, global quantization, or remove the strict interval-containment check.
- Do not change audit totals, row-level returns, rankings, verdict thresholds, parent artifacts, or trading permissions.
- Keep the diagnostic train-only and `NO-TRADE`.
- Preserve unrelated dirty-worktree changes and never stage generated attribution artifacts.

---

### Task 1: Correct Wilson Extreme Endpoints Through TDD

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py:335-365`
- Test: `tests/unit/test_five_day_ranking_v3_attribution.py:500-540`
- Test: `tests/unit/test_five_day_ranking_v3_attribution_report.py:300-380`

**Interfaces:**
- Consumes: `_wilson_interval(successes: int, total: int) -> tuple[Decimal, Decimal]` through `summarize_attributed_returns()` and the unchanged V2 strict report validator.
- Produces: exact lower bound `Decimal("0")` for `0/N`, exact upper bound `Decimal("1")` for `N/N`, and byte-identical non-extreme formula outputs.

- [ ] **Step 1: Add failing pure endpoint tests**

Add this parameterized public-summary test:

```python
@pytest.mark.parametrize(
    ("raw_returns", "expected_ratio", "endpoint", "expected_endpoint"),
    (
        (("-0.03", "-0.02"), Decimal("0"), 0, Decimal("0")),
        (
            ("0.01", "0.02", "0.03"),
            Decimal("1"),
            1,
            Decimal("1"),
        ),
    ),
)
def test_wilson_extreme_endpoint_is_exact_under_low_ambient_precision(
    raw_returns: tuple[str, ...],
    expected_ratio: Decimal,
    endpoint: int,
    expected_endpoint: Decimal,
) -> None:
    with localcontext() as context:
        context.prec = 4
        value = summarize_attributed_returns(
            tuple(_attributed(raw, "0", "0") for raw in raw_returns),
            eligible_rows=len(raw_returns),
            excluded_missing_coverage=0,
        )

    assert value.positive_ratio == expected_ratio
    assert value.positive_wilson_interval is not None
    assert value.positive_wilson_interval[endpoint] == expected_endpoint
    assert value.positive_wilson_interval[0] <= expected_ratio
    assert value.positive_wilson_interval[1] >= expected_ratio
```

The existing `2/3` aggregate test must retain the literal interval
`(0.2076596008020477361408035871, 0.9385080552796037749310168249)` and serves as the non-extreme no-change regression.

- [ ] **Step 2: Add a failing strict round-trip regression for a non-empty zero-positive status**

Construct one completed negative actual trade aggregate with the real domain summarizer and replace every review variant's actual/status metrics while retaining one fixed-five result:

```python
def test_zero_positive_actual_status_survives_strict_round_trip(
    tmp_path: Path,
) -> None:
    row = AttributedReturn(
        raw_return=Decimal("-0.04"),
        matched_index_return=Decimal("0"),
        market_median_return=Decimal("0"),
        index_excess=Decimal("-0.04"),
        market_median_excess=Decimal("-0.04"),
        market_members=1000,
    )
    metrics = summarize_attributed_returns(
        (row,),
        eligible_rows=1,
        excluded_missing_coverage=0,
        gross_returns=(Decimal("-0.03"),),
    )
    base = _review()
    empty = _empty_metrics(gross=True)
    variants = tuple(
        replace(
            variant,
            actual=metrics,
            actual_by_status={
                "STOPPED": metrics,
                "TIME_EXIT_GAIN": empty,
                "TIME_EXIT_FLAT": empty,
                "TIME_EXIT_LOSS": empty,
            },
        )
        for variant in base.variants
    )
    review = replace(base, variants=variants)

    path = write_five_day_ranking_v3_attribution(review, tmp_path)
    artifact = load_five_day_ranking_v3_attribution(path)

    assert artifact.status == "COMPLETE"
    assert artifact.payload["variants"][0]["actual"]["positive_ratio"] == "0"
    assert artifact.payload["variants"][0]["actual"][
        "positive_wilson_interval"
    ][0] == "0"
```

This reproduces the real failure without MySQL and catches deletion of either endpoint correction or the strict containment rule.

- [ ] **Step 3: Run the three endpoint cases and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py::test_wilson_extreme_endpoint_is_exact_under_low_ambient_precision \
  tests/unit/test_five_day_ranking_v3_attribution_report.py::test_zero_positive_actual_status_survives_strict_round_trip -q
```

Expected: the `0/N` or `N/N` assertion fails by a tiny final-digit boundary and the strict writer rejects the non-empty zero-positive metric because its interval does not contain ratio zero.

- [ ] **Step 4: Implement the minimal endpoint correction**

Inside `_wilson_interval()`, retain the existing formula and replace only the final return construction:

```python
lower = max(Decimal("0"), (centre - margin) / denominator)
upper = min(Decimal("1"), (centre + margin) / denominator)
if successes == 0:
    lower = Decimal("0")
if successes == total:
    upper = Decimal("1")
return lower, upper
```

Do not change `math.sqrt`, `_WILSON_Z`, precision 28, or the report validator.

- [ ] **Step 5: Run endpoint, attribution, and static verification**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py \
  tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py -q
ruff check \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
.venv/bin/python -m compileall -q \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
git diff --check -- \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
```

Expected: zero failures and the existing non-extreme literal remains unchanged.

- [ ] **Step 6: Commit only the endpoint fix and tests**

```bash
git add \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
git diff --cached --check
git commit -m "fix(stock-ai): clamp Wilson extreme endpoints"
```

---

### Task 2: Re-run Complete Regressions and Real V2 Attribution

**Files:**
- Verify: the 20 relevant unit-test files listed in Step 1.
- Read: the immutable research/V1/V2/V3 artifacts with identities recorded below.
- Generate but never stage: `output/research/buy_point_five_day_returns/ranking-v3-train-attribution-<identity>.json`.

**Interfaces:**
- Consumes: Task 1, canonical parent artifacts, configured read-only `MYSQL_URL`, and existing benchmark providers.
- Produces: one strict V2 aggregate-only artifact, deterministic rerun evidence, unchanged parents, and a `NO-TRADE` descriptive summary.

- [ ] **Step 1: Run the complete 20-file suite**

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
  tests/unit/test_five_day_ranking_v3_evidence.py \
  tests/unit/test_five_day_ranking_v3_features.py \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3_report.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py \
  tests/unit/test_analyze_five_day_ranking_cli.py \
  tests/unit/test_analyze_five_day_ranking_v2_cli.py \
  tests/unit/test_analyze_five_day_ranking_v3_cli.py \
  tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py \
  tests/unit/test_research_five_day_return_shadow_cli.py -q
```

Expected: zero failures before real data access.

- [ ] **Step 2: Run the manual V2 attribution command**

```bash
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking_v3_attribution.py \
  diagnose-train-attribution \
  --train-artifact output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

Expected: exactly one V2 attribution path; any failure remains sanitized.

- [ ] **Step 3: Strict-load, summarize, and prove idempotency**

Strict-load with both expected parent identities, report aggregate-only coverage and attribution evidence, hash the file, rerun the identical command, and require identical path and SHA-256 hash.

- [ ] **Step 4: Verify immutable parents and operational isolation**

Require the identities:

```text
Research 2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59
V1 d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3
V2 99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22
V3 6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb
```

Require no generated validation, test, freeze, forward, settlement, notification, holding, memory, order, or trading file and an empty Git staging area.

- [ ] **Step 5: Report and stop**

State that the artifact is train-only and `NO-TRADE`. Do not alter V3 or begin the public-strategy challenger suite.
