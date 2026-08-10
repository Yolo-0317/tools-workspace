# Short-Term Trading Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1.1 versioned contracts, complete MySQL schema, repository layer, broker-fact persistence, and least-privilege runtime account required by every later short-term trading phase.

**Architecture:** Keep deterministic domain contracts in `a-share-short-term-trading/short_term_trading/contracts`, isolate SQLAlchemy access in focused repository modules, and install idempotent versioned SQL through a root-only migration CLI. Existing `stock_daily`, `portfolio_account`, and `portfolio_positions` remain compatibility sources while the new `stt_` tables store versioned trading decisions and evidence.

**Tech Stack:** Python 3.10+, Pydantic 2.12, SQLAlchemy 2.x, PyMySQL, MySQL 8, pytest 9

## Global Constraints

- Schema version is exactly `1.1`.
- Internal timestamps are timezone-aware UTC; chat rendering converts to `Asia/Shanghai`.
- Prices and money use `Decimal` in Python, JSON strings, and fixed-point MySQL columns.
- Unknown JSON fields are rejected.
- Root applies migrations; `stt_app` receives runtime DML only and no `CREATE`, `DROP`, `ALTER`, or `INDEX`.
- Evidence and decision snapshots are append-only.
- No Web dashboard, Home Hub integration, scheduler, push notification, or broker order action is added.
- No password, Cookie, full brokerage account number, holding fixture, or personal session data enters Git.
- Preserve unrelated workspace changes and stage only phase-1 files.

---

## File Structure

- Modify `stock-ai/pyproject.toml` to declare the direct Pydantic dependency already present in the lock.
- Create `a-share-short-term-trading/short_term_trading/contracts/base.py` for shared enums, strict base model, UTC validation, code validation, and Decimal JSON rules.
- Create `a-share-short-term-trading/short_term_trading/contracts/market.py` for `MarketStateV1`, `CandidateV1`, and `EvidenceSnapshotV1`.
- Create `a-share-short-term-trading/short_term_trading/contracts/decisions.py` for plan, risk, freeze, and intraday contracts.
- Create `a-share-short-term-trading/short_term_trading/contracts/review.py` for journal, outcome, and evaluation contracts.
- Create `a-share-short-term-trading/short_term_trading/repositories/connection.py` for engine construction and transaction helpers.
- Create `a-share-short-term-trading/short_term_trading/repositories/evidence.py`, `planning.py`, and `review.py` for focused persistence APIs.
- Replace the pre-deployment definitions in `sql/001_stt_daily_sync_runs.sql` and `sql/002_stt_evidence_and_capture.sql` with v1.1-compatible definitions.
- Create `sql/003_stt_core_schema.sql` for the remaining `stt_` tables and `sql/004_portfolio_broker_facts.sql` for missing broker facts.
- Create `scripts/apply_migrations.py` and `scripts/configure_mysql_permissions.py` for explicit root-only administration.
- Modify `stock-ai/scripts/tools/jywg_portfolio_sync.py` and `stock-ai/scripts/tools/portfolio_db.py` to preserve available shares, current price, market value, daily P&L, and brokerage capture time.
- Add isolated unit and integration tests under `a-share-short-term-trading/tests` and `stock-ai/tests/unit`.

---

### Task 1: Strict Contract Foundation

**Files:**
- Modify: `stock-ai/pyproject.toml`
- Create: `a-share-short-term-trading/short_term_trading/contracts/__init__.py`
- Create: `a-share-short-term-trading/short_term_trading/contracts/base.py`
- Test: `a-share-short-term-trading/tests/test_contract_base.py`

**Interfaces:**
- Produces: `ContractModel`, `DataStatus`, `SignalStatus`, `MarketStatus`, `ReleaseMode`, `EvidenceKind`, `validate_code(value: str) -> str`, and `utc_now() -> datetime`.
- Consumers: every contract and repository in later tasks.

- [ ] **Step 1: Declare Pydantic as a direct dependency**

