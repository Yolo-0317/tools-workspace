# Five-Day Ranking V3 Market and Strategy Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one immutable, aggregate-only, train-only artifact that separates market drag from V3 strategy drag under matched-index and same-universe-median benchmarks and diagnoses same-date Rank-1 inversion.

**Architecture:** Add a pure attribution module, a strict content-addressed report module, and one manual CLI. The CLI strictly verifies the V3 train and parent research lineage before bounded read-only market access, passes in-memory close panels to the pure builder, writes one train-only artifact, and stops.

**Tech Stack:** Python 3.12, frozen dataclasses, `Decimal`, SQLAlchemy read-only queries, existing BaoStock/Eastmoney benchmark loader, canonical JSON, pytest.

## Global Constraints

- Follow `docs/superpowers/specs/2026-08-17-v3-market-strategy-attribution-design.md` exactly.
- Use only the V3 train artifact and its parent research train dates/outcomes.
- Never run or import validation, test, freeze, forward, settlement, advisor, notification, holding, memory, order, or Eastmoney AI 8D flows.
- Do not change V1, V2, V3, their parent research artifact, ranking scores, gates, weights, qualifications, or execution profiles.
- Keep every persisted result aggregate-only; no stock codes, plan keys, observation rows, positions, credentials, or date-keyed observation rows.
- Use `Decimal` under local precision 28; never calculate persisted returns with binary float.
- Require 1,000 valid Shanghai/Shenzhen main-board members for each market-median interval.
- Use matched indexes `sh.000001`, `sz.399001`, and future-only `sh.000688` as frozen in the design.
- Serialize canonical JSON with sorted keys and compact separators; create by content identity or verify identical prior bytes.
- Preserve `train_only=true`, false validation/test/promotion flags, and `trade_permission=NO-TRADE` in every artifact state.
- Use TDD for every production change and commit only task-scoped files.
- Never stage generated research artifacts, `.env`, credentials, holdings, or unrelated dirty-worktree files.

## File Structure

- Create `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py`: pure interval, market panel, aggregate, rank diagnosis, verdict, and full review builder.
- Create `stock_ai/buy_point_selection/five_day_ranking_v3_attribution_report.py`: canonical aggregate-only payload, strict loader, immutable writer.
- Create `scripts/analysis/analyze_five_day_ranking_v3_attribution.py`: manual lineage-safe CLI and bounded read-only market loaders.
- Create `tests/unit/test_five_day_ranking_v3_attribution.py`: pure domain and full-builder behavior.
- Create `tests/unit/test_five_day_ranking_v3_attribution_report.py`: artifact safety, validation, tamper, and idempotency.
- Create `tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py`: parser, lineage ordering, bounded loading, dispatch, and sanitized errors.
- Reuse `tests/unit/five_day_ranking_v3_fixtures.py`; do not add attribution-only methods to production classes.

---

### Task 1: Freeze Benchmark and Interval Primitives

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py`
- Create: `tests/unit/test_five_day_ranking_v3_attribution.py`

**Interfaces:**
- Consumes: normalized A-share codes, ordered train dates, close values.
- Produces: `ATTRIBUTION_SCHEMA`, `ATTRIBUTION_VERSION`, `UNIVERSE_VERSION`, `MIN_MARKET_MEDIAN_MEMBERS`, `AttributionInterval`, `MarketClosePanel`, `AttributedReturn`, `matched_index_id()`, `fifth_subsequent_train_date()`, `simple_return()`, `attribute_interval()`.

- [ ] **Step 1: Write failing primitive tests**

Add literal tests that prove the exact frozen boundaries:

```python
def test_v3_attribution_maps_supported_boards_to_indexes() -> None:
    assert matched_index_id("600001") == "sh.000001"
    assert matched_index_id("002001") == "sz.399001"
    assert matched_index_id("688001") == "sh.000688"


def test_v3_attribution_rejects_unsupported_board() -> None:
    with pytest.raises(ValueError, match="unsupported attribution board"):
        matched_index_id("300001")


