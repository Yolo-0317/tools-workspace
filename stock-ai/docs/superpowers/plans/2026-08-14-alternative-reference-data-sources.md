# Alternative Reference Data Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace unavailable Tushare industry, ST, suspension, and announcement reference endpoints with point-in-time CNInfo and BaoStock sources while keeping buy-point selection fail-closed.

**Architecture:** Add provider-specific adapters behind typed contracts, normalize their output into the existing `SectorMembership` and `RiskFlag` domain types, and coordinate resumable syncs through provider-aware audit and checkpoint records. The selector continues reading the existing reference repository; Tushare `daily` remains unchanged, CNInfo supplies industry and announcements, and BaoStock supplies dated names and trade status.

**Tech Stack:** Python 3.11, SQLAlchemy 2, MySQL 8, pandas/AKShare CNInfo industry functions, requests, BaoStock 0.9.3, pytest.

## Global Constraints

- Do not call, recommend, or read the deprecated Eastmoney eight/eleven-dimension AI framework.
- Do not use Eastmoney or Tonghuashun functions through AKShare; only CNInfo industry functions are allowed.
- Historical backfill starts at `2024-01-02` and ends at the latest complete MySQL trading date.
- Missing provider data must produce zero formal candidates; stale or current facts cannot fill a historical gap.
- Keep the manual-only workflow: no scheduler, push job, or broker-order integration.
- Do not alter Tushare `daily`, the three buy-point patterns, ranking, position sizing, or release gates.
- Do not store tokens, cookies, complete response headers, or unrelated raw payloads.
- Use TDD for every implementation task and commit only the files named by that task.

---

## File Map

- Create `stock-ai/stock_ai/buy_point_selection/reference_sources.py`: typed provider records, provider protocols, and safe provider errors.
- Create `stock-ai/stock_ai/buy_point_selection/reference_normalization.py`: pure point-in-time normalization for CNInfo industry/announcements and BaoStock status rows.
- Create `stock-ai/stock_ai/buy_point_selection/reference_cninfo.py`: CNInfo industry transport and official announcement pagination.
- Create `stock-ai/stock_ai/buy_point_selection/reference_baostock.py`: BaoStock session and dated snapshot adapter.
- Create `stock-ai/stock_ai/buy_point_selection/reference_sync.py`: checkpoint-aware alternative-source orchestration and coverage calculation.
- Modify `stock-ai/stock_ai/buy_point_selection/reference_data.py`: provider-aware sync audit, checkpoint repository methods, and backward-compatible reads.
- Modify `stock-ai/stock_ai/buy_point_selection/__init__.py`: export only stable public contracts.
- Create `stock-mysql/sql/017_buy_point_reference_provider_audit.sql`: additive audit columns and checkpoint table.
- Modify `stock-ai/scripts/sync/sync_buy_point_reference_data.py`: default to `cninfo-baostock`, retain explicit `tushare` fallback, and load bounded universes.
- Modify `a-share-short-term-trading/scripts/select_short_term_candidates.py`: keep the existing refresh call but surface safe provider failures and suspension coverage as risk coverage.
- Modify `stock-ai/pyproject.toml`, `stock-ai/requirements.txt`, and `stock-ai/uv.lock`: add BaoStock.
- Modify `stock-ai/docs/CAPABILITIES.md`, `stock-ai/docs/PROJECT_LAYOUT.md`, and `a-share-short-term-trading/README.md`: document the new manual source and fail-closed behavior.
- Create focused tests under `stock-ai/tests/unit/` and extend the existing CLI and runtime tests.

---