Add this exact dependency to `stock-ai/pyproject.toml`:

```toml
"pydantic>=2.12,<3",
```

Run: `cd stock-ai && uv lock --offline`

Expected: exit 0 with no network access and a lock entry for direct `pydantic` usage.

- [ ] **Step 2: Write failing base-contract tests**

Cover exact schema version, unknown-field rejection, UTC enforcement, six-digit code normalization, Decimal JSON strings, and enum rejection:

```python
def test_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ExampleContract(as_of=UTC_NOW, source="fixture", data_status="VALID", code="600000", extra="x")

def test_contract_serializes_decimal_as_string() -> None:
    value = ExampleContract(
        as_of=UTC_NOW,
        source="fixture",
        data_status="VALID",
        code="600000",
        price=Decimal("12.30"),
    )
    assert value.model_dump(mode="json")["price"] == "12.30"
```

Run: `PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q a-share-short-term-trading/tests/test_contract_base.py`

Expected: fail because `short_term_trading.contracts.base` does not exist.

- [ ] **Step 3: Implement the strict base model and enums**

Use this configuration and validation policy:

```python
class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_encoders={Decimal: lambda value: format(value, "f")},
    )

    schema_version: Literal["1.1"] = "1.1"
    as_of: datetime
    source: str
    data_status: DataStatus

    @field_validator("as_of")
    @classmethod
    def require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(timezone.utc)
```

Define the exact trading enums from the v1.1 spec; do not add a seventh signal status for shadow mode.

- [ ] **Step 4: Run base-contract tests**

Run: `PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q a-share-short-term-trading/tests/test_contract_base.py`

Expected: all tests pass.

- [ ] **Step 5: Commit the foundation**

```bash
git add stock-ai/pyproject.toml stock-ai/uv.lock \
  a-share-short-term-trading/short_term_trading/contracts \
  a-share-short-term-trading/tests/test_contract_base.py
git commit -m "feat(stt): add strict v1.1 contract foundation"
```

---

### Task 2: Domain Contracts and State Validation

**Files:**
- Create: `a-share-short-term-trading/short_term_trading/contracts/market.py`
- Create: `a-share-short-term-trading/short_term_trading/contracts/decisions.py`
- Create: `a-share-short-term-trading/short_term_trading/contracts/review.py`
- Modify: `a-share-short-term-trading/short_term_trading/contracts/__init__.py`
- Test: `a-share-short-term-trading/tests/test_contract_market.py`
- Test: `a-share-short-term-trading/tests/test_contract_decisions.py`
- Test: `a-share-short-term-trading/tests/test_contract_review.py`

**Interfaces:**
- Produces: the ten v1.1 contracts named in the design spec.
- Consumes: `ContractModel` and enums from Task 1.
- Consumers: repositories, deterministic engines, orchestration, and rendering.

- [ ] **Step 1: Write failing market and evidence tests**

Test `MarketStateV1`, `CandidateV1`, and `EvidenceSnapshotV1` for required IDs, exact candidate type `BREAKOUT`, evidence references, timezone-aware expiry, and kind-specific payload validation.

```python
def test_candidate_v1_only_accepts_breakout() -> None:
    with pytest.raises(ValidationError):
        CandidateV1(candidate_type="PULLBACK", **VALID_CANDIDATE)

def test_evidence_requires_code_except_market() -> None:
    with pytest.raises(ValidationError):
        EvidenceSnapshotV1(kind="QUOTE", code=None, **VALID_EVIDENCE)
```

- [ ] **Step 2: Write failing decision-state tests**

Verify that an end-of-day plan cannot be `BUY_ALLOWED`, a shadow intraday decision remains `status=BUY_ALLOWED` with `release_mode=SHADOW` and `actionable=false`, and `REDUCE` includes a quantity or ratio.