def test_fixed_five_date_never_crosses_train_boundary() -> None:
    dates = weekday_dates(7)
    assert fifth_subsequent_train_date(dates[0], dates) == dates[5]
    assert fifth_subsequent_train_date(dates[2], dates) is None


def test_interval_attribution_uses_dual_benchmarks_and_decimal() -> None:
    panel = _market_panel(
        stock_start="10", stock_end="11",
        index_start="100", index_end="102",
        median_start="10", median_end="10.50",
        market_members=1000,
    )
    value = attribute_interval("600001", START, END, panel)
    assert value.raw_return == Decimal("0.1")
    assert value.matched_index_return == Decimal("0.02")
    assert value.market_median_return == Decimal("0.05")
    assert value.index_excess == Decimal("0.08")
    assert value.market_median_excess == Decimal("0.05")
```

The `_market_panel` test helper must construct all 1,000 literal-valid member paths without invoking production aggregation logic.

- [ ] **Step 2: Run the primitive tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py -q
```

Expected: collection fails because the attribution module does not exist.

- [ ] **Step 3: Implement the minimal primitive types and functions**

Define these exact public types:

```python
ATTRIBUTION_SCHEMA = "five-day-ranking-v3-train-attribution-v1"
ATTRIBUTION_VERSION = "dual-benchmark-train-attribution-v1"
UNIVERSE_VERSION = "sh-sz-main-board-close-median-v1"
MIN_MARKET_MEDIAN_MEMBERS = 1000

@dataclass(frozen=True, order=True)
class AttributionInterval:
    start: date
    end: date

@dataclass(frozen=True)
class MarketClosePanel:
    train_dates: tuple[date, ...]
    stock_closes: Mapping[str, Mapping[date, Decimal]]
    index_closes: Mapping[str, Mapping[date, Decimal]]

@dataclass(frozen=True)
class AttributedReturn:
    raw_return: Decimal
    matched_index_return: Decimal
    market_median_return: Decimal
    index_excess: Decimal
    market_median_excess: Decimal
    market_members: int
```

`matched_index_id()` must accept only the exact prefixes in the design.
`fifth_subsequent_train_date()` must validate a unique increasing calendar and
return `None` instead of crossing beyond the supplied train dates.
`simple_return()` must reject non-finite or non-positive endpoints.
`attribute_interval()` must calculate the matched index and the cross-sectional
median from stocks with both endpoints. Raise `MarketCoverageIncomplete` with
reason `INDEX_ENDPOINT_MISSING` or `MARKET_MEMBERS_BELOW_1000`; never impute.

- [ ] **Step 4: Run Task 1 tests and existing market-code tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_buy_point_historical_replay_runtime.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git diff --cached --check
git commit -m "feat(stock-ai): add v3 attribution primitives"
```

---

### Task 2: Aggregate Returns and Freeze Cause Labels

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py`
- Modify: `tests/unit/test_five_day_ranking_v3_attribution.py`

**Interfaces:**
- Consumes: sequences of `AttributedReturn`, optional gross-return values aligned one-to-one with completed rows, and eligible/excluded counts.
- Produces: `AttributionMetrics`, `summarize_attributed_returns()`, `attribution_verdict()`.

- [ ] **Step 1: Write failing aggregate and verdict tests**

Add hand-derived cases:

