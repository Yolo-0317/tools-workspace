# V3 Ranking Component Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one immutable train-only artifact that attributes V3 ranking behavior to base edge, consistency, structure, and downside components through preregistered same-date ablations.

**Architecture:** Add a pure component-attribution domain module, a strict content-addressed report module, a shared bounded market-data loader, and one manual CLI. Reconstruct V3 scores exactly, deduplicate the three selection-mode copies, evaluate baseline and three single-component ablations on identical fixed-five outcomes, and persist aggregate evidence only.

**Tech Stack:** Python 3.12, frozen dataclasses, `Decimal`, SQLAlchemy read-only queries, canonical JSON, pytest, Ruff.

## Global Constraints

- Follow `docs/superpowers/specs/2026-08-18-v3-ranking-component-attribution-design.md` exactly.
- Do not change V3 scores, weights, gates, execution, qualification, or winner rules.
- Run exactly `BASELINE`, `WITHOUT_CONSISTENCY`, `WITHOUT_STRUCTURE`, and `WITHOUT_DOWNSIDE`; base edge remains in all four.
- Use only fold 1 and fold 2 train outcomes; never read validation or test outcomes.
- Treat `FORMAL`, `TOP_1`, and `TOP_5` scored rows as duplicate views and persist one result per policy and fold.
- Require exact Research, V3, parent-attribution, split, registry, formula, fingerprint, and safety lineage before market access.
- Use the same candidate population, dates, fixed-five outcomes, benchmarks, and exclusions in all four experiments.
- Use finite `Decimal` arithmetic and persist audit totals sufficient to recompute every mean, ratio, delta, and label.
- Never persist stock codes, plan identities, dates, rows, positions, holdings, credentials, or daily results.
- Preserve `train_only=true`, false validation/test/promotion flags, and `trade_permission=NO-TRADE`.
- Do not invoke validation, test, freeze, forward, settlement, advisor, notification, memory, holding, order, trade, or Eastmoney AI eight-dimensional flows.
- Generated artifacts stay ignored; preserve unrelated changes; stage only task files.
- Use TDD and Chinese Git commit messages.

## File Structure

- Create `stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py`: score reconstruction, experiments, metrics, labels, and full review builder.
- Create `stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution_report.py`: canonical payload, strict loader, immutable writer.
- Create `stock_ai/buy_point_selection/five_day_ranking_v3_attribution_market.py`: shared bounded stock/index loaders.
- Create `scripts/analysis/analyze_five_day_ranking_v3_component_attribution.py`: one manual diagnosis command.
- Create four matching unit-test files for the domain, report, market loader, and CLI.
- Modify existing V3 attribution domain/tests only to expose the already-tested Wilson and Spearman helpers.
- Modify existing V3 attribution CLI/tests only to consume the shared market loader without behavior change.

---

### Task 1: Reconstruct Components and Rank Frozen Experiments

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py`
- Create: `tests/unit/test_five_day_ranking_v3_component_attribution.py`

**Interfaces:**
- Consumes: `FiveDayV3Policy` and literal fields from a persisted V3 scored row.
- Produces: `COMPONENT_ATTRIBUTION_SCHEMA`, `COMPONENT_ATTRIBUTION_VERSION`, `COMPONENT_IDS`, `EXPERIMENT_IDS`, `PlanIdentity`, `ScoreComponents`, `ComponentOutcome`, `ExperimentalRankedOutcome`, `ExperimentRanking`, `reconstruct_score_components()`, `experiment_score()`, and `rank_component_experiment()`.

- [ ] **Step 1: Write failing reconstruction tests**

```python
def test_reconstructs_signed_policy_components_exactly() -> None:
    policy = _policy("STRUCTURE-K60")
    value = reconstruct_score_components(
        edge=Decimal("0.004"), consistency=Decimal("0.001"),
        feature_adjustment=Decimal("-0.002"),
        downside=Decimal("0.003"), policy=policy,
        persisted_score=Decimal("0.001"),
    )
    assert value == ScoreComponents(
        edge=Decimal("0.004"), consistency=Decimal("0.0005"),
        structure=Decimal("-0.002"), downside=Decimal("-0.0015"),
    )
    assert value.baseline_score == Decimal("0.001")
