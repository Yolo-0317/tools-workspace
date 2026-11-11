# Strong Sector Rotation Detector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manual, fail-closed sector-rotation detector that selects up to six de-duplicated strong industry chains, keeps up to ten observation stocks per chain, promotes up to three conditional trade candidates, persists history in MySQL, and emits a Markdown report without changing existing selection or trading state.

**Architecture:** Add a standalone `stock_ai.sector_rotation` package with pure normalization, scoring, state, selection, pricing, persistence, and reporting units. Reuse Eastmoney OpenCLI only as the live objective-data provider and MySQL as the daily-bar, holdings, and history source; a thin service and CLI orchestrate one manual run. Keep every decision explainable and persist the score inputs, threshold version, state reasons, and rejection reasons.

**Tech Stack:** Python 3.10+, dataclasses, Decimal, Enum, SQLAlchemy 2.x, MySQL 8, existing Eastmoney OpenCLI helpers, pytest 9.x, Markdown.

## Global Constraints

- First release is manual only: no Docker scheduler, launchd, Home Hub, Feishu, WeChat, or other push integration.
- Do not modify `selection_daily_results`, current holdings, monitoring rules, advisor phase, or any order state.
- Never call or depend on the deprecated Eastmoney eight/eleven-dimension diagnosis.
- Scan detailed industries but output at most six de-duplicated chains: three strongest, two strengthening, one pullback; do not backfill weak chains when a bucket is short.
- Keep at most ten observation stocks per chain: two leaders, three followers, three catch-up names, and two pullback names.
- Promote at most three formal candidates per chain: one leader, one catch-up, and one pullback; overheated names remain observation-only.
- Default individual anti-chase thresholds are signal-day gain above 7%, five-day gain above 15%, or MA5 distance above 5%; store thresholds as policy fields, not scattered literals.
- Industry-chain merging is driven by explicit checked-in configuration, never by an LLM classification call.
- Missing current sector ranking is fatal; incomplete constituents or prices downgrade the affected chain/name and must not produce fabricated formal levels.
- Use the broker/MySQL holdings only to set `held=True`; holdings never bypass risk or anti-chase gates.
- User-visible CLI and report copy contains no emoji.
- Add no new dependency unless the approved design is revised.
- Commit messages are in Chinese.

---

### Task 1: Domain Models and Explicit Industry-Chain Normalization

**Files:**
- Create: `stock-ai/stock_ai/sector_rotation/__init__.py`
- Create: `stock-ai/stock_ai/sector_rotation/models.py`
- Create: `stock-ai/stock_ai/sector_rotation/industry_chains.json`
- Create: `stock-ai/stock_ai/sector_rotation/normalization.py`
- Test: `stock-ai/tests/unit/test_sector_rotation_normalization.py`

**Interfaces:**
- Produces: `RotationState`, `RotationBucket`, `CandidateRole`, `RotationPolicy`, `RawSectorRow`, `ChainRule`, `NormalizedChain`, `MemberSnapshot`, `ChainMetrics`, `ChainScore`, `PriceLevels`, `RotationCandidate`, `RotationRunResult`.
- Produces: `load_chain_rules(path: Path | None = None) -> tuple[ChainRule, ...]`.
- Produces: `normalize_sector_name(name: str) -> str`.
- Produces: `merge_sector_rows(rows: Sequence[RawSectorRow], rules: Sequence[ChainRule]) -> tuple[NormalizedChain, ...]`.
- Consumers in later tasks must import these names from `stock_ai.sector_rotation`, not duplicate equivalent dataclasses.

- [ ] **Step 1: Write failing normalization tests**

```python
from stock_ai.sector_rotation.models import RawSectorRow
from stock_ai.sector_rotation.normalization import load_chain_rules, merge_sector_rows


def _row(code: str, name: str, rank: int) -> RawSectorRow:
    return RawSectorRow(code, name, rank, 2.0, "000001", "示例", 5.0)


def test_agriculture_subsectors_merge_into_one_stable_chain() -> None:
    chains = merge_sector_rows(
        (_row("BK1", "种子", 1), _row("BK2", "粮食种植", 5), _row("BK3", "种植业", 9)),
        load_chain_rules(),
    )
    assert [(value.chain_code, value.chain_name) for value in chains] == [
        ("agriculture_planting", "农业种植")
    ]
    assert chains[0].raw_sector_codes == ("BK1", "BK2", "BK3")


def test_unmapped_valid_sector_gets_a_stable_fallback_chain() -> None:
    chains = merge_sector_rows((_row("BK999", "新型材料", 12),), load_chain_rules())
    assert chains[0].chain_code == "raw_bk999"
    assert chains[0].chain_name == "新型材料"


def test_navigation_labels_are_rejected_before_merging() -> None:
    chains = merge_sector_rows((_row("BK0", "今日资金流排行", 1),), load_chain_rules())
    assert chains == ()
```