```python
def test_attribution_summary_reports_mean_median_and_excess() -> None:
    rows = (
        _attributed("-0.02", "-0.03", "-0.04"),
        _attributed("0.04", "-0.01", "0.00"),
        _attributed("0.01", "0.00", "0.01"),
    )
    value = summarize_attributed_returns(rows, eligible_rows=4,
                                         excluded_missing_coverage=1)
    assert value.completed_rows == 3
    assert value.mean_return == Decimal("0.01")
    assert value.median_return == Decimal("0.01")
    assert value.positive_ratio == Decimal("2") / Decimal("3")
    assert value.excluded_missing_coverage == 1


@pytest.mark.parametrize(
    ("raw", "index_excess", "median_excess", "expected"),
    (
        ("-0.01", "0.002", "0.001", "MARKET_DRAG"),
        ("-0.01", "0", "-0.001", "STRATEGY_DRAG"),
        ("-0.01", "0.001", "0", "MIXED"),
        ("0.01", "0.001", "0.001", "INCONCLUSIVE"),
    ),
)
def test_attribution_verdict_truth_table(
    raw: str,
    index_excess: str,
    median_excess: str,
    expected: str,
) -> None:
    rows = tuple(
        AttributedReturn(
            raw_return=Decimal(raw),
            matched_index_return=Decimal(raw) - Decimal(index_excess),
            market_median_return=Decimal(raw) - Decimal(median_excess),
            index_excess=Decimal(index_excess),
            market_median_excess=Decimal(median_excess),
            market_members=1000,
        )
        for _ in range(30)
    )
    value = summarize_attributed_returns(
        rows,
        eligible_rows=30,
        excluded_missing_coverage=0,
    )
    assert value.verdict == expected


def test_attribution_verdict_requires_thirty_completed_rows() -> None:
    rows = tuple(
        AttributedReturn(
            raw_return=Decimal("-0.01"),
            matched_index_return=Decimal("-0.012"),
            market_median_return=Decimal("-0.011"),
            index_excess=Decimal("0.002"),
            market_median_excess=Decimal("0.001"),
            market_members=1000,
        )
        for _ in range(29)
    )
    value = summarize_attributed_returns(
        rows,
        eligible_rows=29,
        excluded_missing_coverage=0,
    )
    assert value.verdict == "INCONCLUSIVE"
```

The helper `_attributed(raw, matched_index, market_median)` must build an
`AttributedReturn` whose two excess fields are derived from those three input
values. Do not call production aggregation code from the helper.

- [ ] **Step 2: Run the new tests and verify RED**

Run the two named tests. Expected: import failure for the new symbols.

- [ ] **Step 3: Implement exact aggregate semantics**

Add:

```python
@dataclass(frozen=True)
class AttributionMetrics:
    eligible_rows: int
    completed_rows: int
    excluded_rows: int
    excluded_missing_coverage: int
    mean_return: Decimal | None
    median_return: Decimal | None
    positive_ratio: Decimal | None
    positive_wilson_interval: tuple[Decimal, Decimal] | None
    mean_matched_index_return: Decimal | None
    median_matched_index_return: Decimal | None
    mean_market_median_return: Decimal | None
    median_market_median_return: Decimal | None
    mean_index_excess: Decimal | None
    median_index_excess: Decimal | None
    mean_market_median_excess: Decimal | None
    median_market_median_excess: Decimal | None
    mean_gross_return: Decimal | None
    mean_after_cost_drag: Decimal | None
    verdict: str
```

Use the existing Wilson implementation semantics from
`five_day_return_validation.py` without importing a private function into the
public API. Empty samples serialize as `None`, never zero. Validate
`eligible_rows == completed_rows + excluded_rows` and
`excluded_missing_coverage <= excluded_rows`. The exact public signature is:

```python
def summarize_attributed_returns(
    rows: Sequence[AttributedReturn],
    *,
    eligible_rows: int,
    excluded_missing_coverage: int,
    gross_returns: Sequence[Decimal] | None = None,
) -> AttributionMetrics:
```

When `gross_returns` is supplied, require its length to equal `len(rows)`, set
`mean_gross_return` to its arithmetic mean, and set `mean_after_cost_drag` to
the arithmetic mean of `gross_return - row.raw_return`. When it is absent,
both fields are `None`.

- [ ] **Step 4: Run all attribution tests**

Expected: all pass with no warnings.

- [ ] **Step 5: Commit Task 2**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git diff --cached --check
git commit -m "feat(stock-ai): classify v3 attribution causes"
```

---

### Task 3: Diagnose Rank-1 on Matched Dates

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py`
- Modify: `tests/unit/test_five_day_ranking_v3_attribution.py`

