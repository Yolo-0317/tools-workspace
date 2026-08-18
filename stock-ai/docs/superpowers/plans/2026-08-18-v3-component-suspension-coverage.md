# V3 Component Suspension Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow V3 component attribution to exclude naturally suspended stock endpoints consistently while preserving fail-closed benchmark coverage and deterministic frozen evidence.

**Architecture:** Keep the artifact schema and ranking formulas unchanged. Split `attribute_interval` failures at the builder boundary: a missing stock series or endpoint becomes an explicitly counted, population-consistent exclusion; `MarketCoverageIncomplete` from the index or market-median benchmark remains an artifact-level failure; every other malformed value remains a score-reconstruction failure.

**Tech Stack:** Python 3.11, pytest, dataclasses, Decimal arithmetic, canonical JSON/SHA-256 artifacts, SQLAlchemy/PyMySQL read-only market loading.

## Global Constraints

- Do not forward-fill, interpolate, or synthesize a suspended stock price.
- Do not change V3 policy weights, score formulas, artifact schema, or component-attribution version.
- The four experiments in each policy-and-fold unit must share one post-exclusion population fingerprint.
- Keep `train_only=true`, `validation_outcomes_read=false`, `test_outcomes_read=false`, `promotion_eligible=false`, and `trade_permission=NO-TRADE`.
- Index endpoint loss or fewer than 1,000 market members at both interval endpoints remains `MARKET_DATA_INCOMPLETE`.
- Invalid plans, scores, ranks, or finite-positive price values must not be reclassified as a suspension exclusion.
- Generated research artifacts remain Git-ignored and must never be staged.
- Do not touch or stage unrelated working-tree changes, especially `reference_cninfo.py`, `test_buy_point_reference_cninfo.py`, WeChat assets, or personal memory/configuration.

---

### Task 1: Separate Stock Suspension Exclusions from Benchmark Failure