```python
def test_shadow_buy_is_not_actionable() -> None:
    decision = IntradayDecisionV1(
        status="BUY_ALLOWED",
        release_mode="SHADOW",
        actionable=False,
        **VALID_INTRADAY,
    )
    assert decision.actionable is False

def test_reduce_requires_size() -> None:
    with pytest.raises(ValidationError):
        IntradayDecisionV1(status="REDUCE", reduce_shares=None, reduce_ratio=None, **VALID_INTRADAY)
```

- [ ] **Step 3: Write failing review-contract tests**

Verify positive quantities, explicit user-confirmed journal actions, evaluation horizons `T1/T3/T5`, immutable decision references, and Decimal serialization.

- [ ] **Step 4: Run the new tests and confirm red state**

Run: `PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q a-share-short-term-trading/tests/test_contract_market.py a-share-short-term-trading/tests/test_contract_decisions.py a-share-short-term-trading/tests/test_contract_review.py`

Expected: imports fail because domain contracts are absent.

- [ ] **Step 5: Implement all ten contracts**

Use UUID string IDs, explicit `Literal`/enum fields, `Decimal` for every price/money field, and model validators for cross-field rules. Export only public contracts from `contracts/__init__.py`.

Required concrete class names:

```python
MarketStateV1
CandidateV1
EvidenceSnapshotV1
TradePlanV1
RiskDecisionV1
DecisionSnapshotV1
IntradayDecisionV1
TradeJournalV1
OutcomeObservationV1
PlanEvaluationV1
```

- [ ] **Step 6: Run all contract tests**

Run: `PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q a-share-short-term-trading/tests/test_contract_*.py`

Expected: all contract tests pass.

- [ ] **Step 7: Commit domain contracts**

```bash
git add a-share-short-term-trading/short_term_trading/contracts \
  a-share-short-term-trading/tests/test_contract_market.py \
  a-share-short-term-trading/tests/test_contract_decisions.py \
  a-share-short-term-trading/tests/test_contract_review.py
git commit -m "feat(stt): define v1.1 domain contracts"
```

---

### Task 3: Complete Idempotent MySQL Schema

**Files:**
- Modify: `a-share-short-term-trading/sql/001_stt_daily_sync_runs.sql`
- Modify: `a-share-short-term-trading/sql/002_stt_evidence_and_capture.sql`
- Create: `a-share-short-term-trading/sql/003_stt_core_schema.sql`
- Create: `a-share-short-term-trading/sql/004_portfolio_broker_facts.sql`
- Create: `a-share-short-term-trading/scripts/apply_migrations.py`
- Test: `a-share-short-term-trading/tests/test_migration_files.py`
- Test: `a-share-short-term-trading/tests/integration/test_mysql_migrations.py`

**Interfaces:**
- Produces: all fifteen `stt_` tables, schema version `1.1`, broker-fact columns, and an idempotent root migration CLI.
- Consumes: `MYSQL_ROOT_PASSWORD`, host `192.168.1.13`, port `3306`, database `stock_data`.

- [ ] **Step 1: Write static failing migration tests**

Assert that SQL files define every table from the spec, use `DECIMAL` for prices/money, include code/trading-date/status/time indexes, declare append-only table IDs, and never contain credentials.

```python
EXPECTED_TABLES = {
    "stt_schema_versions", "stt_watchlist", "stt_market_states",
    "stt_candidates", "stt_evidence_snapshots", "stt_capture_attempts",
    "stt_source_health", "stt_daily_sync_runs", "stt_trade_plans",
    "stt_risk_decisions", "stt_decision_snapshots",
    "stt_intraday_decisions", "stt_outcome_observations",
    "stt_trade_journal", "stt_plan_evaluations",
}
```

- [ ] **Step 2: Write integration tests for first and repeated migration**

The test must require `STT_MYSQL_INTEGRATION=1`, apply migrations twice, inspect `information_schema`, verify schema version `1.1`, and use a temporary transaction for DML. It must not drop the database or existing non-`stt_` tables.

- [ ] **Step 3: Run migration tests and confirm red state**