**Interfaces:**
- Consumes: ephemeral dated ranked outcomes containing ordinal rank and `AttributedReturn`.
- Produces: `RankedAttributedReturn`, `RankPairMetrics`, `RankCorrelationMetrics`, `diagnose_rank_one()`.

- [ ] **Step 1: Write failing same-date and correlation tests**

Use two dates where unconditional averages and paired results disagree to prove
that the function pairs within date. Add a 14-date case that returns
`RANKER_INCONCLUSIVE`, and a 15-date literal case where both paired excess
differences are non-positive and returns `RANKER_INVERTED`.

Add a five-row cross-section with perfect ordering:

```python
def test_rank_correlation_uses_negative_ordinal_rank() -> None:
    rows = tuple(
        _ranked(rank, raw=str(Decimal("0.06") - Decimal(rank) / 100))
        for rank in range(1, 6)
    )
    value = diagnose_rank_one(rows)
    assert value.correlations.completed_dates == 1
    assert value.correlations.mean_raw_correlation == Decimal("1")
```

- [ ] **Step 2: Run named tests and verify RED**

Expected: import failure for `RankedAttributedReturn` and
`diagnose_rank_one`.

- [ ] **Step 3: Implement deterministic pairing and Spearman correlation**

Define:

```python
@dataclass(frozen=True)
class RankedAttributedReturn:
    signal_date: date
    rank: int
    value: AttributedReturn

@dataclass(frozen=True)
class RankPairMetrics:
    paired_dates: int
    mean_raw_difference: Decimal | None
    median_raw_difference: Decimal | None
    mean_index_excess_difference: Decimal | None
    median_index_excess_difference: Decimal | None
    mean_market_excess_difference: Decimal | None
    median_market_excess_difference: Decimal | None
    rank_one_win_ratio: Decimal | None
    verdict: str

@dataclass(frozen=True)
class RankCorrelationMetrics:
    eligible_dates: int
    completed_dates: int
    mean_raw_correlation: Decimal | None
    median_raw_correlation: Decimal | None
    mean_index_excess_correlation: Decimal | None
    median_index_excess_correlation: Decimal | None
    mean_market_excess_correlation: Decimal | None
    median_market_excess_correlation: Decimal | None
```

Rank-1 compares with the within-date median of ranks 2 and 3. Correlation is
Spearman correlation between negative ordinal rank and the return target;
average ranks must be assigned for ties. Require at least five rows on a date.
With at least 15 paired dates, both mean excess differences above zero produce
`RANKER_HEALTHY`, both at or below zero produce `RANKER_INVERTED`, and every
other sign combination produces `RANKER_MIXED`.

- [ ] **Step 4: Run attribution tests**

Expected: all pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git diff --cached --check
git commit -m "feat(stock-ai): diagnose v3 rank inversion"
```

---

### Task 4: Build the Complete Train-Only Attribution Review

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py`
- Modify: `tests/unit/test_five_day_ranking_v3_attribution.py`

**Interfaces:**
- Consumes: `FiveDayRankingV3TrainArtifact`, `FiveDayResearchReview`, verified parent research identity, `MarketClosePanel`.
- Produces: `AttributionVariantReview`, `CoverageSummary`, `FiveDayRankingV3AttributionReview`, `build_five_day_ranking_v3_attribution_review()`.

- [ ] **Step 1: Write failing lineage and fixed-five boundary tests**

Build a strict fixture V3 artifact from existing V3 helpers, then assert:

- a mismatched parent identity fails before market-panel traversal;
- a mismatched parent input fingerprint fails;
- validation/test flags fail;
- only train keys map;
- a ranked signal in the last five train sessions is counted as
  `excluded_without_train_horizon` and never uses a validation date.

- [ ] **Step 2: Write failing actual-holding and variant-registry tests**

Construct one completed admitted observation with literal entry/exit dates and
fees. Require:

