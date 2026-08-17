# Five-Day Ranking V3 Exact Attribution Audit Totals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the V3 train-attribution artifact to V2 so every displayed mean is derived from exact aggregate-only audit totals and every status hierarchy is validated without rounded-mean weighting.

**Architecture:** The pure attribution domain owns exact finite-Decimal accumulation and canonical 28-digit division. `AttributionMetrics` carries an immutable `AttributionAuditTotals`; the strict report serializes those totals, independently derives every auditable display field from them, and validates status children by exact additive totals. The manual CLI remains unchanged and runs only after domain, report, and full regression verification.

**Tech Stack:** Python 3.11, `Decimal`, immutable dataclasses, pytest, Ruff, canonical JSON, SQLAlchemy read-only MySQL loader, existing BaoStock/Eastmoney benchmark loader.

## Global Constraints

- Use schema `five-day-ranking-v3-train-attribution-v2` and attribution version `dual-benchmark-exact-aggregate-v2`.
- Keep the diagnostic train-only and `NO-TRADE`.
- Do not change row-level returns, ranking, qualification, promotion, validation, execution, or any V1/V2/V3 parent artifact.
- Do not introduce tolerance, ULP allowance, or global Decimal quantization.
- Persist aggregate audit totals only; never persist observation rows, stock codes, dates, positions, credentials, or raw provider responses.
- Do not read validation or test outcomes or invoke freeze, forward, settlement, notification, holding, memory, order, or trading flows.
- Reject attribution V1 artifacts under the V2 strict loader; do not silently upgrade them.
- Preserve unrelated dirty-worktree changes and never stage generated attribution artifacts.

---

### Task 1: Add Exact Audit Totals to the Pure Attribution Domain

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py:20-110`
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py:285-455`
- Test: `tests/unit/test_five_day_ranking_v3_attribution.py:1-600`

**Interfaces:**
- Produces: `AttributionAuditTotals`, `exact_decimal_sum(values: Sequence[Decimal]) -> Decimal`, and `canonical_decimal_mean(total: Decimal, count: int) -> Decimal`.
- Produces: `AttributionMetrics.audit_totals: AttributionAuditTotals`; `summarize_attributed_returns()` derives all means and the positive ratio from those totals.
- Consumed by: the V2 report serializer and validator in Task 2.

- [ ] **Step 1: Add failing exact-accumulation tests**

Import `localcontext`, `AttributionAuditTotals`, `exact_decimal_sum`, and `canonical_decimal_mean`. Add literal tests:

```python
def test_exact_decimal_sum_ignores_ambient_precision() -> None:
    with localcontext() as context:
        context.prec = 6
        value = exact_decimal_sum(
            (
                Decimal("123456789.123456789"),
                Decimal("-123456788.123456788"),
            )
        )

    assert value == Decimal("1.000000001")


def test_canonical_decimal_mean_uses_local_precision_28() -> None:
    with localcontext() as context:
        context.prec = 4
        value = canonical_decimal_mean(Decimal("1"), 3)

    assert value == Decimal("0.3333333333333333333333333333")
```

The production mutation caught is ambient-context addition or division replacing exact accumulation and canonical local division.

- [ ] **Step 2: Run the two named tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py::test_exact_decimal_sum_ignores_ambient_precision \
  tests/unit/test_five_day_ranking_v3_attribution.py::test_canonical_decimal_mean_uses_local_precision_28 -q
```

Expected: collection fails because the three new domain symbols do not exist.

- [ ] **Step 3: Implement exact accumulation and the audit-total type**

Set the two version constants exactly:

```python
ATTRIBUTION_SCHEMA = "five-day-ranking-v3-train-attribution-v2"
ATTRIBUTION_VERSION = "dual-benchmark-exact-aggregate-v2"
```

Add the immutable type:

```python
@dataclass(frozen=True)
class AttributionAuditTotals:
    positive_rows: int
    raw_return_sum: Decimal
    matched_index_return_sum: Decimal
    market_median_return_sum: Decimal
    gross_return_sum: Decimal | None
```

Add exact coefficient-aligned accumulation and canonical division:

```python
def exact_decimal_sum(values: Sequence[Decimal]) -> Decimal:
    finite = tuple(values)
    if any(not value.is_finite() for value in finite):
        raise ValueError("exact decimal values must be finite")
    if not finite:
        return Decimal("0")
    exponent = min(value.as_tuple().exponent for value in finite)
    coefficient_sum = 0
    for value in finite:
        item = value.as_tuple()
        coefficient = int("".join(str(digit) for digit in item.digits) or "0")
        if item.sign:
            coefficient = -coefficient
        coefficient_sum += coefficient * (10 ** (item.exponent - exponent))
    sign = int(coefficient_sum < 0)
    digits = tuple(int(character) for character in str(abs(coefficient_sum)))
    return Decimal((sign, digits, exponent))