Run: `PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q a-share-short-term-trading/tests/test_migration_files.py`

Expected: fail with missing tables and migration runner.

- [ ] **Step 4: Implement SQL definitions**

Use `CREATE TABLE IF NOT EXISTS`, explicit primary keys, unique idempotency keys, JSON evidence-reference columns, `DATETIME(6)` UTC storage, and named indexes. Insert schema version with:

```sql
INSERT INTO stt_schema_versions (version, description)
VALUES ('1.1', 'short-term trading v1.1 foundation')
ON DUPLICATE KEY UPDATE description = VALUES(description);
```

`004_portfolio_broker_facts.sql` adds these nullable compatibility columns only when absent through `information_schema`-guarded prepared statements:

```text
portfolio_positions.available_shares
portfolio_positions.current_price
portfolio_positions.market_value
portfolio_positions.position_pnl
portfolio_positions.position_pnl_pct
portfolio_positions.daily_pnl
portfolio_positions.daily_pnl_pct
portfolio_positions.broker_captured_at
portfolio_account.cash_balance
portfolio_account.withdrawable_cash
portfolio_account.frozen_cash
portfolio_account.daily_pnl
portfolio_account.broker_captured_at
```

- [ ] **Step 5: Implement the root migration CLI**

The CLI reads the root password from `stock-ai/.env`, never prints it, executes SQL files in numeric order, stops on first failure, and prints only file names and success states.

Run: `PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/python a-share-short-term-trading/scripts/apply_migrations.py --dry-run`

Expected: lists `001` through `004` without connecting or mutating MySQL.

- [ ] **Step 6: Run static and integration migration tests**

Run static tests first, then:

```bash
STT_MYSQL_INTEGRATION=1 PYTHONPATH=a-share-short-term-trading \
  stock-ai/.venv/bin/pytest -q a-share-short-term-trading/tests/integration/test_mysql_migrations.py
```

Expected: migration can run twice and all schema assertions pass.

- [ ] **Step 7: Commit the schema**

```bash
git add a-share-short-term-trading/sql \
  a-share-short-term-trading/scripts/apply_migrations.py \
  a-share-short-term-trading/tests/test_migration_files.py \
  a-share-short-term-trading/tests/integration/test_mysql_migrations.py
git commit -m "feat(stt): add complete v1.1 mysql schema"
```

---

### Task 4: Focused Repository Layer

**Files:**
- Create: `a-share-short-term-trading/short_term_trading/repositories/__init__.py`
- Create: `a-share-short-term-trading/short_term_trading/repositories/connection.py`
- Create: `a-share-short-term-trading/short_term_trading/repositories/evidence.py`
- Create: `a-share-short-term-trading/short_term_trading/repositories/planning.py`
- Create: `a-share-short-term-trading/short_term_trading/repositories/review.py`
- Modify: `a-share-short-term-trading/short_term_trading/evidence.py`
- Test: `a-share-short-term-trading/tests/test_repositories.py`
- Test: `a-share-short-term-trading/tests/integration/test_mysql_repositories.py`

**Interfaces:**
- Produces: `create_mysql_engine(url: str) -> Engine`, `EvidenceRepository`, `PlanningRepository`, and `ReviewRepository`.
- Consumes: contracts from Task 2 and tables from Task 3.
- Consumers: all later engines and orchestration.

- [ ] **Step 1: Write failing repository unit tests**

Use a recording fake connection to assert exact parameter conversion: UUIDs remain strings, `Decimal` remains Decimal until driver binding, UTC datetimes become naive UTC for MySQL, enums store `.value`, and nested fields serialize as UTF-8 JSON.

- [ ] **Step 2: Write failing integration repository tests**

Inside one rollback-only transaction, save and reload one object of every contract type. Assert equality through `model_dump(mode="json")`, unique-key idempotency, latest-valid evidence ordering, and refusal to update frozen decisions.

- [ ] **Step 3: Run repository tests and confirm red state**

Run: `PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q a-share-short-term-trading/tests/test_repositories.py`