```python
assert review.variants[0].actual.completed_rows == 1
assert review.variants[0].actual.mean_gross_return == Decimal("0.05")
assert review.variants[0].actual.mean_after_cost_drag == Decimal("0.01")
assert len(review.variants) == 72
assert review.validation_outcomes_read is False
assert review.test_outcomes_read is False
assert review.trade_permission == "NO-TRADE"
```

Also assert outcome-status aggregates sum exactly to the actual aggregate and
that fixed-five band counts sum to the ranked eligible total.

- [ ] **Step 3: Run the new builder tests and verify RED**

Expected: missing builder types/functions.

- [ ] **Step 4: Implement ephemeral key mapping and review dataclasses**

Use the exact V3 plan key tuple:

```python
(signal_date, normalized_code, structure_id, profile_id)
```

Map keys only in memory. Reject missing, duplicate, or cross-train mappings.
Read each V3 variant from the verified payload registry. Actual attribution
uses `admitted_trade_keys`; fixed-five and rank diagnosis use
`ranked_plan_keys`. Persist no mapped key.

Define variant records with:

```python
@dataclass(frozen=True)
class AttributionVariantReview:
    fold_id: str
    policy_id: str
    selection_mode: str
    actual: AttributionMetrics
    actual_by_status: Mapping[str, AttributionMetrics]
    fixed_five_by_rank_band: Mapping[str, AttributionMetrics]
    rank_pairs: RankPairMetrics
    rank_correlations: RankCorrelationMetrics
    funnel_counts: Mapping[str, int]
```

Define coverage as aggregate-only evidence:

```python
@dataclass(frozen=True)
class CoverageSummary:
    attempted_intervals: int
    completed_intervals: int
    index_endpoint_missing_intervals: int
    market_members_below_threshold_intervals: int
    missing_endpoint_dates: tuple[date, ...]
```

`missing_endpoint_dates` is the sorted unique set of endpoint dates from failed
intervals; it contains no stock code, plan key, or date-keyed observation row.
Require attempted intervals to equal completed plus the two mutually exclusive
failure counts.

The review status is `COMPLETE` only when every attempted interval satisfies
coverage. Otherwise it is `MARKET_DATA_INCOMPLETE`, all nested verdicts are
forced to `INCONCLUSIVE`, and coverage counts identify index versus median
failures.

- [ ] **Step 5: Implement the market-data fingerprint**

Hash the ordered train dates, frozen benchmark/universe definitions, and the
ordered `(security, endpoint_date, close)` and `(index, endpoint_date, close)`
tuples for endpoint dates actually required by actual or fixed-five intervals.
Return only the digest in the review. Include no URL, credential, or source
response.

- [ ] **Step 6: Run domain, V3 report, and parent report tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3.py \
  tests/unit/test_five_day_ranking_v3_report.py \
  tests/unit/test_five_day_return_report.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py \
  tests/unit/test_five_day_ranking_v3_attribution.py
git diff --cached --check
git commit -m "feat(stock-ai): build v3 train attribution"
```

---

### Task 5: Persist a Strict Aggregate-Only Attribution Artifact

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution_report.py`
- Create: `tests/unit/test_five_day_ranking_v3_attribution_report.py`

**Interfaces:**
- Consumes: `FiveDayRankingV3AttributionReview`.
- Produces: `five_day_ranking_v3_attribution_payload()`, `write_five_day_ranking_v3_attribution()`, `FiveDayRankingV3AttributionArtifact`, `load_five_day_ranking_v3_attribution()`.

- [ ] **Step 1: Write failing canonical round-trip and filename tests**

Build a complete aggregate review with literal metrics. Write and strict-load
it. Assert the filename is
`ranking-v3-train-attribution-<artifact_identity>.json`, payload identity is
the canonical content hash, the variant registry has exactly 72 records, and
all safety flags remain frozen.

- [ ] **Step 2: Write failing safety and tamper tests**

Parameterize forbidden nested keys from the design. For each key, inject it
under a nested aggregate and require strict-load rejection. Add separate tests
for:

