# Stock Diagnosis News Impact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one explainable news-impact service shared by single-stock and MySQL holdings diagnosis, including freshness, deduplication, fixed industry mapping, scoring, risk vetoes, and three-path probability adjustment.

**Architecture:** A pure `stock_ai.news_impact` domain package owns event models, mappings, scoring, probability adjustment, and formatting. Provider adapters read the existing MySQL news pool and an optional standard-event cache; diagnosis entry points receive one immutable result per stock and degrade explicitly when coverage is incomplete.

**Tech Stack:** Python 3.11+, dataclasses, JSON configuration, SQLAlchemy through the existing `portfolio_db.get_engine()`, pytest, OpenCLI-based market collectors.

## Global Constraints

- Overseas market/company events expire after 24 hours; policy/industry events after 3 days; A-share announcements, earnings, and regulatory events after 7 days.
- A single positive event cannot create a buy conclusion or bypass any existing risk gate.
- Verified material negative events may veto new risk but must not block protective reduction or exit of an existing holding.
- Positive aggregate score is capped at `+12`; negative aggregate score is floored at `-20`.
- Rumors receive zero score, and missing news coverage must be disclosed rather than filled with model memory.
- Base, delta, and final strong/neutral/weak probabilities must be visible and final probabilities must total 100.
- Existing user changes and unrelated dirty-worktree files must remain untouched.
- User-visible output must not contain emoji.

---

### Task 1: Domain Models, Freshness, and Deduplication

**Files:**
- Create: `stock-ai/stock_ai/news_impact/__init__.py`
- Create: `stock-ai/stock_ai/news_impact/models.py`
- Create: `stock-ai/stock_ai/news_impact/events.py`
- Test: `stock-ai/tests/unit/test_news_impact_events.py`

**Interfaces:**
- Produces: `NewsEvent`, `StockEventImpact`, `NewsImpactResult`, `ProbabilityPaths` dataclasses.
- Produces: `filter_fresh_events(events, now)` and `deduplicate_events(events)`.

- [ ] **Step 1: Write failing model, freshness, and deduplication tests**

```python
def test_overseas_event_expires_after_24_hours():
    event = make_event(scope="overseas", age_hours=25)
    assert filter_fresh_events([event], now=NOW) == []

def test_duplicate_reprints_keep_best_source():
    low = make_event(event_id="same", source_tier="media")
    official = make_event(event_id="same", source_tier="official")
    assert deduplicate_events([low, official]) == [official]
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_events.py -v`
Expected: FAIL because `stock_ai.news_impact` does not exist.

- [ ] **Step 3: Implement immutable models, expiration defaults, and stable deduplication**

```python
@dataclass(frozen=True)
class NewsEvent:
    event_id: str
    title: str
    summary: str
    published_at: datetime
    observed_at: datetime
    source_url: str
    source_name: str
    source_tier: SourceTier
    market: str
    country: str
    subjects: tuple[str, ...]
    event_type: str
    direction: Direction
    confirmation_state: ConfirmationState
    scope: EventScope
    valid_until: datetime | None = None
    evidence: str = ""
```

- [ ] **Step 4: Run the focused tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_events.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add stock-ai/stock_ai/news_impact stock-ai/tests/unit/test_news_impact_events.py
git commit -m "feat(stock-ai): add news impact event model"
```

### Task 2: Fixed Industry Mapping and Explainable Stock Relevance

**Files:**
- Create: `stock-ai/stock_ai/news_impact/industry_mappings.json`
- Create: `stock-ai/stock_ai/news_impact/mappings.py`
- Test: `stock-ai/tests/unit/test_news_impact_mappings.py`

**Interfaces:**
- Consumes: `NewsEvent` from Task 1.
- Produces: `load_fixed_mappings()`, `infer_event_themes(event)`, and `map_event_to_stock(event, code, name, industry, concepts)`.
- Produces `StockEventImpact` with `transmission_type`, `mapped_sectors`, `relevance`, `confidence`, `mapping_evidence`, and `mapping_source="fixed"`.

- [ ] **Step 1: Write failing fixed-mapping tests for AI cloud, Korean memory, and Japanese semiconductor equipment**

```python
def test_coreweave_maps_lotus_as_industry_demand_not_direct_supplier():
    impact = map_event_to_stock(COREWEAVE_EVENT, "600186", "莲花控股", "食品", ("算力租赁",))
    assert impact.transmission_type == "demand_validation"
    assert impact.relevance == "medium"
    assert "直接供应" not in impact.mapping_evidence