```

Also reject non-finite inputs, unregistered policies, and a persisted-score mismatch.

- [ ] **Step 2: Run named tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v3_component_attribution.py -q
```

Expected: collection fails because the module does not exist.

- [ ] **Step 3: Implement exact types and reconstruction**

```python
COMPONENT_ATTRIBUTION_SCHEMA = "five-day-ranking-v3-component-attribution-v1"
COMPONENT_ATTRIBUTION_VERSION = "score-component-ablation-v1"
COMPONENT_IDS = ("EDGE", "CONSISTENCY", "STRUCTURE", "DOWNSIDE")
EXPERIMENT_IDS = (
    "BASELINE", "WITHOUT_CONSISTENCY",
    "WITHOUT_STRUCTURE", "WITHOUT_DOWNSIDE",
)
PlanIdentity = tuple[date, str, str, str]

@dataclass(frozen=True)
class ScoreComponents:
    edge: Decimal
    consistency: Decimal
    structure: Decimal
    downside: Decimal

    @property
    def baseline_score(self) -> Decimal:
        return self.edge + self.consistency + self.structure + self.downside

@dataclass(frozen=True)
class ComponentOutcome:
    signal_date: date
    plan_identity: PlanIdentity
    profile_id: str
    setup_quality: Decimal
    full_edge: Decimal
    recent_edge: Decimal
    raw_downside: Decimal
    official_rank: int
    components: ScoreComponents
    value: AttributedReturn

@dataclass(frozen=True)
class ExperimentalRankedOutcome:
    signal_date: date
    plan_identity: PlanIdentity
    rank: int
    value: AttributedReturn
    components: ScoreComponents

@dataclass(frozen=True)
class ExperimentRanking:
    experiment_id: str
    rows: tuple[ExperimentalRankedOutcome, ...]
    candidate_rows: int
    boundary_ties: int
```

`reconstruct_score_components()` multiplies the three registered weights, negates the downside contribution, verifies every value is finite, and requires exact equality with `persisted_score`.

- [ ] **Step 4: Write failing experiment tests**

Prove all four formulas, exact baseline V3 ordering, identity-only tie-breaking after ablation, duplicate/invalid ranks rejection, and exact-score ties crossing `1/2` or `3/4` counted as boundary ties.

```python
assert experiment_score(COMPONENTS, "WITHOUT_DOWNSIDE") == (
    COMPONENTS.edge + COMPONENTS.consistency + COMPONENTS.structure
)
```

- [ ] **Step 5: Run the experiment tests and verify RED**

Expected: imports fail for `experiment_score()` and `rank_component_experiment()`.

- [ ] **Step 6: Implement deterministic ranking**

Baseline uses the exact V3 key:

```python
(-score, -edge, -min(full_edge, recent_edge), raw_downside,
 -setup_quality, normalize_code6(plan_identity[1]), profile_id)
```

Require reproduced ranks to equal official ranks. Ablations sort only by `(-experimental_score, plan_identity)`, so deleted components cannot leak through an economic tie-breaker.