- [ ] **Step 2: Run the test and confirm the missing-package failure**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_normalization.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'stock_ai.sector_rotation'`.

- [ ] **Step 3: Add immutable models and enums**

Implement these exact enum values and policy defaults in `models.py`:

```python
class RotationState(str, Enum):
    LATENT = "LATENT"
    STARTING = "STARTING"
    CONFIRMED = "CONFIRMED"
    OVERHEATED = "OVERHEATED"
    FADING = "FADING"


class RotationBucket(str, Enum):
    STRONG = "STRONG"
    STRENGTHENING = "STRENGTHENING"
    PULLBACK = "PULLBACK"


class CandidateRole(str, Enum):
    LEADER = "LEADER"
    FOLLOWER = "FOLLOWER"
    CATCH_UP = "CATCH_UP"
    PULLBACK = "PULLBACK"


@dataclass(frozen=True)
class RotationPolicy:
    version: str = "sector-rotation-1.0.0"
    strongest_count: int = 3
    strengthening_count: int = 2
    pullback_count: int = 1
    observation_limit: int = 10
    formal_limit: int = 3
    latent_score_min: Decimal = Decimal("45")
    starting_score_min: Decimal = Decimal("60")
    confirm_snapshots: int = 2
    fading_score_drop: Decimal = Decimal("15")
    signal_day_overheat_pct: Decimal = Decimal("7")
    return5_overheat_pct: Decimal = Decimal("15")
    ma5_distance_overheat_pct: Decimal = Decimal("5")
```

Add the remaining dataclasses with the field names used by Tasks 2-8:

```python
RawSectorRow(board_code, sector_name, rank, change_pct, leader_code, leader_name, leader_change_pct)
ChainRule(chain_code, chain_name, parent_code, aliases, keywords, excludes, priority, coexistence_codes)
NormalizedChain(chain_code, chain_name, parent_code, raw_sector_codes, raw_sector_names, best_rank, raw_change_pct)
MemberSnapshot(code, name, price, change_pct, return5_pct, amount_ratio, ma5, ma10, ma20, ma5_distance_pct, high20, low20, atr14, liquid, risk_veto, held, data_complete)
ChainMetrics(return_percentile, rank_improvement, breadth_ratio, above_ma5_ratio, above_ma20_ratio, strengthening_count, liquid_count, amount_ratio, advancing_amount_ratio, persistence_count, leader_concentration, data_complete)
ChainScore(total, strength_score, breadth_score, amount_score, persistence_score, structure_score, overheat_penalty, reasons)
PriceLevels(watch_price, trigger_price, no_chase_price, invalidation_price)
RotationCandidate(chain_code, code, name, role, pool_rank, formal_eligible, held, metrics, levels, reasons, rejection_reasons)
RotationRunResult(run_id, observed_at, trade_date, edition, policy_version, chains, candidates, warnings, report_path)
```

Use explicit type annotations (`Decimal`, `date`, `datetime`, tuples, and mappings) and frozen dataclasses.

- [ ] **Step 4: Add checked-in chain rules and normalization**

Seed `industry_chains.json` with at least these deterministic families: agriculture planting, animal husbandry, semiconductors, PCB/electronic materials, AI hardware, copper/aluminum industrial metals, precious metals, rare metals, lithium battery materials, photovoltaic, power utilities, energy storage, oil and gas, chemicals, consumer retail, and robotics. Each entry must contain `chain_code`, `chain_name`, `parent_code`, `aliases`, `keywords`, `excludes`, `priority`, and `coexistence_codes`.

`merge_sector_rows` must:

1. remove navigation/broken rows;
2. match aliases before keywords;
3. apply excludes;
4. choose highest-priority rule on ambiguity;
5. create `raw_<lower-board-code>` fallback chains;
6. sort raw members and final chains deterministically by best rank then code.

- [ ] **Step 5: Run normalization tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_normalization.py -v`

Expected: PASS, 3 tests.

- [ ] **Step 6: Commit Task 1**

```bash
git add stock-ai/stock_ai/sector_rotation stock-ai/tests/unit/test_sector_rotation_normalization.py
git commit -m "feat(stock-ai)：新增板块轮动模型与行业归并"
```

### Task 2: Explainable Scoring and State Transitions

**Files:**
- Create: `stock-ai/stock_ai/sector_rotation/scoring.py`
- Test: `stock-ai/tests/unit/test_sector_rotation_scoring.py`

**Interfaces:**
- Consumes: `RotationPolicy`, `RotationState`, `ChainMetrics`, `ChainScore` from Task 1.
- Produces: `score_chain(metrics: ChainMetrics, policy: RotationPolicy) -> ChainScore`.
- Produces: `classify_state(score: ChainScore, metrics: ChainMetrics, previous: Sequence[tuple[RotationState, ChainScore]], policy: RotationPolicy) -> tuple[RotationState | None, tuple[str, ...]]`; `None` means the chain is below the latent threshold and is not a reportable rotation state.