```

- [ ] **Step 2: Run the mapping tests and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_mappings.py -v`
Expected: FAIL because mapping functions and configuration are absent.

- [ ] **Step 3: Add reviewed fixed mappings and deterministic matching**

The JSON configuration must include `ai_cloud`, `ai_server`, `optical_module`, `liquid_cooling`, `data_center_power`, `memory_chip`, `display_panel`, `battery`, `semiconductor_equipment`, `robotics`, `automotive`, `oil`, `gold`, `nonferrous`, `shipping`, `power_grid`, `energy_storage`, `pharma`, and `export_chain`. Each theme contains overseas subjects, keywords, A-share sectors, and optional code/name/concept mappings.

- [ ] **Step 4: Run the focused mapping tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_mappings.py -v`
Expected: PASS, including no false direct-supplier classification.

- [ ] **Step 5: Commit the task**

```bash
git add stock-ai/stock_ai/news_impact/industry_mappings.json stock-ai/stock_ai/news_impact/mappings.py stock-ai/tests/unit/test_news_impact_mappings.py
git commit -m "feat(stock-ai): add fixed overseas industry mappings"
```

### Task 3: Explainable Scoring, Veto, and Probability Adjustment

**Files:**
- Create: `stock-ai/stock_ai/news_impact/scoring.py`
- Create: `stock-ai/stock_ai/news_impact/probability.py`
- Test: `stock-ai/tests/unit/test_news_impact_scoring.py`
- Test: `stock-ai/tests/unit/test_news_impact_probability.py`

**Interfaces:**
- Consumes: `StockEventImpact` and `ProbabilityPaths`.
- Produces: `score_stock_impacts(impacts) -> ScoreBreakdown`.
- Produces: `detect_material_negative_veto(impacts) -> VetoDecision`.
- Produces: `adjust_probabilities(base, score) -> ProbabilityAdjustment`.

- [ ] **Step 1: Write failing tests for coefficients, bounds, rumor zero, diminishing accumulation, veto, and exact probability totals**

```python
def test_rumor_has_zero_weight():
    assert weighted_score(make_impact(source_tier="rumor", base_score=8)) == 0

def test_probability_result_totals_100():
    result = adjust_probabilities(ProbabilityPaths(35, 45, 20), score=6)
    assert sum(result.final.as_tuple()) == 100
    assert 3 <= result.delta.strong <= 6
```

- [ ] **Step 2: Run scoring tests and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_scoring.py tests/unit/test_news_impact_probability.py -v`
Expected: FAIL because the scoring modules are absent.

- [ ] **Step 3: Implement pure scoring and probability functions**

Use source coefficients `1.0/0.8/0.5/0`, confirmation coefficients `1.0/0.5/0`, relevance coefficients `1.0/0.6/0.3/0`, positive cap `12`, negative floor `-20`, and deterministic integer probability deltas within the approved bands.

- [ ] **Step 4: Run scoring and probability tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_scoring.py tests/unit/test_news_impact_probability.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add stock-ai/stock_ai/news_impact/scoring.py stock-ai/stock_ai/news_impact/probability.py stock-ai/tests/unit/test_news_impact_scoring.py stock-ai/tests/unit/test_news_impact_probability.py
git commit -m "feat(stock-ai): score news and adjust path probabilities"
```

### Task 4: MySQL News Provider and Standard Event Cache

**Files:**
- Create: `stock-ai/stock_ai/news_impact/providers.py`
- Create: `stock-ai/scripts/tools/news_impact_db.py`
- Create: `stock-ai/sql/create_news_impact_events.sql`
- Test: `stock-ai/tests/unit/test_news_impact_providers.py`
- Test: `stock-ai/tests/unit/test_news_impact_db.py`

**Interfaces:**
- Produces: `load_macro_news_events(hours, now) -> list[NewsEvent]`.
- Produces: `load_cached_events(since, now)`, `upsert_cached_events(events)`, and `ensure_news_impact_tables()`.
- Provider return type: `NewsCoverage(events, providers_ok, missing_scopes, fetched_at)`.

- [ ] **Step 1: Write failing provider and persistence tests using fake rows and a temporary SQLite engine**

```python
def test_missing_overseas_company_feed_is_disclosed():
    coverage = build_news_coverage(macro_events=[], cached_events=[])
    assert "overseas_company" in coverage.missing_scopes