def canonical_decimal_mean(total: Decimal, count: int) -> Decimal:
    if not total.is_finite() or count <= 0:
        raise ValueError("canonical decimal mean requires finite total and positive count")
    with localcontext() as context:
        context.prec = 28
        return total / Decimal(count)
```

Add `audit_totals: AttributionAuditTotals` to `AttributionMetrics` immediately after the four row-count fields.

- [ ] **Step 4: Add a failing recurring-decimal audit-total test**

Replace the prior recurring cost-drag assertion with explicit audit facts:

```python
def test_attribution_summary_derives_recurring_means_from_exact_audit_totals() -> None:
    raw_returns = (
        Decimal("0.0135792468135792468135792468"),
        Decimal("-0.0246801357924680135792468013"),
        Decimal("0.0379135792468013579246801357"),
    )
    gross_returns = (
        Decimal("0.0148138147037027036025915924"),
        Decimal("-0.0234455679023445567902344557"),
        Decimal("0.0391481471369248147136924813"),
    )
    value = summarize_attributed_returns(
        tuple(_attributed(str(raw), "0", "0") for raw in raw_returns),
        eligible_rows=3,
        excluded_missing_coverage=0,
        gross_returns=gross_returns,
    )

    assert value.audit_totals == AttributionAuditTotals(
        positive_rows=2,
        raw_return_sum=Decimal("0.0268126902679125911590125812"),
        matched_index_return_sum=Decimal("0"),
        market_median_return_sum=Decimal("0"),
        gross_return_sum=Decimal("0.0305163939382829615260496180"),
    )
    assert value.mean_return == Decimal("0.008937563422637530386337527067")
    assert value.mean_gross_return == Decimal("0.01017213131276098717534987267")
    assert value.mean_after_cost_drag == Decimal("0.0012345678901234567890123456")
```

Also assert empty actual metrics carry zero gross audit totals while empty fixed-five metrics carry `gross_return_sum=None`.

- [ ] **Step 5: Run the recurring test and verify RED**

Run the named recurring test. Expected: it fails because `summarize_attributed_returns()` has not populated `audit_totals` and still averages independently calculated fields.

- [ ] **Step 6: Derive every auditable field from exact totals**

Inside `summarize_attributed_returns()`:

1. Build exact raw, index, market, and optional gross sums with `exact_decimal_sum()`.
2. Build `AttributionAuditTotals` for both empty and non-empty metrics.
3. Derive raw/index/market/gross means with `canonical_decimal_mean()`.
4. Derive mean excess from an exact two-value sum of raw total and the negated benchmark total.
5. Derive mean cost drag from an exact two-value sum of gross total and negated raw total.
6. Derive `positive_ratio` under local precision 28 from `positive_rows / completed_rows` and keep Wilson inputs identical.
7. Preserve row-level medians and verdict truth tables.

Do not use the row-level `index_excess` or `market_median_excess` sequences to compute their means; retain them only for medians.

The central calculation must have this shape:

```python
raw_sum = exact_decimal_sum(raw_returns)
index_sum = exact_decimal_sum(matched_index_returns)
market_sum = exact_decimal_sum(market_median_returns)
gross_sum = (
    exact_decimal_sum(tuple(gross_returns))
    if gross_returns is not None
    else None
)
audit_totals = AttributionAuditTotals(
    positive_rows=positive_count,
    raw_return_sum=raw_sum,
    matched_index_return_sum=index_sum,
    market_median_return_sum=market_sum,
    gross_return_sum=gross_sum,
)
mean_return = canonical_decimal_mean(raw_sum, completed_rows)
mean_index_excess = canonical_decimal_mean(
    exact_decimal_sum((raw_sum, -index_sum)),
    completed_rows,
)
mean_market_median_excess = canonical_decimal_mean(
    exact_decimal_sum((raw_sum, -market_sum)),
    completed_rows,
)
mean_after_cost_drag = (
    canonical_decimal_mean(
        exact_decimal_sum((gross_sum, -raw_sum)),
        completed_rows,
    )
    if gross_sum is not None
    else None
)
```

- [ ] **Step 7: Run the domain suite and commit Task 1**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py -q
ruff check \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
.venv/bin/python -m compileall -q \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git diff --check -- \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git add \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git diff --cached --check
git commit -m "feat(stock-ai): add exact attribution audit totals"
```