### Task 1: Typed Source Contracts and Point-in-Time Normalization

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/reference_sources.py`
- Create: `stock-ai/stock_ai/buy_point_selection/reference_normalization.py`
- Create: `stock-ai/tests/unit/test_buy_point_reference_normalization.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/__init__.py`

**Interfaces:**
- Produces: `IndustryCategory`, `IndustryChange`, `SecurityStatus`, `Announcement`, `AnnouncementPage`, `ProviderFailure`.
- Produces: `normalize_cninfo_memberships(...) -> tuple[SectorMembership, ...]`.
- Produces: `normalize_baostock_risk_flags(...) -> tuple[RiskFlag, ...]`.
- Produces: `normalize_cninfo_announcement_flags(...) -> tuple[RiskFlag, ...]`.
- Consumes: existing `SectorMembership`, `RiskFlag`, and `classify_announcement_title` from `reference_data.py`.

- [ ] **Step 1: Write failing normalization tests**

```python
def test_cninfo_changes_become_non_overlapping_l1_intervals():
    categories = (
        IndustryCategory("801000", "", "农林牧渔", 1, None),
        IndustryCategory("801010", "801000", "种植业", 2, None),
        IndustryCategory("801120", "", "食品饮料", 1, None),
    )
    changes = {
        "600001": (
            IndustryChange("600001", date(2023, 1, 3), "申银万国行业分类标准", "801010"),
            IndustryChange("600001", date(2025, 7, 1), "申银万国行业分类标准", "801120"),
        )
    }
    rows = normalize_cninfo_memberships(
        categories,
        changes,
        previous_trade_date=lambda value: date(2025, 6, 30),
    )
    assert [(row.sector_code, row.valid_from, row.valid_to) for row in rows] == [
        ("801000", date(2023, 1, 3), date(2025, 6, 30)),
        ("801120", date(2025, 7, 1), None),
    ]


def test_baostock_snapshot_emits_daily_st_and_suspension_vetoes():
    rows = normalize_baostock_risk_flags(
        (
            SecurityStatus("600001", "*ST 示例", "1", date(2025, 8, 6)),
            SecurityStatus("600002", "普通股份", "0", date(2025, 8, 6)),
        )
    )
    assert {(row.code, row.flag_type) for row in rows} == {
        ("600001", "ST"),
        ("600002", "SUSPENDED"),
    }
    assert all(row.effective_to == date(2025, 8, 6) for row in rows)


def test_after_close_cninfo_announcement_starts_next_trade_day():
    flag = normalize_cninfo_announcement_flags(
        (
            Announcement(
                "600003",
                "ann-1",
                "公司收到中国证监会立案调查告知书",
                datetime(2025, 8, 8, 18, tzinfo=ZoneInfo("Asia/Shanghai")),
                "https://static.cninfo.com.cn/finalpage/ann-1.PDF",
            ),
        ),
        is_trade_date=lambda value: value == date(2025, 8, 8),
        next_trade_date=lambda value: date(2025, 8, 11),
    )[0]
    assert flag.effective_from == date(2025, 8, 11)
    assert flag.effective_to is None
```

- [ ] **Step 2: Run the new test and verify red**

Run:

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_reference_normalization.py
```

Expected: collection fails because the new modules and types do not exist.

- [ ] **Step 3: Implement the typed records and pure normalizers**

`reference_sources.py` must define frozen dataclasses with these exact fields:

```python
@dataclass(frozen=True)
class IndustryCategory:
    code: str
    parent_code: str
    name: str
    level: int
    terminated_on: date | None


@dataclass(frozen=True)
class IndustryChange:
    code: str
    changed_on: date
    standard: str
    industry_code: str


@dataclass(frozen=True)
class SecurityStatus:
    code: str
    name: str
    trade_status: str
    trade_date: date


@dataclass(frozen=True)
class Announcement:
    code: str
    announcement_id: str
    title: str
    published_at: datetime | None
    official_url: str


@dataclass(frozen=True)
class AnnouncementPage:
    records: tuple[Announcement, ...]
    total_count: int
    page_no: int
    page_size: int
    page_count: int


class ProviderFailure(RuntimeError):
    def __init__(self, provider: str, operation: str, error_code: str): ...


class ReferenceProvider(Protocol):
    provider_name: str


class CninfoReferenceSource(ReferenceProvider, Protocol):
    def fetch_industry_categories(self) -> tuple[IndustryCategory, ...]: ...
    def fetch_industry_changes(
        self, code: str, start: date, end: date
    ) -> tuple[IndustryChange, ...]: ...
    def fetch_announcement_page(self, day: date, page_no: int) -> AnnouncementPage: ...


class BaoStockReferenceSource(ReferenceProvider, Protocol):
    def fetch_security_statuses(self, day: date) -> tuple[SecurityStatus, ...]: ...
```

`reference_normalization.py` must reject overlapping industry records, map each change to its active level-1 ancestor, strip spaces before ST-prefix matching, emit both flags when a security is ST and suspended, and use `CNINFO`/`BAOSTOCK` as `source`. Missing announcement time must map conservatively to the next trading date.

- [ ] **Step 4: Run focused tests and verify green**