**Files:**
- Modify: `tests/unit/test_five_day_ranking_v3_component_attribution.py:15-35,327-351`
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py:17-29,1060-1153`

**Interfaces:**
- Consumes: `MarketClosePanel.stock_closes`, `MarketCoverageIncomplete`, `attribute_interval(code: str, start: date, end: date, panel: MarketClosePanel) -> AttributedReturn`.
- Produces: unchanged `build_five_day_ranking_v3_component_attribution_review(...) -> FiveDayRankingV3ComponentAttributionReview`; missing stock endpoints are represented by `CoverageComparison.excluded_missing_coverage`.

- [ ] **Step 1: Write the failing suspension test and benchmark regression test**

Import the module boundary and typed benchmark exception:

```python
from stock_ai.buy_point_selection import (
    five_day_ranking_v3_component_attribution as component_module,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (
    AttributedReturn,
    MarketClosePanel,
    MarketCoverageIncomplete,
    build_five_day_ranking_v3_attribution_review,
)
```

Replace `test_full_builder_fails_closed_on_missing_stock_coverage` with
`test_full_builder_excludes_missing_stock_endpoint_consistently`. Reuse its setup
that empties `stock_closes["600000"]`, keep the assertion that the parent is
`COMPLETE`, and assert:

```python
assert review.status == "COMPLETE"
assert len(review.fold_experiments) == 64
affected = tuple(
    value
    for value in review.fold_experiments
    if value.fold_id == "train-fold-1"
)
assert len(affected) == 32
assert {
    value.coverage.excluded_missing_coverage for value in affected
} == {1}
assert {
    value.coverage.candidate_rows
    - value.coverage.eligible_outcomes
    - value.coverage.excluded_without_train_horizon
    - value.coverage.excluded_missing_coverage
    for value in affected
} == {0}
for policy_id in {value.policy_id for value in affected}:
    policy_rows = tuple(
        value for value in affected if value.policy_id == policy_id
    )
    assert len(policy_rows) == 4
    assert len(
        {value.coverage.population_fingerprint for value in policy_rows}
    ) == 1
```

Add `test_full_builder_still_fails_closed_on_benchmark_coverage`. Build the unchanged
complete parent first, monkeypatch only the component module's imported
`attribute_interval` boundary to raise
`MarketCoverageIncomplete("INDEX_ENDPOINT_MISSING")`:

```python
def test_full_builder_still_fails_closed_on_benchmark_coverage(
    full_builder_fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    train_artifact, research, parent, panel = full_builder_fixture

    def missing_benchmark(*_args, **_kwargs):
        raise MarketCoverageIncomplete("INDEX_ENDPOINT_MISSING")

    monkeypatch.setattr(
        component_module,
        "attribute_interval",
        missing_benchmark,
    )
    review = build_five_day_ranking_v3_component_attribution_review(
        train_artifact,
        research,
        parent,
        parent_research_identity=PARENT_RESEARCH_IDENTITY,
        market_panel=panel,
    )

    assert review.status == "MARKET_DATA_INCOMPLETE"
    assert review.fold_experiments == ()
    assert review.combined_experiments == ()
    assert review.fold_component_correlations == ()
    assert review.combined_component_correlations == ()
    assert review.component_effects == ()
```

The narrow monkeypatch is required because the parent replay must remain byte-identical
before the component-specific benchmark branch is exercised.

- [ ] **Step 2: Run the suspension test and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_component_attribution.py::test_full_builder_excludes_missing_stock_endpoint_consistently \
  -q
```

Expected: FAIL because the current status is `MARKET_DATA_INCOMPLETE`, not
`COMPLETE`. This confirms the test reproduces the real-data bug.

- [ ] **Step 3: Implement the minimal typed failure split**

Import `MarketCoverageIncomplete` beside `MarketClosePanel`. In the scored-row loop,
replace the broad inner `except ValueError` with an explicit stock-endpoint guard and
typed benchmark exception:

```python
series = market_panel.stock_closes.get(identity[1])
if series is None or identity[0] not in series or endpoint not in series:
    missing_coverage += 1
    continue
try:
    attributed = attribute_interval(
        identity[1], identity[0], endpoint, market_panel
    )
except MarketCoverageIncomplete:
    return _empty_review(
        train_artifact,
        parent_attribution,
        parent_research_identity=parent_research_identity,
        status="MARKET_DATA_INCOMPLETE",
    )
endpoints[identity] = endpoint
```

Remove the unit-level `if missing_coverage: return ... MARKET_DATA_INCOMPLETE` block.
Leave other `ValueError` instances to the existing outer failure boundary so an
invalid finite-positive price or malformed score becomes
`SCORE_RECONSTRUCTION_FAILED`, not a suspension exclusion.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_component_attribution.py::test_full_builder_excludes_missing_stock_endpoint_consistently \
  tests/unit/test_five_day_ranking_v3_component_attribution.py::test_full_builder_still_fails_closed_on_benchmark_coverage \
  tests/unit/test_five_day_ranking_v3_component_attribution.py::test_full_builder_fails_closed_on_score_or_rank_drift \
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Run component and report/CLI regression tests**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_ranking_v3_component_attribution.py \
  tests/unit/test_five_day_ranking_v3_component_attribution_report.py \
  tests/unit/test_analyze_five_day_ranking_v3_component_attribution_cli.py \
  -q
```

Expected: all tests PASS with no warnings or errors.

- [ ] **Step 6: Run the complete five-day research regression suite**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_*five_day*.py -q
```

Expected: all tests PASS. Record the exact pass count and duration.

- [ ] **Step 7: Commit only the tested source and test**

```bash
git diff --check -- \
  stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py \
  tests/unit/test_five_day_ranking_v3_component_attribution.py
git add \
  stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py \
  tests/unit/test_five_day_ranking_v3_component_attribution.py
git diff --cached --name-only
git commit -m "修复(stock-ai)：一致排除V3停牌样本"
```

Expected staged paths: exactly the two files listed above.

---

### Task 2: Real Frozen-Data Acceptance and Determinism

**Files:**
- Verify: `output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json`
- Verify: `output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json`
- Verify: `output/research/buy_point_five_day_returns/ranking-v3-train-attribution-2a934981be23e8fad0957c166dc1af4059327220b492599bb195c8abd28bbd7e.json`
- Generate, ignored: `output/research/buy_point_five_day_returns/ranking-v3-component-attribution-<artifact_identity>.json`

**Interfaces:**
- Consumes: the frozen Research, V3 train, and V3 market-attribution parent chain plus bounded read-only stock/index closes.
- Produces: one strict-loadable, aggregate-only component-attribution artifact with deterministic identity and `NO-TRADE` safety flags.

- [ ] **Step 1: Strict-load the frozen parent chain before market access**

Use the existing strict loaders for Research, V3 train, and V3 attribution. Assert the
known identities, matching `parent_input_fingerprint`, parent train/research identities,
and parent attribution status `COMPLETE`.

Expected: one sanitized line, `frozen_chain=VALID status=COMPLETE`.

- [ ] **Step 2: Run the real component-attribution CLI once**

Load the project environment without printing it, then run:

```bash
set -a
source .env
set +a
PYTHONPATH=. .venv/bin/python \
  scripts/analysis/analyze_five_day_ranking_v3_component_attribution.py \
  diagnose-ranking-components \
  --train-artifact output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json \
  --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json \
  --market-attribution-artifact output/research/buy_point_five_day_returns/ranking-v3-train-attribution-2a934981be23e8fad0957c166dc1af4059327220b492599bb195c8abd28bbd7e.json \
  --output-dir output/research/buy_point_five_day_returns
```

Expected: exit 0 and one generated component-attribution path. Do not print `.env`,
the resolved connection URL, credentials, stock identifiers, or dated rows. If the local
LAN address remains unreachable, use the existing reachable `.env` endpoint without
changing frozen inputs or code.

- [ ] **Step 3: Strict-load and inspect aggregate acceptance invariants**

Assert from the generated artifact:

```text
status=COMPLETE
fold_experiments=64
combined_experiments=32
fold_component_correlations=16
combined_component_correlations=8
component_effects=24
baseline fold experiments=16
non-baseline fold experiments=48
train_only=true
validation_outcomes_read=false
test_outcomes_read=false
promotion_eligible=false
trade_permission=NO-TRADE
```

Also assert every fold experiment satisfies:

```text
candidate_rows = eligible_outcomes
               + excluded_without_train_horizon
               + excluded_missing_coverage
```

Require at least one positive `excluded_missing_coverage`, proving the suspension case
was recorded. Check recursively that stock codes, dates, plan keys, observations,
holdings, orders, credentials, and the forbidden Eastmoney AI eight-dimension framework
do not appear.

- [ ] **Step 4: Record the first file SHA-256 and repeat the identical CLI**

Run `shasum -a 256` on the generated file, repeat Step 2 with byte-identical arguments,
then run `shasum -a 256` again.

Expected: identical output path, artifact identity, and file SHA-256.

- [ ] **Step 5: Verify repository safety**

Run:

```bash
git check-ignore -v output/research/buy_point_five_day_returns/ranking-v3-component-attribution-*.json
git status --short -- output/research/buy_point_five_day_returns
git diff --cached --name-only
git status --short -- \
  stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py \
  tests/unit/test_five_day_ranking_v3_component_attribution.py
```

Expected: generated artifact is ignored; output directory and the two implementation
paths are clean; staging is empty. Unrelated pre-existing changes remain untouched.

- [ ] **Step 6: Report only aggregate research conclusions**

Report component labels by policy, fold-level ablation deltas, correlation ranges,
tie/sample counts, explicit suspension exclusions, deterministic hash evidence, and
safety flags. Do not claim profitability, promotion, stock selection readiness, or
trading permission, and do not start a challenger strategy in this task.
