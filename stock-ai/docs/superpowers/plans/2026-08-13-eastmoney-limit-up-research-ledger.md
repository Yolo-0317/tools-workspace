# Eastmoney Limit-Up Research Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an idempotent, manually triggered ledger that stores Eastmoney limit-up facts, deterministic selection attribution, and T+1/T+3/T+5 outcomes without changing formal Top5 selection.

**Architecture:** A pure `stock_ai.limit_up_research` package normalizes Eastmoney payloads, attributes persisted selection outcomes, computes forward labels, and renders reports. `portfolio_db.py` exposes the MySQL transaction boundary backed by four tables owned by `stock-mysql`; one CLI orchestrates collection, persistence, label backfill, and report generation.

**Tech Stack:** Python 3.11, dataclasses, pandas, SQLAlchemy, MySQL 8, OpenCLI Eastmoney topic-pool collector, pytest.

## Global Constraints

- The workflow is manually triggered only; do not add cron, launchd, Docker scheduler, or host-job routes.
- Eastmoney OpenCLI is the sole source for pool facts; MySQL/Tushare may validate dates and compute forward labels but may not impersonate Eastmoney facts.
- Do not import or invoke the deprecated Eastmoney eight-dimension diagnosis.
- Attribution reason codes and evidence are deterministic and versioned; AI may not create or overwrite them.
- Repeated runs are idempotent for facts, attributions, labels, and report paths while every invocation retains a run audit row.
- The ledger cannot alter strategy parameters, promotion artifacts, holdings, advisor decisions, or `wechat_top5_strategies()`.
- Preserve unrelated worktree changes and do not commit `.env`, brokerage positions, or personal memory.

---

## File Map

- Create `stock-mysql/sql/014_limit_up_research.sql`: four ledger tables and indexes.
- Create `stock-ai/stock_ai/limit_up_research/__init__.py`: public exports.
- Create `stock-ai/stock_ai/limit_up_research/models.py`: normalized facts, stable hashing, validation.
- Create `stock-ai/stock_ai/limit_up_research/attribution.py`: persisted-result matching and versioned explain adapters.
- Create `stock-ai/stock_ai/limit_up_research/labels.py`: trading-session horizon resolution and outcome metrics.
- Create `stock-ai/stock_ai/limit_up_research/report.py`: deterministic Markdown/JSON payload construction.
- Modify `stock-ai/scripts/tools/portfolio_db.py`: audit and bundle persistence/read interfaces.
- Create `stock-ai/scripts/analysis/sync_limit_up_research.py`: the sole manual orchestration CLI.
- Create focused tests under `stock-ai/tests/unit/` and one guarded live integration test under `stock-ai/tests/integration/`.
- Modify `stock-ai/docs/CAPABILITIES.md`: document the manual command and isolation guarantees.

---

### Task 1: Add the research ledger migration

**Files:**
- Create: `stock-mysql/sql/014_limit_up_research.sql`
- Test: `stock-ai/tests/unit/test_limit_up_research_schema.py`

**Interfaces:**
- Produces tables `limit_up_research_runs`, `limit_up_research_pool`, `limit_up_selection_attribution`, and `limit_up_forward_labels`.
- Produces unique keys `(trade_date, pool_kind, ts_code)`, `(trade_date, ts_code, strategy)`, and `(signal_date, ts_code, horizon)`.

- [ ] **Step 1: Write a failing schema contract test**

```python
from pathlib import Path


SQL = Path(__file__).parents[3] / "stock-mysql/sql/014_limit_up_research.sql"


def test_limit_up_research_schema_declares_four_idempotent_tables() -> None:
    text = SQL.read_text(encoding="utf-8")
    for table in (
        "limit_up_research_runs",
        "limit_up_research_pool",
        "limit_up_selection_attribution",
        "limit_up_forward_labels",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    assert "UNIQUE KEY uk_pool_fact (trade_date, pool_kind, ts_code)" in text
    assert "UNIQUE KEY uk_attribution (trade_date, ts_code, strategy)" in text
    assert "PRIMARY KEY (signal_date, ts_code, horizon)" in text
```