- [ ] **Step 1: Write failing score and transition tests**

```python
def test_single_leader_spike_cannot_be_called_starting() -> None:
    metrics = complete_metrics(
        return_percentile=0.95,
        breadth_ratio=0.18,
        amount_ratio=1.60,
        leader_concentration=0.86,
    )
    score = score_chain(metrics, RotationPolicy())
    state, reasons = classify_state(score, metrics, (), RotationPolicy())
    assert state is RotationState.OVERHEATED
    assert "LEADER_ONLY" in reasons


def test_two_valid_strong_snapshots_promote_starting_to_confirmed() -> None:
    policy = RotationPolicy()
    metrics = complete_metrics(return_percentile=0.88, breadth_ratio=0.68, amount_ratio=1.35)
    score = score_chain(metrics, policy)
    state, _ = classify_state(
        score,
        metrics,
        ((RotationState.STARTING, score), (RotationState.STARTING, score)),
        policy,
    )
    assert state is RotationState.CONFIRMED


def test_confirmed_chain_with_score_and_breadth_collapse_fades() -> None:
    policy = RotationPolicy()
    previous_score = replace(score_chain(complete_metrics(), policy), total=Decimal("78"))
    metrics = complete_metrics(breadth_ratio=0.32, amount_ratio=0.71)
    score = replace(score_chain(metrics, policy), total=Decimal("55"))
    state, reasons = classify_state(score, metrics, ((RotationState.CONFIRMED, previous_score),), policy)
    assert state is RotationState.FADING
    assert "SCORE_DROPPED" in reasons
```

- [ ] **Step 2: Run the test and confirm missing functions**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_scoring.py -v`

Expected: FAIL importing `score_chain` and `classify_state`.

- [ ] **Step 3: Implement the five score components**

Use bounded component scores exactly summing to the design weights:

```python
strength = 30 * clamp((metrics.return_percentile + normalized_rank_improvement) / 2)
breadth = 25 * clamp(mean(metrics.breadth_ratio, metrics.above_ma5_ratio, metrics.above_ma20_ratio))
amount = 20 * clamp(mean(scale(metrics.amount_ratio, 0.70, 1.50), metrics.advancing_amount_ratio))
persistence = 15 * clamp(metrics.persistence_count / policy.confirm_snapshots)
structure = 10 * clamp(1 - metrics.leader_concentration)
total = max(Decimal("0"), strength + breadth + amount + persistence + structure - penalty)
```

The overheat/quality penalty must emit reason codes for `LEADER_ONLY`, `BREADTH_WEAK`, `AMOUNT_WEAK`, and `DATA_INCOMPLETE`; incomplete data cannot classify as `STARTING` or `CONFIRMED`.

- [ ] **Step 4: Implement deterministic state precedence**

Apply in this order: incomplete downgrade, overheat, fading, confirmed, starting, latent, unqualified `None`. A chain with no prior snapshot cannot be `CONFIRMED`; a chain with no prior starting/confirmed state cannot be `FADING`. Store both score reasons and transition reasons.

- [ ] **Step 5: Run scoring tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_scoring.py -v`

Expected: PASS, including the three transition tests.

- [ ] **Step 6: Commit Task 2**

```bash
git add stock-ai/stock_ai/sector_rotation/scoring.py stock-ai/tests/unit/test_sector_rotation_scoring.py
git commit -m "feat(stock-ai)：实现板块评分与轮动状态机"
```

### Task 3: Six-Chain Core Pool and Ten-Stock Observation Pools

**Files:**
- Create: `stock-ai/stock_ai/sector_rotation/selection.py`
- Test: `stock-ai/tests/unit/test_sector_rotation_selection.py`

**Interfaces:**
- Consumes: normalized/scored chains, states, policy, and `MemberSnapshot`.
- Produces: `select_core_pool(chains: Sequence[ScoredChain], policy: RotationPolicy) -> tuple[SelectedChain, ...]` where `ScoredChain` and `SelectedChain` are added to `models.py` with all snapshot fields plus `state`, `bucket`, `score`, and `state_reasons`.
- Produces: `build_observation_pool(chain: SelectedChain, members: Sequence[MemberSnapshot], policy: RotationPolicy) -> tuple[RotationCandidate, ...]`.
- Produces: `promote_formal_candidates(observations: Sequence[RotationCandidate], policy: RotationPolicy) -> tuple[RotationCandidate, ...]`.

- [ ] **Step 1: Write failing pool-allocation tests**