- [ ] **Step 7: Run Task 1 tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v3_component_attribution.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py tests/unit/test_five_day_ranking_v3_component_attribution.py
git diff --cached --check
git commit -m "功能(stock-ai)：重构V3评分组件与消融排序"
```

---

### Task 2: Add Robust Metrics and Cross-Fold Labels

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py`
- Modify: `tests/unit/test_five_day_ranking_v3_attribution.py`
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py`
- Modify: `tests/unit/test_five_day_ranking_v3_component_attribution.py`

**Interfaces:**
- Consumes: `ExperimentRanking`.
- Produces: public `wilson_interval()`, public `spearman_correlation()`, `RankMetricAuditTotals`, `RobustRankMetrics`, `ComponentCorrelationMetrics`, `AblationDelta`, `ComponentEffectReview`, `summarize_experiment_ranking()`, `summarize_component_correlations()`, `compare_ablation()`, and `classify_component_effect()`.

- [ ] **Step 1: Write failing public-helper tests**

```python
assert wilson_interval(0, 2)[0] == Decimal("0")
assert wilson_interval(3, 3)[1] == Decimal("1")
assert spearman_correlation(
    (Decimal("1"), Decimal("2"), Decimal("3")),
    (Decimal("1"), Decimal("2"), Decimal("3")),
) == Decimal("1")
```

- [ ] **Step 2: Promote helpers without changing arithmetic**

Rename `_wilson_interval` and `_spearman_correlation` to their public names and update internal calls. Do not change formulas, endpoint clamps, tie semantics, float square root, or precision. Run all three existing attribution test files before continuing.

- [ ] **Step 3: Write failing robust-metric tests**

Use 30 literal dates to assert raw/index/market paired sums and medians, Rank-1 win count/ratio/Wilson interval, completed correlation dates, and raw/index/market Spearman sums. Prove pairing stays within date, requires Rank 1 plus Rank 2-3, correlations need five rows, constant components are excluded, and exact sums ignore ambient precision.

- [ ] **Step 4: Write failing label truth-table tests**

```python
@pytest.mark.parametrize(("fold1", "fold2", "expected"), (
    (HARMFUL, HARMFUL, "CONSISTENTLY_HARMFUL"),
    (HELPFUL, HELPFUL, "CONSISTENTLY_HELPFUL"),
    (HARMFUL, HELPFUL, "REGIME_UNSTABLE"),
    (MIXED, HARMFUL, "INCONCLUSIVE"),
))
def test_component_effect_label_truth_table(fold1, fold2, expected):
    assert classify_component_effect(fold1, fold2).label == expected
```

Add explicit tests for fewer than 30 paired/correlation dates, boundary ties, equality neutrality, and combined metrics being ignored by the label function.

- [ ] **Step 5: Run the new metric and label tests and verify RED**

Expected: imports fail for the new audit, metric, delta, and label types.

- [ ] **Step 6: Implement exact aggregates and labels**

Persist audit sums and counts; derive means with `canonical_decimal_mean()`, win intervals with `wilson_interval()`, and deltas as `ablation - baseline`. The core delta vector is median raw difference, win ratio, and mean raw Spearman. Benchmark safeguards are mean index- and market-excess differences. Implement the strict two-fold sign rules from the design.

- [ ] **Step 7: Run and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v3_attribution.py tests/unit/test_five_day_ranking_v3_attribution_report.py tests/unit/test_five_day_ranking_v3_component_attribution.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v3_attribution.py stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py tests/unit/test_five_day_ranking_v3_attribution.py tests/unit/test_five_day_ranking_v3_component_attribution.py
git diff --cached --check
git commit -m "功能(stock-ai)：增加V3组件稳健归因指标"
```

---

### Task 3: Build the Deduplicated Train Review

**Files:**
- Modify: `stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py`
- Modify: `tests/unit/test_five_day_ranking_v3_component_attribution.py`

**Interfaces:**
- Consumes: strict `FiveDayRankingV3TrainArtifact`, `FiveDayResearchReview`, strict `FiveDayRankingV3AttributionArtifact`, and `MarketClosePanel`.
- Produces: `FoldExperimentReview`, `PolicyComponentEffect`, `CoverageComparison`, `FiveDayRankingV3ComponentAttributionReview`, and `build_five_day_ranking_v3_component_attribution_review()`.

- [ ] **Step 1: Build an in-memory 35-date-per-fold fixture**

Reuse `five_day_ranking_v3_fixtures.py` and the bounded-panel helper pattern. Include five candidates per date, eight policies, three modes, and strict Research/V3/parent-attribution objects; no database or network.

- [ ] **Step 2: Write failing lineage/deduplication tests**

Prove parent attribution is replayed exactly from the supplied panel; identity, fingerprint, safety, coverage, or scored-mode drift fails; and the complete result has exactly 64 fold experiments (`8 × 2 × 4`), 32 combined experiment summaries (`8 × 4`), 16 fold component-correlation groups, 8 combined correlation groups, and 24 cross-fold component effects.

- [ ] **Step 3: Run lineage/deduplication tests and verify RED**

Expected: imports fail for the full review types and builder.

- [ ] **Step 4: Implement parent validation and mode deduplication**

