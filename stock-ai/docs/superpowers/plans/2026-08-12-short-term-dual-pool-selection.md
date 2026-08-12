# Short-Term Dual-Pool Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the existing technical selection universe with a fresh, explainable major-news event pool without allowing news alone to create an actionable buy signal.

**Architecture:** A pure `stock_ai.dual_pool_selection` module converts fixed news mappings into event-watch rows and enriches technical rows with bounded news scoring and veto state. `scripts.tools.selection_results` invokes that module after multi-strategy deduplication and before Top5 selection; a standalone CLI persists the enriched technical universe plus the separate `news_event_watch` lane.

**Tech Stack:** Python 3.11+, dataclasses, pandas adapters, existing `stock_ai.news_impact` package, SQLAlchemy persistence through `portfolio_db`, pytest.

## Global Constraints

- Technical signals remain the only source of trading eligibility.
- Positive news may add at most 6 ranking points and may not upgrade `建议动作`.
- Verified official material negatives veto new risk and are excluded from Top5.
- Event-only stocks are labeled `event_watch`, use action `消息观察，等待技术确认`, and are never eligible for actionable Top5.
- Overseas events expire after 24 hours, policy/industry events after 3 days, and A-share events after 7 days.
- News failure or empty coverage preserves the original technical order and values.
- Existing phase, position, holding, action, industry-diversity, and execution-card gates remain in force.
- User-visible output must not contain emoji.
- Unrelated dirty-worktree files must not be touched or staged.

---

### Task 1: Fixed-Mapping Stock Enumeration

**Files:**
- Modify: `stock-ai/stock_ai/news_impact/mappings.py`
- Test: `stock-ai/tests/unit/test_news_impact_mappings.py`

**Interfaces:**
- Consumes: `infer_event_themes(event: NewsEvent) -> list[tuple[str, dict]]`.
- Produces: `MappedStock` and `iter_event_mapped_stocks(event: NewsEvent) -> tuple[MappedStock, ...]`.

- [ ] **Step 1: Write failing tests for paired code/name parsing and duplicate removal**

```python
def test_event_mapped_stocks_are_code_name_pairs_without_duplicates():
    stocks = iter_event_mapped_stocks(COREWEAVE_EVENT)
    lotus = next(item for item in stocks if item.code == "600186")
    assert lotus.name == "莲花控股"
    assert len({item.code for item in stocks}) == len(stocks)
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_mappings.py -v`
Expected: FAIL because `MappedStock` and `iter_event_mapped_stocks` do not exist.

- [ ] **Step 3: Implement strict six-digit code/name pair parsing**

```python
@dataclass(frozen=True)
class MappedStock:
    code: str
    name: str
    theme: str
    sectors: tuple[str, ...]

def iter_event_mapped_stocks(event: NewsEvent) -> tuple[MappedStock, ...]:
    # Only accept a six-digit code followed by a non-code name.
    # Ignore sector-only rules and deduplicate by code.
```

- [ ] **Step 4: Run mapping tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_mappings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the mapping task**

```bash
git add stock-ai/stock_ai/news_impact/mappings.py stock-ai/tests/unit/test_news_impact_mappings.py
git commit -m "feat(stock-ai): enumerate fixed news-mapped stocks"
```

### Task 2: Pure Dual-Pool Merge Domain

**Files:**
- Create: `stock-ai/stock_ai/dual_pool_selection.py`
- Test: `stock-ai/tests/unit/test_dual_pool_selection.py`

**Interfaces:**
- Consumes: `Sequence[Mapping[str, object]]`, `Sequence[NewsEvent]`, `now: datetime`, and `coverage_status: str`.
- Produces: `DualPoolResult(technical_rows, event_watch_rows)` and `merge_dual_pool_rows(...) -> DualPoolResult`.

- [ ] **Step 1: Write failing tests for overlap, cap, event-only watch, veto, and no-news degradation**

```python
def test_positive_news_enriches_but_does_not_upgrade_action():
    result = merge_dual_pool_rows([TECH_LOTUS], [COREWEAVE_EVENT], now=NOW)
    row = result.technical_rows[0]
    assert row["候选池来源"] == "both"
    assert row["建议动作"] == TECH_LOTUS["建议动作"]
    assert 0 < row["总分"] - row["技术原始分"] <= 6

def test_event_only_stock_is_watch_not_buy():
    result = merge_dual_pool_rows([], [COREWEAVE_EVENT], now=NOW)
    assert all(row["候选池来源"] == "event_watch" for row in result.event_watch_rows)
    assert all(row["建议动作"] == "消息观察，等待技术确认" for row in result.event_watch_rows)

def test_official_material_negative_vetoes_new_risk():
    result = merge_dual_pool_rows([TECH_LOTUS], [OFFICIAL_NEGATIVE], now=NOW)
    assert result.technical_rows[0]["候选池来源"] == "vetoed"

def test_empty_news_preserves_scores_and_order():
    result = merge_dual_pool_rows(TECH_ROWS, [], now=NOW, coverage_status="不足")
    assert [row["总分"] for row in result.technical_rows] == [row["总分"] for row in TECH_ROWS]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_dual_pool_selection.py -v`
Expected: FAIL because `stock_ai.dual_pool_selection` does not exist.

- [ ] **Step 3: Implement immutable result and deterministic row enrichment**

```python
@dataclass(frozen=True)
class DualPoolResult:
    technical_rows: tuple[dict[str, object], ...]
    event_watch_rows: tuple[dict[str, object], ...]

def merge_dual_pool_rows(
    technical_rows: Sequence[Mapping[str, object]],
    events: Sequence[NewsEvent],
    *,
    now: datetime,
    coverage_status: str = "完整",
) -> DualPoolResult:
    # Filter/deduplicate events, score existing rows through analyze_stock_news_impact,
    # clamp score * 0.5, preserve action, attach evidence fields, and build separate watches.
```