- [ ] **Step 2: Run the test and verify the missing migration failure**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_schema.py -q`

Expected: FAIL because `014_limit_up_research.sql` does not exist.

- [ ] **Step 3: Add exact MySQL 8 DDL**

The migration uses `InnoDB`, `utf8mb4_unicode_ci`, JSON columns for raw evidence, foreign keys from the pool and attribution snapshots to `limit_up_research_runs(run_id)`, and enums represented as bounded `VARCHAR` plus `CHECK` clauses. `limit_up_research_runs` uses `BIGINT AUTO_INCREMENT`; timestamps use `DATETIME(6)`; money and percentage values use `DECIMAL` rather than float.

```sql
CREATE TABLE IF NOT EXISTS limit_up_research_runs (
    run_id BIGINT NOT NULL AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL,
    source VARCHAR(64) NOT NULL,
    snapshot_hash CHAR(64) DEFAULT NULL,
    limit_up_count INT DEFAULT NULL,
    exploded_count INT DEFAULT NULL,
    limit_down_count INT DEFAULT NULL,
    missing_fields_json JSON NOT NULL,
    error_code VARCHAR(64) DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    raw_meta_json JSON NOT NULL,
    started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) DEFAULT NULL,
    PRIMARY KEY (run_id),
    INDEX idx_limit_up_run_date (trade_date, status),
    INDEX idx_limit_up_snapshot (trade_date, snapshot_hash),
    CHECK (status IN ('STARTED', 'SUCCEEDED', 'FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS limit_up_research_pool (
    id BIGINT NOT NULL AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    pool_kind VARCHAR(16) NOT NULL,
    ts_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    pct_chg DECIMAL(10,4) DEFAULT NULL,
    amount_wan DECIMAL(18,2) DEFAULT NULL,
    board_height INT DEFAULT NULL,
    main_theme VARCHAR(128) DEFAULT NULL,
    first_seal_time VARCHAR(16) DEFAULT NULL,
    last_seal_time VARCHAR(16) DEFAULT NULL,
    reopen_count INT DEFAULT NULL,
    seal_amount_wan DECIMAL(18,2) DEFAULT NULL,
    missing_fields_json JSON NOT NULL,
    source_run_id BIGINT NOT NULL,
    raw_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_pool_fact (trade_date, pool_kind, ts_code),
    INDEX idx_pool_ladder (trade_date, pool_kind, board_height),
    CONSTRAINT fk_limit_up_pool_run FOREIGN KEY (source_run_id)
      REFERENCES limit_up_research_runs(run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS limit_up_selection_attribution (
    id BIGINT NOT NULL AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(10) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    selected TINYINT(1) NOT NULL DEFAULT 0,
    rank_no INT DEFAULT NULL,
    score DECIMAL(12,4) DEFAULT NULL,
    action VARCHAR(64) DEFAULT NULL,
    attribution VARCHAR(32) NOT NULL,
    first_reason_code VARCHAR(64) DEFAULT NULL,
    reason_codes_json JSON NOT NULL,
    evidence_json JSON NOT NULL,
    rule_version VARCHAR(64) NOT NULL,
    source_run_id BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_attribution (trade_date, ts_code, strategy),
    INDEX idx_attribution_reason (trade_date, strategy, attribution),
    CONSTRAINT fk_limit_up_attribution_run FOREIGN KEY (source_run_id)
      REFERENCES limit_up_research_runs(run_id),
    CHECK (attribution IN (
      'SELECTED', 'RANKED_OUT', 'HARD_REJECTED', 'DATA_MISSING',
      'EXPLAINER_UNAVAILABLE', 'STRATEGY_NOT_RUN'
    ))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS limit_up_forward_labels (
    signal_date DATE NOT NULL,
    ts_code VARCHAR(10) NOT NULL,
    horizon VARCHAR(4) NOT NULL,
    outcome_date DATE DEFAULT NULL,
    signal_close DECIMAL(16,4) DEFAULT NULL,
    outcome_close DECIMAL(16,4) DEFAULT NULL,
    close_return_pct DECIMAL(12,4) DEFAULT NULL,
    max_return_pct DECIMAL(12,4) DEFAULT NULL,
    max_drawdown_pct DECIMAL(12,4) DEFAULT NULL,
    closed_limit_up TINYINT(1) DEFAULT NULL,
    board_height INT DEFAULT NULL,
    data_complete TINYINT(1) NOT NULL DEFAULT 0,
    missing_fields_json JSON NOT NULL,
    label_version VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (signal_date, ts_code, horizon),
    INDEX idx_forward_outcome (outcome_date, horizon),
    CHECK (horizon IN ('T1', 'T3', 'T5'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

- [ ] **Step 4: Run the schema contract test**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_schema.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the migration**

```bash
git add stock-mysql/sql/014_limit_up_research.sql stock-ai/tests/unit/test_limit_up_research_schema.py
git commit -m "feat(stock-mysql): add limit-up research ledger"
```

---

### Task 2: Normalize and validate Eastmoney pool facts

**Files:**
- Create: `stock-ai/stock_ai/limit_up_research/__init__.py`
- Create: `stock-ai/stock_ai/limit_up_research/models.py`
- Create: `stock-ai/tests/unit/test_limit_up_research_models.py`

**Interfaces:**
- Produces `PoolFact`, `NormalizedSnapshot`, `SelectionAttribution`, `ForwardLabel`, `normalize_topic_pools(pools, trade_date)`, and `snapshot_hash(facts)`.
- Consumes raw keys already returned by `fetch_emotion_topic_pools_opencli`: `c`, `n`, `zdp`, `amount`, `lbc`, `zttj`, `hybk`, `fbt`, `lbt`, `zbc`, and `fund`.

- [ ] **Step 1: Write failing normalization tests**

```python
from datetime import date

import pytest

from stock_ai.limit_up_research.models import normalize_topic_pools


def test_normalize_limit_up_fact_preserves_raw_and_board_height() -> None:
    pools = {
        "zt": [{"c": "601991", "n": "大唐发电", "zdp": 10.02,
                "amount": 812000000, "lbc": 2, "hybk": "电力行业",
                "fbt": "093125", "lbt": "145702", "zbc": 1,
                "fund": 92500000}],
        "zb": [],
        "dt": [],
    }
    result = normalize_topic_pools(pools, date(2026, 8, 13))
    fact = result.facts[0]
    assert (fact.pool_kind, fact.code, fact.board_height) == ("LIMIT_UP", "601991", 2)
    assert fact.amount_wan == 81200.0
    assert fact.first_seal_time == "09:31:25"
    assert fact.raw_json["c"] == "601991"


def test_normalization_rejects_missing_pool_or_invalid_code() -> None:
    with pytest.raises(ValueError, match="missing topic pool"):
        normalize_topic_pools({"zt": [], "zb": []}, date(2026, 8, 13))
    with pytest.raises(ValueError, match="invalid A-share code"):
        normalize_topic_pools(
            {"zt": [{"c": "bad", "n": "坏数据"}], "zb": [], "dt": []},
            date(2026, 8, 13),
        )
```

- [ ] **Step 2: Run tests and verify import failure**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_models.py -q`

Expected: FAIL because the package is missing.

- [ ] **Step 3: Implement immutable models and normalization**

```python
@dataclass(frozen=True)
class PoolFact:
    trade_date: date
    pool_kind: Literal["LIMIT_UP", "EXPLODED", "LIMIT_DOWN"]
    code: str
    name: str
    pct_chg: float | None
    amount_wan: float | None
    board_height: int | None
    main_theme: str | None
    first_seal_time: str | None
    last_seal_time: str | None
    reopen_count: int | None
    seal_amount_wan: float | None
    missing_fields: tuple[str, ...]
    raw_json: Mapping[str, Any]


@dataclass(frozen=True)
class NormalizedSnapshot:
    trade_date: date
    facts: tuple[PoolFact, ...]
    warnings: tuple[str, ...]
    snapshot_hash: str


@dataclass(frozen=True)
class SelectionAttribution:
    trade_date: date
    code: str
    strategy: str
    selected: bool
    rank_no: int | None
    score: float | None
    action: str | None
    attribution: str
    first_reason_code: str | None
    reason_codes: tuple[str, ...]
    evidence: Mapping[str, Any]
    rule_version: str


@dataclass(frozen=True)
class ForwardLabel:
    signal_date: date
    code: str
    horizon: Literal["T1", "T3", "T5"]
    outcome_date: date | None
    signal_close: float | None
    outcome_close: float | None
    close_return_pct: float | None
    max_return_pct: float | None
    max_drawdown_pct: float | None
    closed_limit_up: bool | None
    board_height: int | None
    data_complete: bool
    missing_fields: tuple[str, ...]
    label_version: str = "limit-up-forward-label-1.0.0"
```

Normalize time values to `HH:MM:SS`, convert Eastmoney yuan amounts to ten-thousand yuan, recover `board_height` from `zttj.ct` or `zttj.days` when `lbc` is absent, sort by `(pool_kind, code)`, deduplicate identical facts, and reject conflicting duplicates. Hash canonical JSON with sorted keys and compact separators.

- [ ] **Step 4: Add missing-field and stable-hash cases**

Add tests proving absent optional values are `None` and listed in `missing_fields`; zero `zbc` remains zero; input order does not change `snapshot_hash`; the same stock may exist in different pool kinds without collision.

- [ ] **Step 5: Run model tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_models.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the pure model**

```bash
git add stock-ai/stock_ai/limit_up_research stock-ai/tests/unit/test_limit_up_research_models.py
git commit -m "feat(stock-ai): normalize Eastmoney limit-up pools"
```

---

### Task 3: Add transactional persistence and audit APIs

**Files:**
- Modify: `stock-ai/scripts/tools/portfolio_db.py`
- Create: `stock-ai/tests/unit/test_limit_up_research_db.py`
- Create: `stock-ai/tests/integration/test_limit_up_research_mysql.py`

**Interfaces:**
- Consumes `PoolFact`, `SelectionAttribution`, and `ForwardLabel` dataclasses.
- Produces:
  - `start_limit_up_research_run(trade_date, *, source, engine=None) -> int`
  - `finish_limit_up_research_run(run_id, *, status, snapshot_hash=None, counts=None, error=None, engine=None) -> None`
  - `save_limit_up_research_bundle(run_id, trade_date, facts, attributions, labels, *, engine=None) -> dict[str, int]`
  - `load_limit_up_pool(trade_date, *, pool_kind=None, engine=None) -> list[dict[str, Any]]`
  - `load_limit_up_research_bundle(trade_date, *, engine=None) -> dict[str, Any]`

- [ ] **Step 1: Write failing transaction-boundary tests**

Use a recording fake engine whose `begin()` context records SQL and parameters. Assert that `save_limit_up_research_bundle` executes pool, attribution, and label upserts inside one `begin()` context and never calls `commit()` directly. Assert `start_limit_up_research_run` returns the inserted primary key and `finish_limit_up_research_run` refuses a status outside `SUCCEEDED|FAILED`.

- [ ] **Step 2: Run the persistence unit tests and verify missing API failures**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_db.py -q`

Expected: FAIL because the persistence functions do not exist.

- [ ] **Step 3: Implement audit writes and MySQL upserts**

Use `INSERT ... ON DUPLICATE KEY UPDATE` for the three idempotent tables. Store tuples and mappings with `json.dumps(..., ensure_ascii=False, sort_keys=True)`. Never delete a successful snapshot before replacement. Validate the supplied `run_id`, six-digit code, pool kind, attribution, and horizon before opening the transaction.

```python
def save_limit_up_research_bundle(
    run_id: int,
    trade_date: date,
    facts: Sequence[PoolFact],
    attributions: Sequence[SelectionAttribution],
    labels: Sequence[ForwardLabel],
    *,
    engine: Engine | None = None,
) -> dict[str, int]:
    eng = engine or get_engine()
    if eng is None:
        raise RuntimeError("未配置 MYSQL_URL，无法写入涨停研究账本")
    with eng.begin() as conn:
        pool_count = _upsert_limit_up_pool(conn, run_id, trade_date, facts)
        attribution_count = _upsert_limit_up_attributions(conn, run_id, trade_date, attributions)
        label_count = _upsert_limit_up_labels(conn, labels)
    return {"pool": pool_count, "attributions": attribution_count, "labels": label_count}
```

- [ ] **Step 4: Add guarded live MySQL integration coverage**

The integration test skips unless `RUN_MYSQL_INTEGRATION=1`. It creates a unique historical fixture date, starts a run, writes one fact/attribution/label twice, asserts one row per unique key, then deletes only rows linked to its `run_id`. It must not truncate tables or use production dates.

- [ ] **Step 5: Run persistence unit tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_db.py -q`

Expected: PASS.

- [ ] **Step 6: Commit persistence APIs**

```bash
git add stock-ai/scripts/tools/portfolio_db.py stock-ai/tests/unit/test_limit_up_research_db.py stock-ai/tests/integration/test_limit_up_research_mysql.py
git commit -m "feat(stock-ai): persist limit-up research ledger"
```

---

### Task 4: Build deterministic selection attribution

**Files:**
- Create: `stock-ai/stock_ai/limit_up_research/attribution.py`
- Modify: `stock-ai/stock_ai/limit_up_research/__init__.py`
- Create: `stock-ai/tests/unit/test_limit_up_research_attribution.py`

**Interfaces:**
- Consumes `SelectionAttribution` from `models.py`.
- Produces `StrategySnapshot`, `ExplainResult`, `build_selection_attributions(...)`, and `STRATEGY_RULE_VERSIONS`.
- Consumes all `LIMIT_UP` facts, exact-date rows from `load_selection_daily_results`, and optional deterministic explain callbacks.

- [ ] **Step 1: Write failing attribution-state tests**

```python
def test_persisted_candidate_is_selected_with_original_rank_and_score() -> None:
    result = build_selection_attributions(
        trade_date=DATE,
        limit_up_codes=("601991",),
        snapshots={"combined": StrategySnapshot(ran=True, rows=(
            {"代码": "601991", "总分": 78, "建议动作": "强势关注"},
        ))},
        explainers={},
    )
    assert result[0].attribution == "SELECTED"
    assert (result[0].rank_no, result[0].score) == (1, 78.0)


def test_missing_lane_and_missing_explainer_are_not_hard_rejections() -> None:
    rows = build_selection_attributions(
        trade_date=DATE,
        limit_up_codes=("601991",),
        snapshots={
            "combined": StrategySnapshot(ran=False, rows=()),
            "five_factor": StrategySnapshot(ran=True, rows=()),
        },
        explainers={},
    )
    assert [row.attribution for row in rows] == [
        "STRATEGY_NOT_RUN",
        "EXPLAINER_UNAVAILABLE",
    ]
```

- [ ] **Step 2: Run tests and verify import failure**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_attribution.py -q`

Expected: FAIL because attribution types are missing.

- [ ] **Step 3: Implement the state resolver**

```python
AttributionCode = Literal[
    "SELECTED", "RANKED_OUT", "HARD_REJECTED", "DATA_MISSING",
    "EXPLAINER_UNAVAILABLE", "STRATEGY_NOT_RUN",
]


@dataclass(frozen=True)
class ExplainResult:
    attribution: Literal["HARD_REJECTED", "DATA_MISSING"]
    reason_codes: tuple[str, ...]
    evidence: Mapping[str, Any]
    rule_version: str
```

Use the original persisted row order as rank. Treat the sentinel row with code `000000` and `raw_json._lane_completed=true` as proof that a zero-candidate lane ran. Never infer `HARD_REJECTED` without an `ExplainResult`.

- [ ] **Step 4: Add versioned explain adapters**

Register all seven current lanes in `STRATEGY_RULE_VERSIONS`. Implement a real adapter for `limit_up_gene_watch` using `analyze_limit_up_logic` plus `PRECISION_POLICY`, returning ordered codes such as `BASE_FILTER_FAILED`, `GENE_NOT_STRONG`, `NO_RECENT_LIMIT_UP`, `SUPPORT_BROKEN`, `CONTINUATION_TOO_LOW`, `FAILURE_TOO_HIGH`, `RISK_VETO`, `NOT_NEAR_BOX_CEILING`, and `NOT_MATURE_CONSOLIDATION`. For lanes without a safe rejection trace, register metadata but no callback so the state is explicitly `EXPLAINER_UNAVAILABLE`.

- [ ] **Step 5: Verify no future data and no AI dependency**

Add a test callback that records the maximum input bar date and assert it never exceeds `trade_date`. Inspect `sys.modules` after importing the package and assert `scripts.analysis.eastmoney_sop_extract` is absent. Assert source rows cannot pass an arbitrary natural-language rejection string as a reason code.

- [ ] **Step 6: Run attribution tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_attribution.py tests/unit/test_limit_up_gene_watch.py -q`

Expected: PASS.

- [ ] **Step 7: Commit attribution**

```bash
git add stock-ai/stock_ai/limit_up_research stock-ai/tests/unit/test_limit_up_research_attribution.py
git commit -m "feat(stock-ai): attribute limit-up selection misses"
```

---

### Task 5: Compute T+1, T+3, and T+5 forward labels

**Files:**
- Create: `stock-ai/stock_ai/limit_up_research/labels.py`
- Modify: `stock-ai/stock_ai/limit_up_research/__init__.py`
- Create: `stock-ai/tests/unit/test_limit_up_research_labels.py`

**Interfaces:**
- Consumes `ForwardLabel` from `models.py`.
- Produces `compute_forward_labels(signal_date, code, bars, market_dates) -> tuple[ForwardLabel, ...]`.
- Consumes date-ordered daily bars with `trade_date`, `close`, `high`, `low`, and `pct_chg`.

- [ ] **Step 1: Write failing session-horizon tests**

Create literal bars spanning a Friday signal and the next five trading sessions. Assert T1 uses Monday rather than Saturday, T3 uses Wednesday, T5 uses Friday, and returns are based on the signal close. Add a suspended-code fixture missing T3 and assert T3 has `data_complete=False` without substituting T4.

- [ ] **Step 2: Run tests and verify import failure**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_labels.py -q`

Expected: FAIL because label computation is missing.

- [ ] **Step 3: Implement exact label math**

Resolve target dates from the full market session list. Return the exact `ForwardLabel` type defined in Task 2. Compute maximum high return and minimum low return across T+1 through the target horizon. Determine `closed_limit_up` with the existing board-aware `limit_up_threshold`; compute consecutive board height from actual adjacent code bars only.

- [ ] **Step 4: Add not-due and invalid-price cases**

Assert no label is emitted for a horizon whose market session is not yet available. Assert a non-positive signal close produces an incomplete label with `INVALID_SIGNAL_CLOSE` rather than a division error.

- [ ] **Step 5: Run label tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_labels.py -q`

Expected: PASS.

- [ ] **Step 6: Commit labels**

```bash
git add stock-ai/stock_ai/limit_up_research stock-ai/tests/unit/test_limit_up_research_labels.py
git commit -m "feat(stock-ai): label limit-up forward outcomes"
```

---

### Task 6: Build the deterministic report and manual CLI

**Files:**
- Create: `stock-ai/stock_ai/limit_up_research/report.py`
- Create: `stock-ai/scripts/analysis/sync_limit_up_research.py`
- Modify: `stock-ai/stock_ai/limit_up_research/__init__.py`
- Create: `stock-ai/tests/unit/test_limit_up_research_report.py`
- Create: `stock-ai/tests/unit/test_sync_limit_up_research.py`

**Interfaces:**
- Produces `build_research_report(bundle) -> tuple[dict[str, Any], str]` and CLI `main(argv: list[str] | None = None) -> int`.
- Consumes the existing `fetch_emotion_topic_pools_opencli`, normalization, DB APIs, attribution, and label computation.

- [ ] **Step 1: Write a failing report contract test**

Build a literal bundle with one first board, one second board, one exploded stock, two attribution states, and one completed T1 label. Assert JSON counters, ladder grouping, strategy coverage, reason aggregation, `source`, `run_id`, and `data_cutoff`; assert Markdown contains no buy action or position instruction.

- [ ] **Step 2: Write failing CLI orchestration tests**

Inject collector and repository callables into `run_pipeline(...)`. Assert call order is `start -> collect -> normalize -> load selections -> attribute -> labels -> save -> finish -> report`. Make collection raise and assert `finish(... status="FAILED")`, no bundle save, no report write, and return code 1.

- [ ] **Step 3: Run report and CLI tests and verify import failures**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_report.py tests/unit/test_sync_limit_up_research.py -q`

Expected: FAIL because report and CLI modules are missing.

- [ ] **Step 4: Implement deterministic report construction**

The JSON structure must contain `schema_version`, `run_id`, `trade_date`, `source`, `data_cutoff`, `counts`, `board_ladder`, `themes`, `strategy_coverage`, `miss_reasons`, `pool_rows`, `attributions`, `label_backfill`, and `missing_fields`. Markdown renders these values without calling any LLM.

- [ ] **Step 5: Implement the manual pipeline**

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="东财涨停研究账本手动采集与复盘")
    parser.add_argument("--date", help="已收盘交易日 YYYY-MM-DD；默认最近已收盘交易日")
    parser.add_argument(
        "--output-dir",
        default="output/research/limit_up",
        help="Markdown/JSON 复盘目录",
    )
    args = parser.parse_args(argv)
    try:
        result = run_pipeline(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0
```

Resolve the default date only after 15:00 Asia/Shanghai; before close select the previous complete trade date. Write reports through temporary sibling files followed by `Path.replace()` so reruns atomically replace the same date paths.

- [ ] **Step 6: Add safety tests**

Patch `wechat_top5_strategies()` before and after a successful fake run and assert equality. Patch the deprecated SOP extractor to raise if imported and assert it is never touched. Assert the CLI source tree has no scheduler installer change and no network fallback other than `fetch_emotion_topic_pools_opencli`.

- [ ] **Step 7: Run CLI and report tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest tests/unit/test_limit_up_research_report.py tests/unit/test_sync_limit_up_research.py tests/unit/test_selection_results.py -q`

Expected: PASS.

- [ ] **Step 8: Commit the manual workflow**

```bash
git add stock-ai/stock_ai/limit_up_research stock-ai/scripts/analysis/sync_limit_up_research.py stock-ai/tests/unit/test_limit_up_research_report.py stock-ai/tests/unit/test_sync_limit_up_research.py
git commit -m "feat(stock-ai): add manual limit-up research workflow"
```

---

### Task 7: Document, migrate, and verify end to end

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md`
- Modify: `stock-mysql/README.md`
- Runtime only example: `stock-ai/output/research/limit_up/2026-08-12.md`
- Runtime only example: `stock-ai/output/research/limit_up/2026-08-12.json`

**Interfaces:**
- Consumes all previous tasks.
- Produces an applied schema, one real manually triggered ledger snapshot, and verification evidence.

- [ ] **Step 1: Document the exact command and guarantees**

Add a “东财涨停研究账本” section containing the manual command, four tables, data-source rule, idempotency, failure behavior, T+1/T+3/T+5 semantics, and the statement that it cannot enable Top5.

- [ ] **Step 2: Run the complete offline test suite for this feature**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_limit_up_research_schema.py \
  tests/unit/test_limit_up_research_models.py \
  tests/unit/test_limit_up_research_db.py \
  tests/unit/test_limit_up_research_attribution.py \
  tests/unit/test_limit_up_research_labels.py \
  tests/unit/test_limit_up_research_report.py \
  tests/unit/test_sync_limit_up_research.py \
  tests/unit/test_selection_results.py -q
```

Expected: all pass with zero failures.

- [ ] **Step 3: Apply the migration with the existing idempotent initializer**

Run: `cd stock-mysql && bash scripts/init-db.sh`

Expected: exit 0 and all four tables present. This requires explicit approval because it mutates MySQL schema.

- [ ] **Step 4: Run the guarded MySQL integration test**

Run: `cd stock-ai && RUN_MYSQL_INTEGRATION=1 PYTHONPATH=. .venv/bin/pytest tests/integration/test_limit_up_research_mysql.py -q`

Expected: PASS and fixture rows removed by targeted cleanup.

- [ ] **Step 5: Execute one real manual snapshot**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m scripts.analysis.sync_limit_up_research --date 2026-08-12`

Expected: JSON with `ok=true`, non-zero `run_id`, pool counts, attribution counts, label backfill count, and both report paths. This requires explicit approval for OpenCLI browser control and MySQL writes.

- [ ] **Step 6: Verify database/report parity and Top5 isolation**

Read the saved bundle and report JSON, assert counts match, inspect at least one `SELECTED`, `HARD_REJECTED` when available, and `EXPLAINER_UNAVAILABLE`, then run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -c \
  "from scripts.tools.selection_results import wechat_top5_strategies; print(wechat_top5_strategies())"
```

Expected: the strategy tuple is unchanged from before the snapshot and does not gain a strategy through this ledger.

- [ ] **Step 7: Run syntax and diff checks**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m py_compile \
  stock_ai/limit_up_research/models.py \
  stock_ai/limit_up_research/attribution.py \
  stock_ai/limit_up_research/labels.py \
  stock_ai/limit_up_research/report.py \
  scripts/analysis/sync_limit_up_research.py
cd ..
git diff --check
git status --short
```

Expected: compile and diff checks exit 0; only scoped files are staged for the final commit, while unrelated existing changes remain untouched.

- [ ] **Step 8: Commit documentation and verified wiring**

```bash
git add stock-ai/docs/CAPABILITIES.md stock-mysql/README.md
git commit -m "docs(stock-ai): document limit-up research workflow"
```

---

## Completion Checklist

- [ ] Every invocation creates a run audit row.
- [ ] Eastmoney pool facts are full, raw-preserving, and idempotent.
- [ ] Empty/failed collection cannot overwrite a prior successful snapshot.
- [ ] All current lanes have an attribution record; unavailable explainers are explicit.
- [ ] T+1/T+3/T+5 labels use trading sessions and never rewrite T-day attribution.
- [ ] Markdown and JSON reports agree with MySQL counts.
- [ ] The deprecated Eastmoney eight-dimension diagnosis is never imported.
- [ ] No scheduler or host-job route is added.
- [ ] Formal Top5 sources remain unchanged.
- [ ] Offline tests, guarded MySQL integration, syntax checks, and diff checks pass.