Run the Task 1 pytest command again.

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock-ai/stock_ai/buy_point_selection/reference_sources.py \
  stock-ai/stock_ai/buy_point_selection/reference_normalization.py \
  stock-ai/stock_ai/buy_point_selection/__init__.py \
  stock-ai/tests/unit/test_buy_point_reference_normalization.py
git commit -m "feat(stock-ai): normalize alternative reference facts"
```

---

### Task 2: Provider-Aware Audit Schema and Checkpoint Repository

**Files:**
- Create: `stock-mysql/sql/017_buy_point_reference_provider_audit.sql`
- Modify: `stock-ai/stock_ai/buy_point_selection/reference_data.py`
- Modify: `stock-ai/tests/unit/test_buy_point_reference_schema.py`
- Create: `stock-ai/tests/unit/test_buy_point_reference_repository.py`

**Interfaces:**
- Produces: expanded `ReferenceSyncRun(provider, expected_count, coverage_ratio, details)`.
- Produces: `ReferenceCheckpoint(provider, dataset, partition_key, cursor_value, status, error_code, details, updated_at)`.
- Produces repository methods `save_checkpoint`, `load_checkpoint`, and `memberships_between`.
- Preserves: old `ReferenceSyncRun` callers by giving new fields safe defaults.

- [ ] **Step 1: Write failing schema and repository tests**

```python
def test_provider_audit_migration_is_additive_and_has_checkpoints():
    sql = (SQL_DIR / "017_buy_point_reference_provider_audit.sql").read_text().lower()
    for column in ("provider", "expected_count", "coverage_ratio", "details_json"):
        assert column in sql
    assert "create table if not exists buy_point_reference_checkpoints" in sql
    assert "primary key (provider, dataset, partition_key)" in sql
    assert "drop table" not in sql and "delete from" not in sql


def test_repository_round_trips_provider_checkpoint(fake_connection):
    repository = SQLReferenceRepository(fake_connection)
    checkpoint = ReferenceCheckpoint(
        provider="CNINFO",
        dataset="sector",
        partition_key="600001",
        cursor_value=None,
        status="COMPLETE",
        error_code=None,
        details={"rows": 2},
        updated_at=NOW,
    )
    repository.save_checkpoint(checkpoint)
    assert "buy_point_reference_checkpoints" in fake_connection.statements[-1]
```

- [ ] **Step 2: Run tests and verify red**

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_reference_schema.py \
  stock-ai/tests/unit/test_buy_point_reference_repository.py
```

Expected: missing migration, checkpoint model, and repository methods.

- [ ] **Step 3: Write additive migration and repository implementation**

The migration must use `information_schema.columns` guards for each new nullable audit column and create this table:

```sql
CREATE TABLE IF NOT EXISTS buy_point_reference_checkpoints (
  provider VARCHAR(32) NOT NULL,
  dataset VARCHAR(32) NOT NULL,
  partition_key VARCHAR(64) NOT NULL,
  cursor_value VARCHAR(64) NULL,
  status VARCHAR(16) NOT NULL,
  error_code VARCHAR(64) NULL,
  details_json JSON NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (provider, dataset, partition_key),
  KEY idx_reference_checkpoint_status (dataset, status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

`save_sync_run` must serialize `details` to `details_json`; `coverage()` must continue accepting old rows and only use `dataset`, dates, and `status`. `memberships_between(start, end)` must issue one bounded query, not one query per date.

- [ ] **Step 4: Run schema and repository tests**

Expected: both files pass.

- [ ] **Step 5: Run existing reference-data tests**

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_reference_data.py \
  stock-ai/tests/unit/test_sync_buy_point_reference_data.py
```

Expected: existing Tushare compatibility tests remain green.

- [ ] **Step 6: Commit Task 2**

```bash
git add stock-mysql/sql/017_buy_point_reference_provider_audit.sql \
  stock-ai/stock_ai/buy_point_selection/reference_data.py \
  stock-ai/tests/unit/test_buy_point_reference_schema.py \
  stock-ai/tests/unit/test_buy_point_reference_repository.py
git commit -m "feat(stock-ai): audit reference providers and checkpoints"
```

---