Expected: zero domain failures. Report tests are intentionally deferred until their V2 fixtures and loader are upgraded in Task 2.

---

### Task 2: Upgrade Canonical Serialization and Strict Loading to V2

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution_report.py:1-850`
- Modify: `tests/unit/test_five_day_ranking_v3_attribution_report.py:1-500`
- Verify: `tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py`

**Interfaces:**
- Consumes: `AttributionMetrics.audit_totals`, `exact_decimal_sum()`, `canonical_decimal_mean()`, and the existing `_wilson_interval()` from Task 1.
- Produces: V2 canonical JSON with one `audit_totals` object per metric set and a loader that validates exact totals, derived displays, exact status addition, registry, lineage, coverage, and safety flags.

- [ ] **Step 1: Update report fixtures to express V2 audit facts**

Import `AttributionAuditTotals`. Change the empty helper signature to
`_empty_metrics(*, gross: bool) -> AttributionMetrics` and update every call so
actual/status metrics pass `gross=True` and fixed-rank metrics pass
`gross=False`. Update `_one_metrics()` so populated metrics use:

```python
audit_totals=AttributionAuditTotals(
    positive_rows=1,
    raw_return_sum=Decimal("0.04"),
    matched_index_return_sum=Decimal("0"),
    market_median_return_sum=Decimal("0"),
    gross_return_sum=Decimal("0.05") if gross else None,
)
```

The empty helper must construct:

```python
audit_totals=AttributionAuditTotals(
    positive_rows=0,
    raw_return_sum=Decimal("0"),
    matched_index_return_sum=Decimal("0"),
    market_median_return_sum=Decimal("0"),
    gross_return_sum=Decimal("0") if gross else None,
)
```

Update direct `AttributionMetrics(...)` constructors in both attribution test
files without changing their observable test intent.

- [ ] **Step 2: Add failing V2 payload and strict-audit tests**

Add assertions that every serialized metric has exact keys:

```python
assert payload["schema"] == "five-day-ranking-v3-train-attribution-v2"
assert payload["attribution_version"] == "dual-benchmark-exact-aggregate-v2"
assert payload["variants"][0]["actual"]["audit_totals"] == {
    "positive_rows": 1,
    "raw_return_sum": "0.04",
    "matched_index_return_sum": "0",
    "market_median_return_sum": "0",
    "gross_return_sum": "0.05",
}
```

Add three behavioral tamper tests using `_write_tampered()`:

1. Change `actual.mean_return` while leaving its audit total unchanged; strict loading must raise `ValueError`.
2. Change the total actual audit sums and all dependent total display means consistently while leaving `TIME_EXIT_GAIN` unchanged; strict loading must raise `ValueError` because the status hierarchy no longer adds exactly.
3. Change a valid payload's schema/version to the two V1 strings, recompute content identity and filename, and require strict loading to raise `ValueError`.

The production mutations caught are trusting display fields, restoring rounded weighted means, or silently accepting the old schema.

Use these concrete mutations:

```python
def test_loader_rejects_mean_not_derived_from_audit_total(tmp_path: Path) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload["variants"][0]["actual"]["mean_return"] = "0.041"

    with pytest.raises(ValueError):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


def test_loader_rejects_status_audit_total_mismatch(tmp_path: Path) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    actual = payload["variants"][0]["actual"]
    actual["audit_totals"]["raw_return_sum"] = "0.05"
    actual["mean_return"] = "0.05"
    actual["mean_index_excess"] = "0.05"
    actual["mean_market_median_excess"] = "0.05"
    actual["mean_after_cost_drag"] = "0"

    with pytest.raises(ValueError):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


def test_v2_loader_rejects_v1_attribution_schema(tmp_path: Path) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload["schema"] = "five-day-ranking-v3-train-attribution-v1"
    payload["attribution_version"] = "dual-benchmark-train-attribution-v1"

    with pytest.raises(ValueError):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))