```python
def build_five_day_ranking_v3_component_attribution_review(
    train_artifact: FiveDayRankingV3TrainArtifact,
    research: FiveDayResearchReview,
    parent_attribution: FiveDayRankingV3AttributionArtifact,
    *, parent_research_identity: str,
    market_panel: MarketClosePanel,
) -> FiveDayRankingV3ComponentAttributionReview:
```

Strictly compare lineage before traversing rows. Rebuild the parent attribution and compare its canonical payload with the loaded parent. Group variants by `(fold_id, policy_id)`, require exactly the three registered modes and byte-equivalent `scored` arrays, then use `FORMAL` as the one in-memory copy.

- [ ] **Step 5: Write failing population tests**

Prove last-five-session rows are counted without crossing train, missing stock/index/market coverage fails closed, score/rank mismatch stops review, all four experiments share one population fingerprint, combined metrics are descriptive only, and component labels use folds only.

- [ ] **Step 6: Run the population tests and verify RED**

Expected: failures for fixed-five mapping, comparability, combined summaries, and status propagation.

- [ ] **Step 7: Implement fixed-five mapping**

Map each plan key to one parent observation, require its signal date in that fold, resolve the fifth subsequent train date, call `attribute_interval()`, reconstruct components, and reuse the resulting `ComponentOutcome` in all four experiments. Persist only counts and a hash of in-memory identities/endpoints/Decimal outcomes. Use the exact artifact statuses `LINEAGE_INVALID`, `SCORE_RECONSTRUCTION_FAILED`, `BASELINE_REPRODUCTION_FAILED`, `MARKET_DATA_INCOMPLETE`, `COMPARABILITY_FAILED`, and `COMPLETE`; a non-complete status omits component labels.

- [ ] **Step 8: Assemble fold, combined, and component-effect reviews**

Build fold reviews first, concatenate the two disjoint fold populations for descriptive combined metrics, and call `classify_component_effect()` only with fold-level deltas.

- [ ] **Step 9: Run and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v3_component_attribution.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py tests/unit/test_five_day_ranking_v3_component_attribution.py
git diff --cached --check
git commit -m "功能(stock-ai)：构建V3组件归因评审"
```

---

### Task 4: Freeze the Strict Artifact

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution_report.py`
- Create: `tests/unit/test_five_day_ranking_v3_component_attribution_report.py`

**Interfaces:**
- Consumes: `FiveDayRankingV3ComponentAttributionReview`.
- Produces: `FiveDayRankingV3ComponentAttributionArtifact`, `five_day_ranking_v3_component_attribution_payload()`, `write_five_day_ranking_v3_component_attribution()`, and `load_five_day_ranking_v3_component_attribution()`.

- [ ] **Step 1: Write failing canonical/idempotent tests**

Require compact sorted JSON, `ranking-v3-component-attribution-<identity>.json`, two identical writes producing identical bytes, and strict load with all three expected parent identities.

- [ ] **Step 2: Run the round-trip test and verify RED**

Expected: import failure because the report module does not exist.

- [ ] **Step 3: Implement payload and exclusive writer**

Hash primitive content without `artifact_identity`; insert the identity; write exclusively or verify byte-identical existing content. Use `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, and one trailing newline.

- [ ] **Step 4: Write failing tamper tests**

Cover wrong filename/identity/parents/split/registries/formula/safety flags; old schema; extra or missing experiments; non-finite/non-string/non-canonical Decimal; count, audit sum, mean, ratio, Wilson, delta, label, population, or status tampering under a recomputed outer identity; immutable-path conflict; and forbidden nested keys.

```python
FORBIDDEN_KEYS = {
    "code", "ts_code", "stock_code", "plan_key", "plan_identity",
    "signal_date", "entry_date", "exit_date", "trade_date", "dates",
    "observation", "observations", "rows", "position", "positions",
    "holding", "holdings", "order", "orders", "credential", "credentials",
}
```

- [ ] **Step 5: Run tamper tests and verify RED**

Expected: failures until the loader recomputes all derived arithmetic and labels.

- [ ] **Step 6: Implement strict loader**

```python
def load_five_day_ranking_v3_component_attribution(
    path: str | Path, *,
    expected_parent_train_identity: str | None = None,
    expected_parent_research_identity: str | None = None,
    expected_parent_attribution_identity: str | None = None,
) -> FiveDayRankingV3ComponentAttributionArtifact:
```

Recompute exact keys, content identity, 64 fold experiments, 32 combined experiment summaries, 64 fold component-correlation blocks, 32 combined component-correlation blocks, 24 effects, audit-derived metrics, ablation deltas, and fold-only labels. Failure artifacts cannot contain helpful/harmful labels.

- [ ] **Step 7: Run and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v3_component_attribution.py tests/unit/test_five_day_ranking_v3_component_attribution_report.py -q
git add stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution_report.py tests/unit/test_five_day_ranking_v3_component_attribution_report.py
git diff --cached --check
git commit -m "功能(stock-ai)：冻结V3组件归因产物"
```