### Task 3: CNInfo Industry and Announcement Adapter

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/reference_cninfo.py`
- Create: `stock-ai/tests/unit/test_buy_point_reference_cninfo.py`

**Interfaces:**
- Consumes: Task 1 source records and `ProviderFailure`.
- Produces: `CninfoReferenceProvider.fetch_industry_categories()`.
- Produces: `CninfoReferenceProvider.fetch_industry_changes(code, start, end)`.
- Produces: `CninfoReferenceProvider.fetch_announcement_page(day, page_no)`.

- [ ] **Step 1: Write failing adapter tests with injected callables and session**

```python
def test_cninfo_adapter_allows_only_sw_industry_rows():
    provider = CninfoReferenceProvider(
        category_fetcher=lambda symbol: DataFrame([
            {"类目编码": "801000", "父类编码": "", "类目名称": "农林牧渔", "分级": 1, "终止日期": None}
        ]),
        change_fetcher=lambda **kwargs: DataFrame([
            {"证券代码": "600001", "变更日期": date(2024, 1, 2), "分类标准": "申银万国行业分类标准", "行业编码": "801000"}
        ]),
        session=FakeSession(),
    )
    assert provider.fetch_industry_categories()[0].code == "801000"
    assert provider.fetch_industry_changes("600001", date(1990, 1, 1), date(2025, 8, 6))[0].standard == "申银万国行业分类标准"


def test_cninfo_announcement_page_preserves_declared_totals():
    provider = CninfoReferenceProvider(
        category_fetcher=unused,
        change_fetcher=unused,
        session=FakeSession(total=31, announcements=[announcement_payload]),
        page_size=30,
    )
    page = provider.fetch_announcement_page(date(2025, 8, 6), 1)
    assert page.total_count == 31
    assert page.page_count == 2
    assert page.records[0].official_url.startswith("https://static.cninfo.com.cn/")
```

Also test 429 to `PROVIDER_RATE_LIMITED`, 5xx to `PROVIDER_UNAVAILABLE`, missing `totalAnnouncement` to `PROVIDER_SCHEMA_CHANGED`, duplicate/missing announcement IDs, and timestamps converted to `Asia/Shanghai`.

- [ ] **Step 2: Run adapter tests and verify red**

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_reference_cninfo.py
```

- [ ] **Step 3: Implement the adapter**

Lazy-import AKShare inside the default constructor. Pass exactly `"申银万国行业分类标准"` to `stock_industry_category_cninfo`; call `stock_industry_change_cninfo(symbol=..., start_date=YYYYMMDD, end_date=YYYYMMDD)` for changes.

Announcements must POST to:

```text
https://www.cninfo.com.cn/new/hisAnnouncement/query
```

Use `pageNum`, `pageSize`, `column=szse`, `tabName=fulltext`, empty `stock`, and `seDate=YYYY-MM-DD~YYYY-MM-DD`. Validate `totalAnnouncement` before constructing `AnnouncementPage`. Build official PDF URLs from `adjunctUrl`; do not fabricate a detail URL when the field is absent.

- [ ] **Step 4: Run adapter and normalization tests**

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_reference_cninfo.py \
  stock-ai/tests/unit/test_buy_point_reference_normalization.py
```

- [ ] **Step 5: Commit Task 3**

```bash
git add stock-ai/stock_ai/buy_point_selection/reference_cninfo.py \
  stock-ai/tests/unit/test_buy_point_reference_cninfo.py
git commit -m "feat(stock-ai): fetch CNInfo reference facts"
```

---

### Task 4: BaoStock Dated Status Adapter and Dependency

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/reference_baostock.py`
- Create: `stock-ai/tests/unit/test_buy_point_reference_baostock.py`
- Modify: `stock-ai/pyproject.toml`
- Modify: `stock-ai/requirements.txt`
- Modify: `stock-ai/uv.lock`

**Interfaces:**
- Consumes: Task 1 `SecurityStatus` and `ProviderFailure`.
- Produces: `BaoStockReferenceProvider.fetch_security_statuses(day) -> tuple[SecurityStatus, ...]`.

- [ ] **Step 1: Write failing session-lifecycle tests**

```python
def test_baostock_adapter_logs_out_and_preserves_requested_day():
    sdk = FakeBaoStock(
        rows=[("sh.600001", "1", "*ST 示例"), ("sz.000002", "0", "普通股份")]
    )
    rows = BaoStockReferenceProvider(sdk=sdk).fetch_security_statuses(date(2025, 8, 6))
    assert [row.code for row in rows] == ["600001", "000002"]
    assert all(row.trade_date == date(2025, 8, 6) for row in rows)
    assert sdk.login_calls == 1 and sdk.logout_calls == 1
```