```

- [ ] **Step 2: Run provider tests and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_providers.py tests/unit/test_news_impact_db.py -v`
Expected: FAIL because provider and cache modules are absent.

- [ ] **Step 3: Implement adapters without direct Eastmoney HTTP calls**

Read `macro_news_items` through the existing SQLAlchemy engine, normalize only rows with parseable time and evidence, and use an idempotent cache table keyed by `event_id`. Preserve raw source fields and serialized subjects/evidence.

- [ ] **Step 4: Run provider and persistence tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_providers.py tests/unit/test_news_impact_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add stock-ai/stock_ai/news_impact/providers.py stock-ai/scripts/tools/news_impact_db.py stock-ai/sql/create_news_impact_events.sql stock-ai/tests/unit/test_news_impact_providers.py stock-ai/tests/unit/test_news_impact_db.py
git commit -m "feat(stock-ai): add news impact providers and cache"
```

### Task 5: Shared Service, Formatting, and Standalone CLI

**Files:**
- Create: `stock-ai/stock_ai/news_impact/service.py`
- Create: `stock-ai/stock_ai/news_impact/formatting.py`
- Create: `stock-ai/scripts/analysis/analyze_news_impact.py`
- Test: `stock-ai/tests/unit/test_news_impact_service.py`
- Test: `stock-ai/tests/unit/test_news_impact_formatting.py`

**Interfaces:**
- Produces: `analyze_stock_news_impact(stock, events, base_probabilities, now, existing_holding) -> NewsImpactResult`.
- Produces: `analyze_portfolio_news_impact(stocks, events, base_probabilities_by_code, now) -> dict[str, NewsImpactResult]`.
- Produces: `format_stock_impact_card(result)` and `format_portfolio_impact_table(results)`.

- [ ] **Step 1: Write failing end-to-end service tests**

```python
def test_single_and_batch_services_return_identical_result():
    single = analyze_stock_news_impact(STOCK, EVENTS, BASE, NOW, True)
    batch = analyze_portfolio_news_impact([STOCK], EVENTS, {STOCK.code: BASE}, NOW)[STOCK.code]
    assert single == batch
```

- [ ] **Step 2: Run service tests and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_service.py tests/unit/test_news_impact_formatting.py -v`
Expected: FAIL because service and formatters are absent.

- [ ] **Step 3: Implement shared orchestration and concise Chinese output**

The formatter displays at most three material events, score/direction/effective window, transmission chain, base/delta/final probabilities, invalidation conditions, data cutoff, sources, and explicit coverage gaps. It contains no emoji.

- [ ] **Step 4: Run service and formatting tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_service.py tests/unit/test_news_impact_formatting.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add stock-ai/stock_ai/news_impact/service.py stock-ai/stock_ai/news_impact/formatting.py stock-ai/scripts/analysis/analyze_news_impact.py stock-ai/tests/unit/test_news_impact_service.py stock-ai/tests/unit/test_news_impact_formatting.py
git commit -m "feat(stock-ai): add shared news impact service"
```

### Task 6: Connect MySQL Holdings Diagnosis

**Files:**
- Modify: `stock-ai/scripts/analysis/analyze_holdings_v2.py`
- Test: `stock-ai/tests/unit/test_analyze_holdings_news_impact.py`

**Interfaces:**
- Consumes: `analyze_portfolio_news_impact()` and `format_portfolio_impact_table()` from Task 5.
- Preserves the existing technical and DeepSeek diagnosis when news providers fail.

- [ ] **Step 1: Write a failing integration test with a fake holdings table and injected news service**

```python
def test_holdings_prompt_contains_shared_news_impact_and_probability_audit():
    prompt = build_combined_prompt(ROW, MARKET, TECH, NEWS_RESULT)
    assert "消息面影响" in prompt
    assert "基础概率" in prompt
    assert "最终概率" in prompt
```

- [ ] **Step 2: Run the integration test and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_analyze_holdings_news_impact.py -v`
Expected: FAIL because the prompt builder and shared news injection do not exist.

- [ ] **Step 3: Extract a testable prompt builder and inject one batched news pass**

Load holdings and news once, compute all stock impacts once, insert the per-stock card into the DeepSeek prompt, and append the portfolio impact table to the Markdown report. On provider failure, insert a coverage warning and keep the original diagnosis running.

- [ ] **Step 4: Run the holdings integration test**