```python
def test_core_pool_enforces_three_two_one_and_parent_deduplication() -> None:
    selected = select_core_pool(sample_scored_chains(), RotationPolicy())
    assert [value.bucket for value in selected].count(RotationBucket.STRONG) == 3
    assert [value.bucket for value in selected].count(RotationBucket.STRENGTHENING) == 2
    assert [value.bucket for value in selected].count(RotationBucket.PULLBACK) == 1
    assert len({value.parent_code for value in selected}) == len(selected)


def test_short_bucket_is_not_filled_with_a_weak_chain() -> None:
    selected = select_core_pool(only_two_qualified_chains(), RotationPolicy())
    assert len(selected) == 2


def test_observation_pool_keeps_ten_but_only_three_formal_roles() -> None:
    observed = build_observation_pool(sample_selected_chain(), sample_members(20), RotationPolicy())
    formal = promote_formal_candidates(observed, RotationPolicy())
    assert len(observed) == 10
    assert len(formal) <= 3
    assert {value.role for value in formal} <= {
        CandidateRole.LEADER,
        CandidateRole.CATCH_UP,
        CandidateRole.PULLBACK,
    }
```

- [ ] **Step 2: Run and confirm missing selection functions**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_selection.py -v`

Expected: FAIL importing the three functions.

- [ ] **Step 3: Implement six-chain allocation**

Strong accepts only `STARTING`/`CONFIRMED`; strengthening accepts only `LATENT`; pullback accepts a previously confirmed chain whose current metrics remain complete and whose state is neither `FADING` nor `OVERHEATED`. Sort by state priority, post-penalty score, breadth, persistence, structure, then `chain_code`. Apply parent de-duplication before consuming bucket capacity, except for explicitly configured coexistence pairs with member overlap below the policy threshold.

- [ ] **Step 4: Implement observation roles and quotas**

Classify every complete, liquid, non-veto member with deterministic role scores:

- leader: sector-relative strength and amount expansion;
- follower: positive sector-relative trend without leader rank;
- catch-up: above MA20, improving amount, not more than the policy MA5 distance;
- pullback: above MA20, near MA5/MA10, contraction or controlled retracement.

Select 2/3/3/2 by role, de-duplicate by code, and do not backfill from a role that fails its minimum requirements. Append reason codes such as `LEADER_STRENGTH`, `FOLLOWER_EXPANSION`, `CATCH_UP_NOT_EXTENDED`, and `PULLBACK_NEAR_SUPPORT`.

- [ ] **Step 5: Implement formal promotion and anti-chase**

Promote at most one eligible member for leader, catch-up, and pullback. Set `formal_eligible=False` and add exact rejection codes when `risk_veto`, incomplete data, signal-day gain, five-day gain, or MA5 distance breaches policy. `held=True` must not change ordering or eligibility.

- [ ] **Step 6: Run selection tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_selection.py -v`

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add stock-ai/stock_ai/sector_rotation/models.py stock-ai/stock_ai/sector_rotation/selection.py stock-ai/tests/unit/test_sector_rotation_selection.py
git commit -m "feat(stock-ai)：实现轮动核心池与候选分层"
```

### Task 4: Explainable Conditional Price Levels

**Files:**
- Create: `stock-ai/stock_ai/sector_rotation/pricing.py`
- Test: `stock-ai/tests/unit/test_sector_rotation_pricing.py`

**Interfaces:**
- Consumes: eligible `RotationCandidate`, `MemberSnapshot`, and at least twenty `BuyPointBar` values.
- Produces: `calculate_price_levels(candidate: RotationCandidate, member: MemberSnapshot, bars: Sequence[BuyPointBar], policy: RotationPolicy) -> PriceLevels | None`.
- Produces invariant for long candidates: `invalidation_price < watch_price <= trigger_price < no_chase_price`.

- [ ] **Step 1: Write failing role-specific and invariant tests**

```python
@pytest.mark.parametrize("role", [CandidateRole.LEADER, CandidateRole.CATCH_UP, CandidateRole.PULLBACK])
def test_price_levels_are_ordered_for_each_formal_role(role: CandidateRole) -> None:
    levels = calculate_price_levels(candidate(role), member(), bars60(), RotationPolicy())
    assert levels is not None
    assert levels.invalidation_price < levels.watch_price <= levels.trigger_price < levels.no_chase_price


def test_incomplete_structure_downgrades_instead_of_guessing_prices() -> None:
    assert calculate_price_levels(candidate(CandidateRole.CATCH_UP), member(), bars10(), RotationPolicy()) is None
```

- [ ] **Step 2: Run and confirm the missing pricing module**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_pricing.py -v`

Expected: FAIL importing `calculate_price_levels`.

- [ ] **Step 3: Implement structure-first pricing**

Use `high20`, `low20`, MA5/10/20, and ATR14 already present on `MemberSnapshot`; verify them against supplied bars. Use role-specific anchors:

- leader/catch-up watch price: maximum of MA5 and nearest platform support;
- leader/catch-up trigger: structure high plus `0.10 * ATR14`, capped below the no-chase level;
- pullback watch price: MA5/MA10 support band midpoint;
- pullback trigger: most recent reversal high plus `0.05 * ATR14`;
- invalidation: below the relevant structural low by `0.10 * ATR14` but never above MA20;
- no-chase: minimum of `trigger * 1.05` and `MA5 * 1.05` when both are valid.