Add tests for login failure, row iteration failure, schema mismatch, duplicate codes, and logout in `finally`.

- [ ] **Step 2: Run adapter tests and verify red**

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_reference_baostock.py
```

- [ ] **Step 3: Add BaoStock and lock dependencies**

Add `"baostock>=0.9.3,<0.10"` to `pyproject.toml`, add `baostock>=0.9.3,<0.10` to `requirements.txt`, then run:

```bash
cd stock-ai
uv lock
uv sync
```

- [ ] **Step 4: Implement the adapter**

Lazy-import `baostock` for production. Call `login()`, `query_all_stock(day=day.isoformat())`, iterate with `next()`/`get_row_data()`, map the response field names instead of assuming column order, and call `logout()` in `finally`. Provider errors must contain only provider, operation, and safe error code.

- [ ] **Step 5: Run BaoStock and normalization tests**

Expected: all tests pass with no network access.

- [ ] **Step 6: Commit Task 4**

```bash
git add stock-ai/stock_ai/buy_point_selection/reference_baostock.py \
  stock-ai/tests/unit/test_buy_point_reference_baostock.py \
  stock-ai/pyproject.toml stock-ai/requirements.txt stock-ai/uv.lock
git commit -m "feat(stock-ai): fetch BaoStock dated status"
```

---

### Task 5: Resumable Alternative Reference Sync Service

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/reference_sync.py`
- Create: `stock-ai/tests/unit/test_buy_point_alternative_reference_sync.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/__init__.py`

**Interfaces:**
- Consumes: Task 1 normalizers, Task 2 repository/checkpoints, Task 3 CNInfo provider, Task 4 BaoStock provider.
- Produces: `AlternativeReferenceSyncRequest` and `sync_alternative_reference_data(...) -> tuple[ReferenceSyncRun, ...]`.

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_sync_marks_daily_st_and_announcement_coverage_complete():
    request = AlternativeReferenceSyncRequest(
        trade_dates=(date(2025, 8, 5), date(2025, 8, 6)),
        universe_by_date={
            date(2025, 8, 5): frozenset({"600001", "600002"}),
            date(2025, 8, 6): frozenset({"600001", "600002"}),
        },
        captured_at=NOW,
        minimum_coverage=Decimal("0.98"),
    )
    runs = sync_alternative_reference_data(
        request,
        cninfo=FakeCninfoProvider(),
        baostock=FakeBaoStockProvider(),
        repository=MemoryRepository(),
        sleep=lambda _: None,
    )
    assert {(run.dataset, run.status) for run in runs} == {
        ("sector", "COMPLETE"),
        ("st", "COMPLETE"),
        ("announcement", "COMPLETE"),
    }
```

Add tests that prove:

- a complete checkpoint skips that partition;
- refreshing the last two trading dates does not skip them;
- one missing announcement page fails only announcement coverage;
- 97% BaoStock coverage records `COVERAGE_BELOW_THRESHOLD`;
- weekend announcements are included in Monday's announcement coverage;
- a failed industry code prevents a broad sector `COMPLETE` run;
- repeated syncs produce identical fact keys and no duplicate page records.

- [ ] **Step 2: Run orchestration tests and verify red**

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_alternative_reference_sync.py
```

- [ ] **Step 3: Implement request, partitioning, and checkpoints**

Use this exact request contract:

```python
@dataclass(frozen=True)
class AlternativeReferenceSyncRequest:
    trade_dates: tuple[date, ...]
    universe_by_date: Mapping[date, frozenset[str]]
    captured_at: datetime
    minimum_coverage: Decimal = Decimal("0.98")
    refresh_recent_trade_dates: int = 2
```

Industry partitions are six-digit codes. BaoStock partitions are trading dates. Announcement partitions are calendar dates; Monday coverage is complete only after Saturday, Sunday, and Monday partitions succeed. Query existing memberships once with `memberships_between`, merge new facts, and calculate all sector-date coverage ratios in memory.

- [ ] **Step 4: Implement page validation, retry, and audit runs**

Fetch every announcement page from 1 through `page_count`, verify all pages report the same `total_count`, and require unique announcement IDs. Retry only `PROVIDER_RATE_LIMITED` and `PROVIDER_UNAVAILABLE` with delays `(1, 2, 4)` seconds; never retry schema or coverage failures. Persist a failed checkpoint and safe error code after the final attempt.