Expected: repository imports fail.

- [ ] **Step 4: Implement focused repositories**

Required public methods include:

```python
EvidenceRepository.save_snapshot(snapshot: EvidenceSnapshotV1) -> None
EvidenceRepository.latest_valid(code: str, kind: EvidenceKind) -> EvidenceSnapshotV1 | None
PlanningRepository.save_market_state(state: MarketStateV1) -> None
PlanningRepository.save_candidate(candidate: CandidateV1) -> None
PlanningRepository.save_plan(plan: TradePlanV1) -> None
PlanningRepository.save_risk_decision(decision: RiskDecisionV1) -> None
PlanningRepository.freeze_decision(snapshot: DecisionSnapshotV1) -> None
PlanningRepository.save_intraday(decision: IntradayDecisionV1) -> None
ReviewRepository.save_journal(entry: TradeJournalV1) -> None
ReviewRepository.save_outcome(observation: OutcomeObservationV1) -> None
ReviewRepository.save_evaluation(evaluation: PlanEvaluationV1) -> None
```

Move SQLAlchemy persistence out of `short_term_trading/evidence.py`; keep its validation/capture behavior and inject the new repository protocol.

- [ ] **Step 5: Run unit and integration repository tests**

Run unit tests, then run integration tests with `STT_MYSQL_INTEGRATION=1`.

Expected: all repository round trips pass and leave no test rows after rollback.

- [ ] **Step 6: Run the existing MVP regression suite**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q -p no:cacheprovider a-share-short-term-trading/tests`

Expected: existing daily sync, diagnosis, evidence, gate, capture, and intraday tests remain green.

- [ ] **Step 7: Commit repositories**

```bash
git add a-share-short-term-trading/short_term_trading/repositories \
  a-share-short-term-trading/short_term_trading/evidence.py \
  a-share-short-term-trading/tests/test_repositories.py \
  a-share-short-term-trading/tests/integration/test_mysql_repositories.py
git commit -m "feat(stt): add v1.1 mysql repositories"
```

---

### Task 5: Preserve Complete Brokerage Facts

**Files:**
- Modify: `stock-ai/scripts/tools/jywg_portfolio_sync.py`
- Modify: `stock-ai/scripts/tools/portfolio_db.py`
- Modify: `stock-ai/scripts/tools/fetch_jywg_positions_opencli.py`
- Test: `stock-ai/tests/unit/test_jywg_portfolio_sync.py`
- Test: `a-share-short-term-trading/tests/integration/test_broker_fact_sync.py`

**Interfaces:**
- Produces: complete broker facts in compatibility tables without changing alert rules.
- Consumes: the existing JYWG payload keys `qty`, `available`, `cost`, `price`, `market_value`, `pnl`, `pnl_pct`, `day_pnl`, and `day_pnl_pct`.

- [ ] **Step 1: Write a failing parser/sync unit test**

Use a fully synthetic payload and assert conversion preserves every broker field and a timezone-aware `broker_captured_at` while masking the account identifier.

```python
assert position.shares == 500
assert position.available_shares == 200
assert position.current_price == Decimal("7.01")
assert position.daily_pnl == Decimal("33.00")
```

- [ ] **Step 2: Write a failing rollback-only MySQL integration test**

Sync two synthetic positions, verify every new column, verify absent previous codes become inactive, and roll back the transaction.

- [ ] **Step 3: Run tests and confirm red state**

Run: `cd stock-ai && .venv/bin/pytest -q tests/unit/test_jywg_portfolio_sync.py`

Expected: missing broker-fact attributes or columns.

- [ ] **Step 4: Extend conversion and upsert logic**

Introduce dedicated `BrokerPosition` and `BrokerAccount` dataclasses in `jywg_portfolio_sync.py` without changing the Markdown-card parser contract. Add a dedicated `sync_broker_positions_and_account` function in `portfolio_db.py`, bind all new fields, retain `source="jywg"`, and do not modify `alert_rules`.

- [ ] **Step 5: Run unit and integration tests**

Expected: all facts round-trip, old inactive-code behavior remains, and no alert rule changes occur.

- [ ] **Step 6: Commit brokerage persistence**

```bash
git add stock-ai/scripts/tools/jywg_portfolio_sync.py \
  stock-ai/scripts/tools/portfolio_db.py \
  stock-ai/scripts/tools/fetch_jywg_positions_opencli.py \
  stock-ai/tests/unit/test_jywg_portfolio_sync.py \
  a-share-short-term-trading/tests/integration/test_broker_fact_sync.py