Quantize all prices to `Decimal("0.01")`. Return `None` for fewer than twenty bars, non-positive ATR, stale member data, violated ordering, or a trigger already above no-chase.

- [ ] **Step 4: Run pricing tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_pricing.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add stock-ai/stock_ai/sector_rotation/pricing.py stock-ai/tests/unit/test_sector_rotation_pricing.py
git commit -m "feat(stock-ai)：计算板块候选条件价"
```

### Task 5: Objective Data Providers and Batch Daily-Bar Assembly

**Files:**
- Modify: `stock-ai/scripts/tools/fetch_eastmoney_quotes.py`
- Modify: `stock-ai/scripts/tools/portfolio_db.py`
- Create: `stock-ai/stock_ai/sector_rotation/providers.py`
- Test: `stock-ai/tests/unit/test_sector_rotation_providers.py`
- Modify: `stock-ai/tests/unit/test_fetch_eastmoney_quotes.py`

**Interfaces:**
- Produces from Eastmoney helper constituent rows: `code`, `name`, `price`, `change_pct`, `amount`, `turnover_rate`.
- Produces: `load_stock_daily_panel(codes: Sequence[str], *, limit: int = 60, engine: Engine | None = None) -> dict[str, list[dict[str, Any]]]` in `portfolio_db.py`, ordered ascending within each code.
- Produces protocol: `RotationDataProvider.fetch_ranked_sectors(limit: int)`, `fetch_chain_members(chains)`, `load_daily_panel(codes, limit)`, `load_held_codes()`, `load_previous_snapshots(chain_codes)`.
- Produces implementation: `ProductionRotationDataProvider`.

- [ ] **Step 1: Write failing provider and parser-contract tests**

```python
def test_provider_converts_objective_rows_without_inventing_missing_amount() -> None:
    provider = ProductionRotationDataProvider(
        sector_fetcher=lambda **_: [{"board_code": "BK1", "sector": "铜", "sector_chg": 1.2, "code": "600001", "leader_name": "甲", "leader_chg": 5.0}],
        constituent_fetcher=lambda *_args, **_kwargs: [{"code": "600001", "name": "甲", "price": 10.2, "change_pct": 5.0, "amount": None, "turnover_rate": 2.1}],
        daily_loader=lambda *_args, **_kwargs: {},
        holdings_loader=lambda: set(),
    )
    rows = provider.fetch_ranked_sectors(20)
    members = provider.fetch_chain_members(rows)
    assert rows[0].sector_name == "铜"
    assert members["BK1"][0]["amount"] is None


def test_batch_daily_loader_returns_ascending_bars_per_code(fake_engine) -> None:
    panel = load_stock_daily_panel(["000001", "600001"], limit=60, engine=fake_engine)
    assert list(panel) == ["000001", "600001"]
    assert panel["000001"][0]["trade_date"] < panel["000001"][-1]["trade_date"]
```

- [ ] **Step 2: Run provider tests and confirm missing interfaces**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_providers.py tests/unit/test_fetch_eastmoney_quotes.py -v`

Expected: FAIL on missing provider and batch loader.

- [ ] **Step 3: Extend Eastmoney constituent payload only with objective fields**

Add `f2,f3,f6,f8` to `_jsonp_board_constituents_js` and map them to `price`, `change_pct`, `amount`, and `turnover_rate`. Keep existing keys and function signature backward compatible. Do not add direct HTTP access.

- [ ] **Step 4: Add one-query batch daily-bar loader**

Implement `load_stock_daily_panel` with a MySQL 8 window query using `ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC)`, then reverse each code's rows into ascending order. Normalize six-digit input codes and return empty lists for valid codes without bars. Do not loop `load_stock_daily_bars` once per member.

- [ ] **Step 5: Implement injected production provider**

Keep OpenCLI functions, daily loader, holdings loader, and snapshot loader injectable. The provider must not swallow Eastmoney ranking failures. It may return partial constituent groups, but must attach completeness warnings used by the service.

- [ ] **Step 6: Run provider and existing fetch tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_providers.py tests/unit/test_fetch_eastmoney_quotes.py -v`

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git add stock-ai/scripts/tools/fetch_eastmoney_quotes.py stock-ai/scripts/tools/portfolio_db.py stock-ai/stock_ai/sector_rotation/providers.py stock-ai/tests/unit/test_sector_rotation_providers.py stock-ai/tests/unit/test_fetch_eastmoney_quotes.py
git commit -m "feat(stock-ai)：接入板块行情与批量日线数据"
```

### Task 6: MySQL Schema and Atomic Rotation Repository

**Files:**
- Create: `stock-mysql/sql/018_sector_rotation.sql`
- Create: `stock-ai/stock_ai/sector_rotation/repository.py`
- Test: `stock-ai/tests/unit/test_sector_rotation_repository.py`