Write one sector run for the requested range and one ST/announcement run per trading date. A daily announcement run summarizes the natural-date partitions since the previous trading date. `details` must contain counts and partition keys, not raw responses.

- [ ] **Step 5: Run sync, repository, and normalization tests**

```bash
PYTHONPATH=stock-ai stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_alternative_reference_sync.py \
  stock-ai/tests/unit/test_buy_point_reference_repository.py \
  stock-ai/tests/unit/test_buy_point_reference_normalization.py
```

- [ ] **Step 6: Commit Task 5**

```bash
git add stock-ai/stock_ai/buy_point_selection/reference_sync.py \
  stock-ai/stock_ai/buy_point_selection/__init__.py \
  stock-ai/tests/unit/test_buy_point_alternative_reference_sync.py
git commit -m "feat(stock-ai): sync alternative point-in-time references"
```

---

### Task 6: Manual CLI Wiring and Selector Fail-Closed Integration

**Files:**
- Modify: `stock-ai/scripts/sync/sync_buy_point_reference_data.py`
- Modify: `stock-ai/tests/unit/test_sync_buy_point_reference_data.py`
- Modify: `a-share-short-term-trading/scripts/select_short_term_candidates.py`
- Modify: `a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py`
- Modify: `stock-ai/tests/unit/test_buy_point_full_universe_runtime.py`

**Interfaces:**
- Consumes: Task 5 `sync_alternative_reference_data`.
- Produces CLI `--provider {cninfo-baostock,tushare}` with default `cninfo-baostock`.
- Preserves `--start`, `--end latest`, and selector `--refresh-reference-data`.

- [ ] **Step 1: Write failing CLI and runtime tests**

```python
def test_reference_cli_defaults_to_cninfo_baostock():
    args = module.build_parser().parse_args([
        "--start", "2024-01-02", "--end", "latest"
    ])
    assert args.provider == "cninfo-baostock"


def test_reference_cli_keeps_tushare_as_explicit_fallback():
    args = module.build_parser().parse_args([
        "--start", "2024-01-02", "--end", "latest", "--provider", "tushare"
    ])
    assert args.provider == "tushare"
```

Add tests that `_universe_by_date` executes one bounded SQL query, filters to Shanghai/Shenzhen main-board codes, uses a 180-calendar-day lookback for suspended securities, and that a `SUSPENDED` VETO excludes formal selection through the existing base gate. Verify provider failure prints only a safe code.

- [ ] **Step 2: Run CLI/runtime tests and verify red**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_sync_buy_point_reference_data.py \
  stock-ai/tests/unit/test_buy_point_full_universe_runtime.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py
```

- [ ] **Step 3: Implement provider selection and bounded universe loading**

Add `--provider` to the sync parser. Build `universe_by_date` in one query spanning `start - 180 days` through `end`; for each trading date include main-board codes with at least one bar in the trailing window. Instantiate CNInfo and BaoStock adapters only when the alternative provider is selected.

The CLI must print each run as:

```text
sector[CNINFO]: COMPLETE, rows=..., coverage=..., range=... .. ...
st[BAOSTOCK]: COMPLETE, rows=..., coverage=..., range=... .. ...
announcement[CNINFO]: COMPLETE, rows=..., coverage=..., range=... .. ...
```

Failures append only `error=<SAFE_CODE>` and return 2.

- [ ] **Step 4: Preserve selector behavior**

`DefaultRuntime.refresh_reference_data` should continue calling the default sync without a provider argument. A successful alternative sync must be visible through existing `SQLReferenceRepository.coverage()`. Missing ST/suspension data remains `RISK_COVERAGE`; do not add a fourth release gate.

- [ ] **Step 5: Run CLI/runtime and all buy-point tests**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/pytest -q \
  stock-ai/tests/unit/test_buy_point_*.py \
  stock-ai/tests/unit/test_sync_buy_point_reference_data.py \
  a-share-short-term-trading/tests/test_buy_point_*.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py
```

- [ ] **Step 6: Commit Task 6**

```bash
git add stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  stock-ai/tests/unit/test_sync_buy_point_reference_data.py \
  stock-ai/tests/unit/test_buy_point_full_universe_runtime.py \
  a-share-short-term-trading/scripts/select_short_term_candidates.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py
git commit -m "feat(stock-ai): use CNInfo and BaoStock reference sync"
```

---