git commit -m "feat(stt): preserve complete brokerage facts"
```

---

### Task 6: Runtime Permissions and Phase-1 Acceptance

**Files:**
- Create: `a-share-short-term-trading/scripts/configure_mysql_permissions.py`
- Test: `a-share-short-term-trading/tests/test_permission_script.py`
- Test: `a-share-short-term-trading/tests/integration/test_mysql_permissions.py`
- Modify: `a-share-short-term-trading/README.md`

**Interfaces:**
- Produces: root-only permission administration and verified `stt_app` runtime access.
- Consumes: `MYSQL_ROOT_PASSWORD`, existing `MYSQL_URL`, database `stock_data`, account `stt_app@%`.

- [ ] **Step 1: Write failing permission tests**

Assert dry-run SQL revokes `CREATE`, `DROP`, `ALTER`, and `INDEX`; preserves `SELECT`, `INSERT`, `UPDATE`, and `DELETE`; never prints passwords; and targets only `stock_data` plus `stt_app@%`.

- [ ] **Step 2: Implement permission dry-run and apply modes**

The script defaults to `--dry-run`; mutation requires explicit `--apply`. It validates root connectivity, table presence, and `stt_app` connectivity before revoking DDL. If any prerequisite fails, it exits without changing grants.

- [ ] **Step 3: Run unit tests**

Run: `PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/pytest -q a-share-short-term-trading/tests/test_permission_script.py`

Expected: pass with no MySQL mutation.

- [ ] **Step 4: Apply migrations to the household MySQL**

Run:

```bash
PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/apply_migrations.py --apply
```

Expected: migrations `001` through `004` report success and version `1.1` exists.

- [ ] **Step 5: Apply least-privilege grants**

Run:

```bash
PYTHONPATH=a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/configure_mysql_permissions.py --apply
```

Expected: DDL grants are absent; runtime DML grants remain.

- [ ] **Step 6: Run final integration acceptance**

Run all phase-1 unit tests and integration tests. Then query `information_schema` to assert fifteen `stt_` tables, schema version `1.1`, broker columns, and exact `stt_app` grants. Perform one rollback-only object round trip for each repository.

Expected: zero failures and no persistent test rows.

- [ ] **Step 7: Update README and commit acceptance tooling**

Document dry-run/apply commands, root/runtime separation, rollback-only integration flags, and the fact that no scheduler or dashboard is installed.

```bash
git add a-share-short-term-trading/scripts/configure_mysql_permissions.py \
  a-share-short-term-trading/tests/test_permission_script.py \
  a-share-short-term-trading/tests/integration/test_mysql_permissions.py \
  a-share-short-term-trading/README.md
git commit -m "feat(stt): complete phase 1 foundation"
```

---

## Phase-1 Completion Gate

Phase 1 is complete only when:

- All ten v1.1 contracts reject invalid versions, fields, timezones, enum values, and cross-field states.
- All fifteen `stt_` tables and compatibility broker columns exist in household MySQL.
- Migrations run twice without failure or duplicate records.
- Every repository round-trips through a rollback-only integration test.
- The existing seventeen MVP tests remain green.
- Full brokerage facts survive conversion and MySQL persistence.
- `stt_app` can perform DML but cannot perform DDL.
- No phase-1 diff or test output contains a password, Cookie, full brokerage account, or personal holding fixture.