**Interfaces:**
- Produces protocol: `RotationRepository.start_run(...) -> str`, `load_history(chain_codes, limit=3)`, `save_success(result)`, `save_failure(run_id, code, message)`, `load_latest_result()`.
- Produces: `SQLRotationRepository(connection)` and `MemoryRotationRepository` for tests/service fixtures.
- `save_success` atomically writes one run, chain snapshots, and candidates; failure rolls back all success rows and then records a failed run status.

- [ ] **Step 1: Write failing schema-contract and repository tests**

```python
def test_schema_declares_all_three_tables() -> None:
    sql = Path("../stock-mysql/sql/018_sector_rotation.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS sector_rotation_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS sector_rotation_snapshots" in sql
    assert "CREATE TABLE IF NOT EXISTS sector_rotation_candidates" in sql


def test_repository_round_trip_preserves_reasons_levels_and_held_flag() -> None:
    repository = MemoryRotationRepository()
    result = successful_result()
    repository.save_success(result)
    loaded = repository.load_latest_result()
    assert loaded.chains[0].score.reasons == result.chains[0].score.reasons
    assert loaded.candidates[0].levels == result.candidates[0].levels
    assert loaded.candidates[0].held is True


def test_failed_success_write_leaves_no_partial_snapshots(fake_connection) -> None:
    repository = SQLRotationRepository(fake_connection_that_fails_on_candidates())
    with pytest.raises(RuntimeError):
        repository.save_success(successful_result())
    assert fake_connection.rollback_called
```

- [ ] **Step 2: Run and confirm missing schema/repository failures**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_repository.py -v`

Expected: FAIL because migration and repository do not exist.

- [ ] **Step 3: Add idempotent migration 018**

Create the three tables and exact uniqueness constraints from the approved design:

- runs primary key `run_id`, indexes on `(trade_date, observed_at)` and `status`;
- snapshots unique `(run_id, chain_code)`, indexes on `(chain_code, observed_at)` and `(state, observed_at)`;
- candidates unique `(run_id, chain_code, ts_code)`, indexes on `(ts_code, observed_at)` and `(formal_eligible, role, observed_at)`.

Use `DATETIME(6)`, `DECIMAL`, `JSON`, `utf8mb4`, and foreign keys with `ON DELETE CASCADE` from snapshots/candidates to runs. Include `threshold_version`, completeness, all score components, four prices, reasons JSON, rejection JSON, and raw JSON.

- [ ] **Step 4: Implement memory and SQL repositories**

Serialize Decimal/date/datetime/Enum values explicitly. Use SQLAlchemy `text()` with parameter dictionaries. `load_history` returns newest-first typed snapshots and never mixes threshold versions without exposing each snapshot's version.

- [ ] **Step 5: Run repository tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_repository.py -v`

Expected: PASS.

- [ ] **Step 6: Validate migration through the existing initializer in a disposable/test MySQL when available**

Run: `cd stock-mysql && bash scripts/init-db.sh`

Expected: output contains `apply: 018_sector_rotation.sql` and lists all three new tables. If production MySQL is the only configured target, do not run this step automatically; use the repository unit tests and ask for the normal migration approval during execution.

- [ ] **Step 7: Commit Task 6**

```bash
git add stock-mysql/sql/018_sector_rotation.sql stock-ai/stock_ai/sector_rotation/repository.py stock-ai/tests/unit/test_sector_rotation_repository.py
git commit -m "feat(stock-ai)：持久化板块轮动历史快照"
```

### Task 7: Markdown Report With Ten-Stock Detail and State Changes

**Files:**
- Create: `stock-ai/stock_ai/sector_rotation/reporting.py`
- Test: `stock-ai/tests/unit/test_sector_rotation_reporting.py`

**Interfaces:**
- Consumes: `RotationRunResult` and optional previous typed result.
- Produces: `render_rotation_report(result: RotationRunResult, previous: RotationRunResult | None) -> str`.
- Produces: `write_rotation_report(result, output_path: Path | None = None) -> Path` with default `output/sector_rotation_YYYYMMDD_HHMM.md`.

- [ ] **Step 1: Write failing full-report tests**

```python
def test_report_contains_freshness_six_buckets_ten_stock_pool_and_formal_levels() -> None:
    text = render_rotation_report(report_result(), previous_result())
    assert "数据时间与完整性" in text
    assert "当前最强" in text
    assert "正在增强" in text
    assert "回踩观察" in text
    assert "状态变化" in text
    assert "持仓交集" in text
    assert "观察价" in text and "触发价" in text and "禁追价" in text and "失效位" in text
    assert "禁止追高" in text
    assert "非自动交易" in text
    assert "🚀" not in text


def test_report_explains_a_short_bucket_instead_of_padding_it() -> None:
    text = render_rotation_report(short_bucket_result(), None)
    assert "本次仅有2个方向通过门槛" in text
```