Run: `cd stock-ai && uv run pytest tests/unit/test_analyze_holdings_news_impact.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add stock-ai/scripts/analysis/analyze_holdings_v2.py stock-ai/tests/unit/test_analyze_holdings_news_impact.py
git commit -m "feat(stock-ai): include news impact in holdings diagnosis"
```

### Task 7: Connect Single-Stock Diagnosis Workflow and Korean Indices

**Files:**
- Modify: `stock-ai/investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md`
- Modify: `stock-ai/core_v2/analyze_specific_stocks.py`
- Modify: `stock-ai/scripts/tools/fetch_eastmoney_quotes.py`
- Test: `stock-ai/tests/unit/test_single_stock_news_impact.py`
- Test: `stock-ai/tests/unit/test_fetch_eastmoney_quotes.py`

**Interfaces:**
- Consumes: shared service and formatter from Task 5.
- Extends `INTERNATIONAL_INDEX_SPECS` with KOSPI and KOSDAQ identifiers validated against the OpenCLI source.

- [ ] **Step 1: Write failing tests for the single-stock prompt and Korean index specifications**

```python
def test_single_stock_prompt_uses_shared_news_card():
    prompt = build_single_stock_prompt(STOCK_DATA, NEWS_RESULT)
    assert "消息面影响" in prompt
    assert "海外公司新闻覆盖不足" in prompt

def test_international_specs_include_korean_indices():
    labels = {label for label, _ in INTERNATIONAL_INDEX_SPECS}
    assert {"韩国KOSPI", "韩国KOSDAQ"} <= labels
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `cd stock-ai && uv run pytest tests/unit/test_single_stock_news_impact.py tests/unit/test_fetch_eastmoney_quotes.py -v`
Expected: FAIL because the single-stock prompt lacks news impact and Korean index specs are absent.

- [ ] **Step 3: Inject the shared result and update the SOP contract**

Require every conversational diagnosis to run the standalone/shared service after fresh Eastmoney facts, display the message card, and preserve the three-path audit. Add Korean indices only after confirming the OpenCLI quote identifiers; if unavailable, expose the gap without fabricating values.

- [ ] **Step 4: Run focused and regression tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_single_stock_news_impact.py tests/unit/test_fetch_eastmoney_quotes.py tests/unit/test_news_impact_*.py tests/unit/test_analyze_holdings_news_impact.py -v`
Expected: PASS.

- [ ] **Step 5: Run a manual dry-run without calling the broker**

Run: `cd stock-ai && uv run python scripts/analysis/analyze_news_impact.py --code 600186 --name 莲花控股 --concept 算力租赁 --base 35,45,20`
Expected: A Chinese impact card with source cutoff, coverage status, and probabilities totaling 100; no order is sent.

- [ ] **Step 6: Commit the task**

```bash
git add stock-ai/investment-agent/docs/skills/eastmoney-browser-sop/SKILL.md stock-ai/core_v2/analyze_specific_stocks.py stock-ai/scripts/tools/fetch_eastmoney_quotes.py stock-ai/tests/unit/test_single_stock_news_impact.py stock-ai/tests/unit/test_fetch_eastmoney_quotes.py
git commit -m "feat(stock-ai): connect news impact to single stock diagnosis"
```

### Task 8: Final Verification and Documentation

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md`
- Modify: `stock-ai/investment-agent/memory/2026-08-12.md` if local memory remains available; this file is gitignored and must not be committed.

**Interfaces:**
- Documents the standalone command, supported sources, degradation behavior, and the deferred short-term selection dual-pool decision.

- [ ] **Step 1: Update capability documentation with exact command and limitations**

Document that overseas company coverage depends on cached/verified events, while missing coverage leaves technical diagnosis unchanged.

- [ ] **Step 2: Run the complete relevant test set**

Run: `cd stock-ai && uv run pytest tests/unit/test_news_impact_*.py tests/unit/test_analyze_holdings_news_impact.py tests/unit/test_single_stock_news_impact.py tests/unit/test_fetch_eastmoney_quotes.py -v`
Expected: PASS.

- [ ] **Step 3: Run static and whitespace checks**

Run: `git diff --check`
Expected: no output.

- [ ] **Step 4: Inspect only scoped changes**

Run: `git status --short && git diff --stat HEAD`
Expected: only news-impact implementation, diagnosis integrations, related tests/docs, and pre-existing unrelated user changes.

- [ ] **Step 5: Commit documentation**

```bash
git add stock-ai/docs/CAPABILITIES.md
git commit -m "docs(stock-ai): document diagnosis news impact"
```