---

### Task 5: Extract the Shared Bounded Market Loader

**Files:**
- Create: `stock_ai/buy_point_selection/five_day_ranking_v3_attribution_market.py`
- Create: `tests/unit/test_five_day_ranking_v3_attribution_market.py`
- Modify: `scripts/analysis/analyze_five_day_ranking_v3_attribution.py`
- Modify: `tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py`

**Interfaces:**
- Produces: `configured_read_only_engine()`, `load_stock_closes()`, `load_mysql_stock_closes()`, `required_index_ids()`, and `load_required_benchmark_closes()`.

- [ ] **Step 1: Write failing shared-loader tests**

Move the literal SQL-boundary, main-board filter, invalid-close filter, benchmark registry/date normalization, and engine-disposal assertions into the new test file. Keep one old-CLI injection test proving its parser and dispatch contract do not change.

- [ ] **Step 2: Run the shared-loader tests and verify RED**

Expected: import failure because the shared module does not exist.

- [ ] **Step 3: Extract loader behavior**

Keep `WHERE trade_date BETWEEN :start AND :end`, finite positive closes, Shanghai/Shenzhen main-board filtering, ordered dictionaries, `pool_pre_ping=True`, and disposal in `finally`. The module is read-only and accepts the existing benchmark callback rather than importing a script.

- [ ] **Step 4: Refactor old CLI without changing behavior**

Import shared functions without changing command name, options, lineage order, injection seams, error message, or output.

- [ ] **Step 5: Run shared-loader and old-CLI tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v3_attribution_market.py tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py -q
```

- [ ] **Step 6: Commit**

```bash
git add stock_ai/buy_point_selection/five_day_ranking_v3_attribution_market.py scripts/analysis/analyze_five_day_ranking_v3_attribution.py tests/unit/test_five_day_ranking_v3_attribution_market.py tests/unit/test_analyze_five_day_ranking_v3_attribution_cli.py
git diff --cached --check
git commit -m "重构(stock-ai)：复用V3归因市场加载器"
```

---

### Task 6: Add the Manual Component CLI

**Files:**
- Create: `scripts/analysis/analyze_five_day_ranking_v3_component_attribution.py`
- Create: `tests/unit/test_analyze_five_day_ranking_v3_component_attribution_cli.py`

**Interfaces:**
- Produces: `build_parser()`, `dispatch_command()`, and `main()` for `diagnose-ranking-components`.

- [ ] **Step 1: Write failing parser tests**

Require exactly `--train-artifact`, `--research-artifact`, `--market-attribution-artifact`, and `--output-dir`; forbid validation/test/freeze/forward/settlement/notification/holding/memory/order/trade options.

- [ ] **Step 2: Run parser tests and verify RED**

Expected: the script does not exist.

- [ ] **Step 3: Implement parser only**

Add exactly one `diagnose-ranking-components` subcommand and the four required path options. Do not load files or market data in this step.

- [ ] **Step 4: Write failing dispatch tests**

Prove bad lineage or incomplete attribution never calls loaders; bounds equal first/last train dates; only required indexes load; writer receives no-trade review; writer failure leaves no partial file; no side-effect modules are imported.

- [ ] **Step 5: Run dispatch tests and verify RED**

Expected: failures because `dispatch_command()` is not implemented.

- [ ] **Step 6: Implement pre-market lineage gate and sanitized main**

Dispatch order is fixed: require files, strict-load V3, strict-load and identify Research, strict-load parent attribution with expected identities, verify split/fingerprint/safety/complete coverage, then and only then load bounded stocks/indexes, build review, and call the injected writer.

On success print only the path. At the outer CLI boundary catch provider/config errors, print exactly `五日排名V3组件归因失败`, and return 2 without traceback, URL, credential, code, or provider payload.

- [ ] **Step 7: Run tests and static checks**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_five_day_ranking_v3_component_attribution.py tests/unit/test_five_day_ranking_v3_component_attribution_report.py tests/unit/test_five_day_ranking_v3_attribution_market.py tests/unit/test_analyze_five_day_ranking_v3_component_attribution_cli.py -q
/opt/anaconda3/bin/ruff check stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution_report.py stock_ai/buy_point_selection/five_day_ranking_v3_attribution_market.py scripts/analysis/analyze_five_day_ranking_v3_component_attribution.py tests/unit/test_five_day_ranking_v3_component_attribution.py tests/unit/test_five_day_ranking_v3_component_attribution_report.py tests/unit/test_five_day_ranking_v3_attribution_market.py tests/unit/test_analyze_five_day_ranking_v3_component_attribution_cli.py
.venv/bin/python -m compileall -q stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution.py stock_ai/buy_point_selection/five_day_ranking_v3_component_attribution_report.py stock_ai/buy_point_selection/five_day_ranking_v3_attribution_market.py scripts/analysis/analyze_five_day_ranking_v3_component_attribution.py
```