### Task 7: Documentation and Offline Verification

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md`
- Modify: `stock-ai/docs/PROJECT_LAYOUT.md`
- Modify: `a-share-short-term-trading/README.md`
- Modify: `stock-ai/tests/unit/test_buy_point_reference_schema.py`

**Interfaces:**
- Documents the default provider, manual commands, permissions, checkpoints, and fail-closed behavior.

- [ ] **Step 1: Update documentation assertions first**

Extend the schema test to assert that migration 017 is additive, does not contain credentials, and creates provider checkpoints. Add a CLI help test asserting `cninfo-baostock` and `tushare` both appear.

- [ ] **Step 2: Run documentation-contract tests and verify red**

Run the schema and CLI test files.

- [ ] **Step 3: Update user documentation**

Document these commands exactly:

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2024-01-02 --end latest

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2024-01-02 --end latest --provider tushare
```

The second command is an explicit fallback and is expected to fail when the token lacks permission. State that normal selection does not refresh references and that neither command installs a schedule.

- [ ] **Step 4: Run full offline verification**

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_*.py \
  stock-ai/tests/unit/test_sync_buy_point_reference_data.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py \
  a-share-short-term-trading/tests/test_buy_point_*.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py
```

Also run:

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py --help
git diff --check
```

- [ ] **Step 5: Commit Task 7**

```bash
git add stock-ai/docs/CAPABILITIES.md stock-ai/docs/PROJECT_LAYOUT.md \
  a-share-short-term-trading/README.md \
  stock-ai/tests/unit/test_buy_point_reference_schema.py
git commit -m "docs(stock-ai): document alternative reference sync"
```

---

### Task 8: Controlled Runtime Rollout and Backfill

**Files:**
- Runtime only: MySQL schema and data; no generated holdings, credentials, or backfill output may be committed.

**Interfaces:**
- Consumes all completed implementation tasks.
- Produces MySQL migration 017, reference facts, checkpoints, and provider-aware audit rows.

- [ ] **Step 1: Dry-check migration and current runtime state**

Read-only checks must confirm migration 017 has not already been applied, count current failed Tushare audits, and identify the latest complete `stock_daily` date. Do not print URLs containing credentials.

- [ ] **Step 2: Apply migration 017 explicitly**

Use the configured MySQL root connection to execute only:

```text
stock-mysql/sql/017_buy_point_reference_provider_audit.sql
```

Then verify the four audit columns and `buy_point_reference_checkpoints` exist.

- [ ] **Step 3: Run a two-trading-day provider smoke test**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start <previous-complete-trading-date> --end latest
```

Inspect only safe summary fields. Require all three datasets to be `COMPLETE`, coverage at least 98%, and official CNInfo evidence links for any matched announcement risk.

- [ ] **Step 4: Verify idempotency on the same two dates**

Run the same command again. Compare fact counts and primary-key counts before/after; duplicates must remain zero and checkpoints must remain `COMPLETE`.

- [ ] **Step 5: Run the resumable historical backfill**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  --start 2024-01-02 --end latest
```

Monitor progress in bounded intervals, reporting completed/failed industry codes, ST dates, and announcement dates. Do not mark the implementation complete while any checkpoint required for the range is failed or running.

- [ ] **Step 6: Run the V1.3 selector and inspect the new gap profile**

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/select_short_term_candidates.py \
  --skip-lanes --output text
```

Verify the current analysis date no longer gives every observation `SECTOR` and `RISK_COVERAGE`. The selector must remain `SHADOW` until the historical validation artifact and 20-day/20-resolved-plan gates pass.

- [ ] **Step 7: Final evidence and handoff**

Re-run the full offline verification command from Task 7 after runtime rollout. Report exact test counts, three provider coverage statuses, backfill bounds, unresolved checkpoints, and current release mode. Do not promise profitability or call `SHADOW` formally live.

---

## Plan Self-Review Checklist

- [ ] Every design section maps to at least one implementation task.
- [ ] No task calls an Eastmoney or Tonghuashun AKShare function.
- [ ] CNInfo announcement totals remain visible and testable at the adapter boundary.
- [ ] BaoStock snapshots are explicitly dated and never reused across dates.
- [ ] Coverage, checkpoints, retry rules, and safe error codes have concrete tests.
- [ ] Existing Tushare reference sync remains an explicit, backward-compatible fallback.
- [ ] Runtime migration and network backfill are separate from offline tests and commits.
- [ ] No placeholder instructions or undefined neighboring interfaces remain.