- [ ] **Step 4: Run dual-pool tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_dual_pool_selection.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the domain task**

```bash
git add stock-ai/stock_ai/dual_pool_selection.py stock-ai/tests/unit/test_dual_pool_selection.py
git commit -m "feat(stock-ai): merge technical and news candidate pools"
```

### Task 3: Selection Pipeline and Top5 Integration

**Files:**
- Modify: `stock-ai/scripts/tools/selection_results.py`
- Modify: `stock-ai/tests/unit/test_wechat_top5_selection.py`

**Interfaces:**
- Adds optional keyword arguments `include_news: bool = True`, `news_events: Sequence[NewsEvent] | None = None`, and `now: datetime | None = None` to `merge_selection_strategies_df`.
- Preserves its return contract `(trade_date, DataFrame, source)`.
- Excludes rows whose `候选池来源` is `event_watch` or `vetoed` inside `pick_selection_top`.

- [ ] **Step 1: Write failing integration tests**

```python
def test_merge_applies_news_before_top5_ranking():
    _, frame, source = merge_selection_strategies_df(
        trade_date=DATE,
        strategies=("combined",),
        news_events=[COREWEAVE_EVENT],
        now=NOW,
    )
    assert "dual-pool" in source
    assert "消息影响分" in frame.columns

def test_top5_excludes_event_watch_and_vetoed_rows():
    top = pick_selection_top(FRAME_WITH_ALL_POOL_STATES, top_n=5, eligible_actions=None)
    assert set(top["候选池来源"]) <= {"technical", "both"}
```

- [ ] **Step 2: Run integration tests and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_top5_selection.py -v`
Expected: FAIL because merge arguments and pool-state filtering are absent.

- [ ] **Step 3: Load coverage once, invoke the pure merger, and keep backward compatibility**

```python
if include_news:
    coverage = supplied_events or load_news_coverage(engine=engine, now=resolved_now)
    dual = merge_dual_pool_rows(out_df.to_dict("records"), coverage.events, now=resolved_now)
    out_df = pd.DataFrame(dual.technical_rows)
```

When `include_news=False`, return the current exact behavior. Provider exceptions must return the technical frame with `消息覆盖状态=不足`, not fail the selection call.

- [ ] **Step 4: Run existing and new selection tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_top5_selection.py tests/unit/test_enrich_unified_top5.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the pipeline task**

```bash
git add stock-ai/scripts/tools/selection_results.py stock-ai/tests/unit/test_wechat_top5_selection.py
git commit -m "feat(stock-ai): rank Top5 with dual-pool news context"
```

### Task 4: CLI, Persistence, and End-to-End Verification

**Files:**
- Create: `stock-ai/scripts/analysis/merge_dual_pool_selection.py`
- Create: `stock-ai/tests/unit/test_merge_dual_pool_selection_cli.py`
- Modify: `stock-ai/investment-agent/docs/skills/stock-strategy-selector/references/strategy-playbook.md`

**Interfaces:**
- CLI arguments: `--date YYYYMMDD`, `--top N`, `--no-db`, and `--output PATH`.
- Reads the existing multi-strategy universe, loads news coverage once, calls `merge_dual_pool_rows`, writes enriched CSV, and unless `--no-db` saves `news_event_watch` through `save_selection_daily_results`.

- [ ] **Step 1: Write a failing CLI orchestration test with patched data loaders**

```python
def test_cli_writes_enriched_csv_and_event_watch_lane(tmp_path, monkeypatch):
    # Patch selection rows, coverage, and DB save; run main([...]).
    assert output_csv.exists()
    assert saved_strategy == "news_event_watch"
    assert all(row["建议动作"] == "消息观察，等待技术确认" for row in saved_rows)
```

- [ ] **Step 2: Run the CLI test and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_merge_dual_pool_selection_cli.py -v`
Expected: FAIL because the CLI module does not exist.

- [ ] **Step 3: Implement the CLI and add the operating command to the playbook**

```bash
uv run python -m scripts.analysis.merge_dual_pool_selection --date YYYYMMDD --top 5
```

The command must print counts for technical-only, both, vetoed, and event-watch rows, the news cutoff time, output CSV path, and MySQL row count. Output text contains no emoji.

- [ ] **Step 4: Run focused and regression verification**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_mappings.py tests/unit/test_dual_pool_selection.py tests/unit/test_wechat_top5_selection.py tests/unit/test_enrich_unified_top5.py tests/unit/test_merge_dual_pool_selection_cli.py -v`
Expected: PASS.

Run: `cd stock-ai && uv run python -m compileall -q stock_ai/dual_pool_selection.py stock_ai/news_impact scripts/tools/selection_results.py scripts/analysis/merge_dual_pool_selection.py`
Expected: exit code 0.

- [ ] **Step 5: Run a MySQL-backed dry run without writes**

Run: `cd stock-ai && uv run python -m scripts.analysis.merge_dual_pool_selection --no-db`
Expected: exits 0; prints the latest selection date, pool counts, cutoff, and CSV path; event-only rows remain non-actionable.

- [ ] **Step 6: Commit the CLI and documentation task**

```bash
git add stock-ai/scripts/analysis/merge_dual_pool_selection.py stock-ai/tests/unit/test_merge_dual_pool_selection_cli.py stock-ai/investment-agent/docs/skills/stock-strategy-selector/references/strategy-playbook.md
git commit -m "feat(stock-ai): operate dual-pool short-term selection"
```