- edited numeric content with old identity;
- wrong filename;
- unknown policy/mode/fold/rank band;
- `COMPLETE` with missing aggregates;
- `MARKET_DATA_INCOMPLETE` carrying a non-inconclusive verdict;
- completed counts exceeding eligible counts;
- non-finite decimals;
- validation/test/promotion/trade flag changes;
- immutable same-path conflict.

- [ ] **Step 3: Run report tests and verify RED**

Expected: module import failure.

- [ ] **Step 4: Implement canonical serialization and strict loading**

Use explicit content builders for metrics, rank pairs, correlations, coverage,
and variants. Do not use an unrestricted recursive dataclass serializer at the
artifact boundary. Recompute and validate every registry, flag, count, finite
decimal, identity, filename, lineage digest shape, and verdict relationship.

Define:

```python
@dataclass(frozen=True)
class FiveDayRankingV3AttributionArtifact:
    artifact_identity: str
    parent_train_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    market_data_fingerprint: str
    status: str
    payload: Mapping[str, object]
```

The loader accepts optional expected parent train and research identities and
must reject mismatches.

- [ ] **Step 5: Run report and domain tests**

Expected: all pass.

- [ ] **Step 6: Commit Task 5**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_attribution_report.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py
git diff --cached --check
git commit -m "feat(stock-ai): persist v3 attribution evidence"
```

---

### Task 6: Add the Manual Lineage-Safe Attribution CLI

**Files:**
- Create: `scripts/analysis/analyze_five_day_ranking_v3_attribution.py`
- Create: `tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py`

**Interfaces:**
- Consumes: `--train-artifact`, `--research-artifact`, `--output-dir`; configured `MYSQL_URL`; existing `_load_benchmark_index_bars()`.
- Produces: one attribution artifact path or one sanitized failure line.

- [ ] **Step 1: Write failing parser and command-surface tests**

Require exactly one subcommand, `diagnose-train-attribution`, and exactly the
three artifact/output options. Assert there is no validation, test, freeze,
forward, settlement, notification, holding, memory, order, or trade option.

- [ ] **Step 2: Write failing lineage-before-I/O tests**

Load the script as a module. Inject market and benchmark loaders that fail the
test if called. Supply mismatched strict parent/train artifacts and assert
`dispatch_command()` raises before either loader runs.

- [ ] **Step 3: Write failing bounded-loader tests**

Use a fake SQLAlchemy engine that records the statement and parameters. Require
the stock query to select only `ts_code`, `trade_date`, and `close`, use an
inclusive `BETWEEN :start AND :end`, filter through
`is_sh_sz_main_board_code`, and return a `MarketClosePanel` bounded to the
train start/end. Require benchmark loading for exactly the distinct matched
index codes needed by the mapped train plans and for the same date bound. A
Shanghai/Shenzhen fixture therefore loads `sh.000001` and `sz.399001`; a
future STAR-board fixture additionally proves `sh.000688` is requested only
when such a plan is present.

- [ ] **Step 4: Write failing success, incomplete, and sanitized-error tests**

On success, assert one attribution writer call and the returned path. On a
coverage gap, assert the writer receives a `MARKET_DATA_INCOMPLETE` review. On
expected exceptions, assert `main()` returns `2` and stderr is exactly:

```text
五日排名V3市场归因失败
```

Assert stdout contains no URL, code, observation key, SQL row, or exception
message.

- [ ] **Step 5: Run CLI tests and verify RED**

Expected: script module not found.

- [ ] **Step 6: Implement the CLI and read-only loaders**

Dispatch order must be:

1. require and strict-load V3 train;
2. require and strict-load parent research;
3. recompute parent identity and verify identity/fingerprint/split/flags;
4. derive exact train start/end;
5. load only bounded main-board closes;
6. call the existing BaoStock/Eastmoney benchmark loader for the required
   matched indexes and same bound;
7. build the pure review;
8. write one attribution artifact.

Load `.env` without override, replace only `host.docker.internal` with
`127.0.0.1` as existing runtime code does, and never print the resolved URL.
Use `pool_pre_ping=True` and close connections through context managers.

- [ ] **Step 7: Run CLI, report, domain, and loader regression tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py \
  tests/unit/test_five_day_ranking_v3_attribution_report.py \
  tests/unit/test_five_day_ranking_v3_attribution.py \
  tests/unit/test_research_five_day_return_shadow_cli.py \
  tests/unit/test_review_buy_point_case_cli.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit Task 6**

```bash
git add scripts/analysis/analyze_five_day_ranking_v3_attribution.py \
  tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py