```

- [ ] **Step 3: Run the new report tests and verify RED**

Run the named V2 payload and three tamper tests. Expected: failures because `audit_totals` is not serialized or validated and the current loader still implements V1 rounded-mean identities.

- [ ] **Step 4: Serialize exact audit totals**

Add `audit_totals` to `_METRIC_KEYS` and `_metrics_content()` with exactly:

```python
"audit_totals": {
    "positive_rows": value.audit_totals.positive_rows,
    "raw_return_sum": _decimal_content(value.audit_totals.raw_return_sum),
    "matched_index_return_sum": _decimal_content(
        value.audit_totals.matched_index_return_sum
    ),
    "market_median_return_sum": _decimal_content(
        value.audit_totals.market_median_return_sum
    ),
    "gross_return_sum": _decimal_content(value.audit_totals.gross_return_sum),
},
```

Keep the forbidden-key recursion and canonical JSON identity logic unchanged.

- [ ] **Step 5: Replace rounded-mean validation with audit-total derivation**

Implement one parser for the exact `audit_totals` keys. In `_metric_values()`:

1. Require `0 <= positive_rows <= completed_rows`.
2. Require all three common sums to be finite decimals.
3. Require gross sum to be finite for actual metrics and `null` for fixed-five metrics.
4. For zero completed rows, require zero applicable sums and null display means/interval.
5. For non-empty metrics, recompute raw/index/market/gross means, both excess means, cost drag, positive ratio, Wilson interval, and verdict from audit facts; require exact equality with serialized displays.
6. Keep medians finite but do not fabricate row reconstruction.

Replace `_weighted_matches()` and its callers. `_status_aggregates_are_valid()` must require exact equality of the four row counts, `positive_rows`, the three common sums, and gross sum between the total and `exact_decimal_sum()` of the four status children.

- [ ] **Step 6: Verify recurring strict round trip and all report protections**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution_report.py \
  tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py -q
ruff check \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution_report.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
.venv/bin/python -m compileall -q \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution_report.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
```

Expected: zero failures, including the recurring-decimal round trip already present in the report test file.

- [ ] **Step 7: Commit only the V2 report contract**

```bash
git diff --check -- \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution_report.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
git add \
  stock_ai/buy_point_selection/five_day_ranking_v3_attribution_report.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
git diff --cached --check
git commit -m "feat(stock-ai): enforce exact attribution audit totals"
```

---

### Task 3: Run Complete Regressions, Real Attribution, and Stop

**Files:**
- Verify: the 20 relevant unit-test files listed below.
- Read: `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
- Read: `output/research/buy_point_five_day_returns/ranking-train-d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3.json`
- Read: `output/research/buy_point_five_day_returns/ranking-v2-train-99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22.json`
- Read: `output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json`
- Generate but never stage: `output/research/buy_point_five_day_returns/ranking-v3-train-attribution-<identity>.json`

**Interfaces:**
- Consumes: Tasks 1-2, immutable canonical parent artifacts, configured read-only `MYSQL_URL`, and existing benchmark providers.
- Produces: one V2 aggregate-only attribution artifact, a strict-load and idempotency proof, unchanged parent identities, and a descriptive `NO-TRADE` summary.

- [ ] **Step 1: Run the complete relevant suite**

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

Expected: zero failures before any real data access.

- [ ] **Step 2: Run the manual attribution command once**

```bash
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking_v3_attribution.py \
  diagnose-train-attribution \
  --train-artifact output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

Expected: exactly one V2 attribution path. A sanitized technical failure starts a new evidence-gathering cycle without printing credentials or raw provider exceptions. `MARKET_DATA_INCOMPLETE` remains a valid bounded result.

- [ ] **Step 3: Strict-load and summarize aggregate evidence only**

Call `load_five_day_ranking_v3_attribution()` with expected parent identities. Report schema/version, status, coverage, actual and fixed-five dual-benchmark aggregates, Rank-1 paired diagnostics, cost drag, and frozen safety flags. Do not print exact audit sums unless needed to explain an integrity failure, and never print rows, codes, credentials, or forbidden keys.

- [ ] **Step 4: Prove deterministic idempotency**

Hash the generated file with SHA-256, rerun the identical command, and require the same path and identical file hash.

- [ ] **Step 5: Prove immutable parents and operational isolation**

Strict-load the parent research artifact and all train generations again. Require:

```text
Research 2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59
V1 d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3
V2 99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22
V3 6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb
```

Require no generated validation, test, freeze, forward, settlement, notification, holding, memory, order, or trading file. Require the Git staging area to be empty.

- [ ] **Step 6: Report and stop without committing generated data**

State that the result is train-only and `NO-TRADE`. Do not alter V3 from this attribution case and do not start the public-strategy challenger suite inside this plan.