- [ ] **Step 2: Run and confirm missing report functions**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_reporting.py -v`

Expected: FAIL importing report functions.

- [ ] **Step 3: Implement report sections in approved order**

Render: freshness; six-direction summary; transitions; holdings intersection; each chain's up-to-ten observation table; up-to-three formal plan cards; overheated/no-chase section; fading section; limitations and threshold version. Reasons precede scores. Missing levels display `降级为观察：<reason>` rather than dashes that resemble valid prices.

- [ ] **Step 4: Run report tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_reporting.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 7**

```bash
git add stock-ai/stock_ai/sector_rotation/reporting.py stock-ai/tests/unit/test_sector_rotation_reporting.py
git commit -m "feat(stock-ai)：生成板块轮动检测报告"
```

### Task 8: Fail-Closed Service Orchestration and Manual CLI

**Files:**
- Create: `stock-ai/stock_ai/sector_rotation/service.py`
- Create: `stock-ai/scripts/analysis/detect_sector_rotation.py`
- Test: `stock-ai/tests/unit/test_sector_rotation_service.py`
- Test: `stock-ai/tests/unit/test_detect_sector_rotation_cli.py`

**Interfaces:**
- Produces: `detect_sector_rotation(*, provider: RotationDataProvider, repository: RotationRepository | None, policy: RotationPolicy, observed_at: datetime, edition: str, top_sectors: int, stocks_per_sector: int) -> RotationRunResult`.
- Produces CLI `main(argv: Sequence[str] | None = None) -> int`.
- CLI options exactly: `--edition auto|intraday|close`, `--top-sectors`, `--stocks-per-sector`, `--output`, `--no-db`.

- [ ] **Step 1: Write failing happy-path, fatal-source, partial-chain, and CLI tests**

```python
def test_service_persists_and_reports_a_complete_manual_run(tmp_path: Path) -> None:
    repository = MemoryRotationRepository()
    result = detect_sector_rotation(
        provider=fixture_provider(),
        repository=repository,
        policy=RotationPolicy(),
        observed_at=aware_dt("2026-08-18T14:40:00+08:00"),
        edition="intraday",
        top_sectors=6,
        stocks_per_sector=10,
    )
    assert len(result.chains) <= 6
    assert all(sum(c.chain_code == chain.chain_code for c in result.candidates) <= 10 for chain in result.chains)
    assert repository.load_latest_result().run_id == result.run_id


def test_ranking_failure_records_failure_and_returns_nonzero_from_cli(monkeypatch) -> None:
    monkeypatch.setattr(cli, "build_provider", lambda: failing_ranking_provider())
    assert cli.main([]) == 2


def test_incomplete_constituents_never_produce_formal_prices() -> None:
    result = detect_with_one_incomplete_chain()
    affected = [c for c in result.candidates if c.chain_code == "copper"]
    assert affected
    assert all(not c.formal_eligible and c.levels is None for c in affected)
```

- [ ] **Step 2: Run and confirm missing service/CLI failures**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_service.py tests/unit/test_detect_sector_rotation_cli.py -v`

Expected: FAIL importing service and CLI.

- [ ] **Step 3: Implement two-stage data acquisition**

First fetch the ranked industry universe and normalize it. Fetch constituents and daily panels only for a bounded preselection consisting of the top sixty raw industries plus chains present in recent history; this avoids hundreds of sequential OpenCLI calls while preserving improving and pullback chains. Build metrics, scores, and states only after constituent completeness is known.

- [ ] **Step 4: Implement service orchestration and failure semantics**

Use this exact order: start run, fetch ranking, normalize, load history, fetch bounded constituents, batch-load bars/holdings, score/state, select core pool, build observations, promote formal candidates, calculate levels, persist atomically, render report. Ranking absence raises `RotationSourceError("SECTOR_RANKING_UNAVAILABLE")`. Partial chains remain in diagnostics but cannot produce formal prices. Repository failure returns a nonzero CLI status even if a local report was rendered.

- [ ] **Step 5: Implement CLI and edition resolution**

`auto` resolves to `intraday` during A-share sessions and to `close` after 15:00 on a trading day; otherwise it uses the latest valid close and states that explicitly. Validate `1 <= top_sectors <= 12` and `3 <= stocks_per_sector <= 20`, with defaults 6 and 10. Print only the report path, run status, selected direction count, and warnings; do not dump raw account or portfolio values.

- [ ] **Step 6: Run service and CLI tests**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_service.py tests/unit/test_detect_sector_rotation_cli.py -v`

Expected: PASS.

- [ ] **Step 7: Run the full new-module unit suite**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_*.py tests/unit/test_detect_sector_rotation_cli.py -v`

Expected: PASS with zero failures.

- [ ] **Step 8: Commit Task 8**

```bash
git add stock-ai/stock_ai/sector_rotation/service.py stock-ai/scripts/analysis/detect_sector_rotation.py stock-ai/tests/unit/test_sector_rotation_service.py stock-ai/tests/unit/test_detect_sector_rotation_cli.py
git commit -m "feat(stock-ai)：增加板块轮动手动检测命令"
```