git diff --cached --check
git commit -m "feat(stock-ai): expose v3 market attribution"
```

---

### Task 7: Verify Complete Regressions and Safety Boundaries

**Files:**
- Verify only; no planned production changes.

**Interfaces:**
- Consumes: committed Tasks 1-6.
- Produces: fresh evidence that existing V1/V2/V3 and five-day research behavior remains unchanged.

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

Expected: zero failures.

- [ ] **Step 2: Verify static safety boundaries**

Run `git diff --check`, confirm no generated artifact is staged, and inspect
the attribution CLI import graph to confirm it contains no operational modules
listed in Global Constraints. This is a review of the changed files, not a
source-grep test committed to the suite.

- [ ] **Step 3: Fix only failures caused by Tasks 1-6 through a new TDD cycle**

If a failure occurs, reproduce the smallest failing case, add or narrow a
regression test, implement one root-cause fix, rerun the affected file, then
rerun Step 1. Do not change existing frozen V3 behavior to make attribution
tests pass.

- [ ] **Step 4: Commit only if Step 3 required a fix**

Stage only the regression test and root-cause fix. Use a message naming the
specific safety boundary. If Step 1 passes without changes, create no commit.

---

### Task 8: Run One Real Train Attribution and Stop

**Files:**
- Read: `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
- Read: `output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json`
- Generate but never stage: `output/research/buy_point_five_day_returns/ranking-v3-train-attribution-<identity>.json`

**Interfaces:**
- Consumes: immutable canonical train artifacts and configured read-only market sources.
- Produces: one ignored train-only attribution artifact and a descriptive user report.

- [ ] **Step 1: Snapshot identities and output files**

Strict-load V1, V2, V3, and the parent research artifact. Record their exact
identities and list the output directory before running attribution.

- [ ] **Step 2: Run only the manual train attribution command**

```bash
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking_v3_attribution.py \
  diagnose-train-attribution \
  --train-artifact output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --output-dir output/research/buy_point_five_day_returns
```

Expected: exactly one attribution path or one sanitized technical failure. Do
not run validation or any operational command.

- [ ] **Step 3: Strict-load and describe the artifact**

If status is `MARKET_DATA_INCOMPLETE`, report exact aggregate coverage reasons
and stop. If status is `COMPLETE`, report:

- actual-holding dual-benchmark verdicts by mode/fold and best/worst policy;
- fixed-five dual-benchmark verdicts by rank band;
- same-date Rank-1 paired differences and correlation summaries;
- raw versus net and after-cost drag;
- whether evidence supports market drag, strategy drag, mixed, or
  inconclusive attribution.

All descriptions must state train-only and `NO-TRADE`.

- [ ] **Step 4: Prove idempotency and unchanged parents**

Hash the attribution file, rerun the identical command, and require the same
path and file hash. Strict-load V1/V2/V3 again and require identities:

```text
V1 d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3
V2 99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22
V3 6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb
```

Require no attribution validation/test/freeze/forward/settlement/notification/
holding/memory/order file and no staged generated artifact.

- [ ] **Step 5: Report and stop**

Do not modify V3 based on the verdict. Do not begin the public challenger suite
inside this task. Present the attribution evidence and make the public
challenger suite the next separately approved design/implementation sequence.

No commit is required for the ignored real attribution artifact.