- [ ] **Step 8: Commit**

```bash
git add scripts/analysis/analyze_five_day_ranking_v3_component_attribution.py tests/unit/test_analyze_five_day_ranking_v3_component_attribution_cli.py
git diff --cached --check
git commit -m "功能(stock-ai)：增加V3组件归因命令"
```

---

### Task 7: Verify and Run Frozen Real Data Twice

**Files:**
- Verify only; generated component artifacts remain under ignored `output/`.

**Interfaces:**
- Consumes: canonical Research, V1, V2, V3, parent attribution, and the new CLI.
- Produces: one strict aggregate-only idempotent component artifact and an aggregate summary.

- [ ] **Step 1: Run the full relevant regression suite**

Run the existing 20-file five-day suite plus the four new test files. Expected: zero failures and no collection warnings.

- [ ] **Step 2: Strict-load the frozen chain**

```text
Research     2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59
V1           d3e53dceee1f31e1ba33bf0f36c292a52fbd0c30b002e026941dead7e54374a3
V2           99e1d16eae69669c8bed05bfabff276c8521e754d17a5a15aa258f8ac8888b22
V3           6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb
Attribution  2a934981be23e8fad0957c166dc1af4059327220b492599bb195c8abd28bbd7e
```

- [ ] **Step 3: Run the real CLI**

```bash
PYTHONPATH=. .venv/bin/python scripts/analysis/analyze_five_day_ranking_v3_component_attribution.py diagnose-ranking-components --train-artifact output/research/buy_point_five_day_returns/ranking-v3-train-6a54b2922b089b00511fe274ea16e8e0d207f8927d373e675fe33f61b82ab5bb.json --research-artifact output/research/buy_point_five_day_returns/research-2b52de79dfeb39a8e6b7ead3190473d157de224a007d7400b746883d04f91b59.json --market-attribution-artifact output/research/buy_point_five_day_returns/ranking-v3-train-attribution-2a934981be23e8fad0957c166dc1af4059327220b492599bb195c8abd28bbd7e.json --output-dir output/research/buy_point_five_day_returns
```

Require exit 0, `status=COMPLETE`, 16 baseline reproductions, 48 comparable fold ablations, 24 labels, full coverage, safety flags, and no forbidden keys.

- [ ] **Step 4: Prove idempotency and repository safety**

Record path and `shasum -a 256`, rerun identically, and require the same path/hash. Confirm the artifact is ignored, staging is empty, and target files are clean.

- [ ] **Step 5: Report and stop**

Report only policy/component labels, fold-level deltas, correlation ranges, tie/sample counts, and safety status. Do not expose codes/dates/rows, modify V3, or start the challenger suite in this plan.