### Task 9: Documentation, Dry Run, and Regression Verification

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md`
- Modify: `stock-ai/investment-agent/docs/skills/stock-strategy-selector/SKILL.md`
- Modify: `stock-ai/investment-agent/docs/skills/stock-strategy-selector/references/strategy-playbook.md`
- Test: `stock-ai/tests/unit/test_sector_rotation_docs.py`

**Interfaces:**
- Documents the manual command, data sources, output path, state meanings, ten-observation/three-formal split, and fail-closed limitations.
- Does not document any scheduler, push, or automatic order integration.

- [ ] **Step 1: Write a failing documentation-contract test**

```python
def test_docs_publish_only_the_manual_sector_rotation_entrypoint() -> None:
    capabilities = Path("docs/CAPABILITIES.md").read_text()
    playbook = Path("investment-agent/docs/skills/stock-strategy-selector/references/strategy-playbook.md").read_text()
    command = ".venv/bin/python -m scripts.analysis.detect_sector_rotation"
    assert command in capabilities
    assert command in playbook
    assert "每个方向最多10只观察股" in capabilities
    assert "自动下单" in capabilities and "不" in capabilities
```

- [ ] **Step 2: Run and confirm the documentation test fails**

Run: `cd stock-ai && .venv/bin/python -m pytest tests/unit/test_sector_rotation_docs.py -v`

Expected: FAIL because the command is not documented.

- [ ] **Step 3: Update the three entry documents**

Add one concise capability section and one holdings-aware routing note. State that the module is manual, independent from Top5, uses Eastmoney for live objective data and MySQL for history, and does not create orders or monitoring rules. Link the approved design and this implementation plan.

- [ ] **Step 4: Run documentation and focused regression tests**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_sector_rotation_*.py \
  tests/unit/test_detect_sector_rotation_cli.py \
  tests/unit/test_fetch_eastmoney_quotes.py \
  tests/unit/test_buy_point_gates.py -v
```

Expected: PASS with zero failures.

- [ ] **Step 5: Run a no-write fixture/dry-run CLI verification**

Run: `cd stock-ai && .venv/bin/python -m scripts.analysis.detect_sector_rotation --no-db --top-sectors 6 --stocks-per-sector 10`

Expected: exit 0, prints one Markdown report path, at most six selected directions, and no raw holdings/account values. If the live Eastmoney session is unavailable, the command must exit nonzero with `SECTOR_RANKING_UNAVAILABLE`; do not treat that as a successful live verification.

- [ ] **Step 6: Inspect the generated report**

Verify with `rg` that it contains the required sections and no emoji:

```bash
rg -n "数据时间与完整性|当前最强|正在增强|回踩观察|观察价|触发价|禁追价|失效位|非自动交易" output/sector_rotation_*.md
rg -n "[🚀📊📈✅❌⚠️]" output/sector_rotation_*.md
```

Expected: the first command finds every section; the second produces no output.

- [ ] **Step 7: Commit Task 9**

```bash
git add stock-ai/docs/CAPABILITIES.md stock-ai/investment-agent/docs/skills/stock-strategy-selector/SKILL.md stock-ai/investment-agent/docs/skills/stock-strategy-selector/references/strategy-playbook.md stock-ai/tests/unit/test_sector_rotation_docs.py
git commit -m "docs(stock-ai)：补充板块轮动检测使用说明"
```

### Task 10: Final Evidence and Handoff

**Files:**
- Verify only; do not add unrelated files.

**Interfaces:**
- Produces the final evidence bundle: focused test result, CLI result, report path, migration status, commit list, and known data limitations.

- [ ] **Step 1: Run the complete focused suite fresh**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_sector_rotation_*.py \
  tests/unit/test_detect_sector_rotation_cli.py \
  tests/unit/test_fetch_eastmoney_quotes.py \
  tests/unit/test_buy_point_gates.py -v
```

Expected: exit 0 and zero failures.

- [ ] **Step 2: Verify no existing selection or order integration changed**

Run:

```bash
git diff 5d84f31..HEAD --name-only
rg -n "selection_daily_results|alert_rules|order|下单" stock_ai/sector_rotation scripts/analysis/detect_sector_rotation.py
```

Expected: no modifications to existing selection/order modules; occurrences of order/下单 are only explicit prohibitions in user-facing copy or comments.

- [ ] **Step 3: Verify database and report contracts**

Run:

```bash
rg -n "sector_rotation_runs|sector_rotation_snapshots|sector_rotation_candidates" ../stock-mysql/sql/018_sector_rotation.sql
rg -n "观察价|触发价|禁追价|失效位|最多10只|非自动交易" output/sector_rotation_*.md
```

Expected: all three tables and all report contract terms are present.

- [ ] **Step 4: Record actual evidence in the final handoff**

Report the exact test count, CLI exit status, generated report path, whether migration 018 was applied, and any live-source limitations. Do not claim the live run or MySQL migration succeeded unless the corresponding command output proves it.
