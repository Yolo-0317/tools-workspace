# Stateful Advisor Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an append-only advisor decision ledger, enforce 3–5 trading-day decision cycles, turn broker position changes into durable memory, and backfill the verified recent closures without storing personal holdings in Git.

**Architecture:** A deterministic state machine owns action continuity and hard-event transitions. Broker synchronization compares the previous current-position projection with the new broker facts, appends idempotent position and decision events in the same MySQL transaction, then updates the mutable projection. AI receives the resulting memory context but cannot write state directly.

**Tech Stack:** Python 3.11, SQLAlchemy, MySQL 8, pytest, existing `stock_ai` and `scripts.tools.portfolio_db` modules.

## Global Constraints

- Decision cycles last 3–5 A-share trading days, not calendar days.
- Only the five approved hard-event classes may interrupt a cycle before its scheduled review.
- Event rows are append-only; corrections append a `CORRECTION` event.
- AI is an explanation layer and cannot directly change action or ledger state.
- Current broker facts, position projection, position event, and decision event update in one transaction.
- Zero-share broker rows create closure memory but do not remain active holdings.
- Unknown execution price, realized PnL, or historical rationale stays SQL `NULL`/`UNKNOWN`.
- No `.env`, account identifier, holding, share count, account amount, or personal decision record is committed to Git.
- Tests use only fictional symbols and values.

---

### Task 1: Add the advisor ledger schema and append-only guards

**Files:**
- Create: `../stock-mysql/sql/013_advisor_decision_ledger.sql`
- Create: `tests/unit/test_advisor_ledger_schema.py`

**Interfaces:**
- Produces MySQL tables `advisor_decision_cycles`, `advisor_decision_events`, and `portfolio_position_events`.
- Produces unique keys `uk_decision_event_fingerprint` and `uk_position_event_fingerprint`.
- Produces `BEFORE UPDATE` and `BEFORE DELETE` triggers for both event tables that `SIGNAL SQLSTATE '45000'`.

- [ ] **Step 1: Write the failing schema contract test**

```python
from pathlib import Path


SQL = (Path(__file__).resolve().parents[3] / "stock-mysql/sql/013_advisor_decision_ledger.sql")


def test_advisor_ledger_schema_is_append_only_and_idempotent() -> None:
    body = SQL.read_text(encoding="utf-8")
    for table in (
        "advisor_decision_cycles",
        "advisor_decision_events",
        "portfolio_position_events",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in body
    assert "uk_decision_event_fingerprint" in body
    assert "uk_position_event_fingerprint" in body
    assert body.count("BEFORE UPDATE") >= 2
    assert body.count("BEFORE DELETE") >= 2
    assert "SIGNAL SQLSTATE '45000'" in body
```

- [ ] **Step 2: Run the test and verify it fails because the migration does not exist**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_ledger_schema.py -q`

Expected: FAIL with `FileNotFoundError` for `013_advisor_decision_ledger.sql`.

- [ ] **Step 3: Write the migration**

Create the three tables with the columns and enums from the approved design. Use `CHAR(64)` fingerprints, nullable `cycle_id` on position events, JSON evidence fields, foreign keys from decision events to cycles, and indexes on `(ts_code, status)`, `(cycle_id, effective_trade_date)`, and `(ts_code, broker_captured_at)`. Create append-only triggers only on the two event tables; cycle rows remain mutable projections.

- [ ] **Step 4: Run the schema test**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_ledger_schema.py -q`

Expected: PASS.

- [ ] **Step 5: Apply the migration to the configured local MySQL and inspect the tables**

Run: `cd stock-mysql && mysql --defaults-extra-file=.my.cnf stock_data < sql/013_advisor_decision_ledger.sql`

Run: `mysql --defaults-extra-file=.my.cnf stock_data -e "SHOW TABLES LIKE '%advisor%'; SHOW TABLES LIKE 'portfolio_position_events';"`

Expected: all three tables exist. Do not print account or holding rows.

- [ ] **Step 6: Commit the schema task**

```bash
git add stock-mysql/sql/013_advisor_decision_ledger.sql stock-ai/tests/unit/test_advisor_ledger_schema.py
git commit -m "feat(stock-ai): add append-only advisor ledger schema"
```

### Task 2: Implement trading-day cycle state transitions

**Files:**
- Create: `stock_ai/advisor_memory/__init__.py`
- Create: `stock_ai/advisor_memory/models.py`
- Create: `stock_ai/advisor_memory/state_machine.py`
- Create: `tests/unit/test_advisor_memory_state_machine.py`

**Interfaces:**
- Produces `DecisionCycle`, `DecisionEventDraft`, `HardEvent`, `CycleStatus`, and `HardEventKind` dataclasses/enums.
- Produces `resolve_cycle_dates(start: date, trading_days: Sequence[date]) -> tuple[date, date]`.
- Produces `advance_cycle(cycle: DecisionCycle, *, as_of: date, hard_events: Sequence[HardEvent], extend_at_review: bool) -> CycleTransition`.

- [ ] **Step 1: Write failing tests for the approved cycle behavior**

```python
from datetime import date

from stock_ai.advisor_memory.models import DecisionCycle, CycleStatus, HardEvent, HardEventKind
from stock_ai.advisor_memory.state_machine import advance_cycle, resolve_cycle_dates


DAYS = tuple(date(2026, 8, day) for day in (10, 11, 12, 13, 14, 17))


def cycle() -> DecisionCycle:
    return DecisionCycle(
        cycle_id="cycle-1",
        code="600000",
        name="示例银行",
        started_trade_date=DAYS[0],
        review_trade_date=DAYS[2],
        expiry_trade_date=DAYS[4],
        initial_action="持有观察",
        current_action="持有观察",
        status=CycleStatus.ACTIVE,
    )


def test_cycle_dates_use_trading_days() -> None:
    assert resolve_cycle_dates(DAYS[0], DAYS) == (DAYS[2], DAYS[4])


def test_normal_day_cannot_change_action() -> None:
    out = advance_cycle(cycle(), as_of=DAYS[1], hard_events=(), extend_at_review=False)
    assert out.action == "持有观察"
    assert out.status is CycleStatus.ACTIVE
    assert out.event_type == "ACTION_MAINTAINED"


def test_review_day_can_extend_to_day_five() -> None:
    out = advance_cycle(cycle(), as_of=DAYS[2], hard_events=(), extend_at_review=True)
    assert out.status is CycleStatus.EXTENDED
    assert out.event_type == "CYCLE_EXTENDED"


def test_stop_loss_interrupts_before_review() -> None:
    event = HardEvent(HardEventKind.PRICE_TRIGGER, "退出观察", {"rule": "stop_loss"})
    out = advance_cycle(cycle(), as_of=DAYS[1], hard_events=(event,), extend_at_review=False)
    assert out.status is CycleStatus.INVALIDATED
    assert out.action == "退出观察"


def test_day_five_must_close() -> None:
    out = advance_cycle(cycle(), as_of=DAYS[4], hard_events=(), extend_at_review=True)
    assert out.status is CycleStatus.CLOSED
```

- [ ] **Step 2: Run the tests and verify imports fail**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_memory_state_machine.py -q`

Expected: FAIL with `ModuleNotFoundError: stock_ai.advisor_memory`.

- [ ] **Step 3: Implement the minimal domain models and pure state machine**

Map approved hard-event kinds to deterministic actions: price stop → `退出观察`; price target → `分批止盈`; position close → `已清仓`; position add/reduce → `仓位已变，重新评估`; trend breakdown → `降级观察`; effective breakout → `升级观察`; material company risk → `风险退出`; market/sector reversal → `降级观察`. Reject hard events outside the five approved classes.

- [ ] **Step 4: Run state-machine tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_memory_state_machine.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the state-machine task**

```bash
git add stock-ai/stock_ai/advisor_memory stock-ai/tests/unit/test_advisor_memory_state_machine.py
git commit -m "feat(stock-ai): add advisor decision cycle state machine"
```

### Task 3: Detect the five hard-event classes from structured facts

**Files:**
- Create: `stock_ai/advisor_memory/hard_events.py`
- Create: `tests/unit/test_advisor_hard_events.py`

**Interfaces:**
- Produces `HardEventInputs` with price, trigger plan, position deltas, trend flags, material-risk flag, and market/sector reversal flags.
- Produces `detect_hard_events(inputs: HardEventInputs) -> tuple[HardEvent, ...]`, where the tuple contains zero or more immutable `HardEvent` values.

- [ ] **Step 1: Write one failing test per hard-event class and one ordinary-noise test**

```python
def test_small_daily_move_is_not_a_hard_event() -> None:
    out = detect_hard_events(HardEventInputs(price=10.05, previous_price=10.0))
    assert out == ()


def test_position_close_is_a_hard_event() -> None:
    out = detect_hard_events(HardEventInputs(shares_before=500, shares_after=0))
    assert out[0].kind is HardEventKind.POSITION_CHANGE
    assert out[0].suggested_action == "已清仓"


def test_material_risk_is_a_hard_event() -> None:
    out = detect_hard_events(HardEventInputs(material_risk=True, material_risk_reasons=("监管立案",)))
    assert out[0].kind is HardEventKind.COMPANY_EVENT
    assert out[0].suggested_action == "风险退出"
```

Add equivalent focused tests for a configured price trigger, a trend structure flag, and a sector reversal flag.

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_hard_events.py -q`

Expected: FAIL because `hard_events.py` does not exist.

- [ ] **Step 3: Implement deterministic detection**

Do not infer company or market events from free text. Accept only structured booleans/reasons produced by existing news-impact and market-regime services. Include `observed_at`, source, and evidence in each event.

- [ ] **Step 4: Run the hard-event tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_hard_events.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the hard-event task**

```bash
git add stock-ai/stock_ai/advisor_memory/hard_events.py stock-ai/tests/unit/test_advisor_hard_events.py
git commit -m "feat(stock-ai): detect advisor hard events"
```

### Task 4: Add append-only repository and idempotent fingerprints

**Files:**
- Create: `stock_ai/advisor_memory/repository.py`
- Create: `tests/unit/test_advisor_memory_repository.py`

**Interfaces:**
- Produces `decision_event_fingerprint(cycle_id: str, event_type: str, effective_trade_date: date, action: str, evidence: Mapping[str, object]) -> str`.
- Produces `position_event_fingerprint(source: str, captured_at: datetime, code: str, shares_before: int, shares_after: int, event_type: str) -> str`.
- Produces `AdvisorLedgerRepository` methods `load_active_cycle`, `append_decision_event`, `append_position_event`, `open_cycle`, `apply_transition`, and `load_memory_context`.
- Every write method accepts an existing SQLAlchemy connection; it does not create its own transaction.

- [ ] **Step 1: Write failing fingerprint and duplicate-write tests**

```python
def test_position_fingerprint_is_stable_and_sensitive_to_delta() -> None:
    first = position_event_fingerprint("jywg", CAPTURED, "600000", 500, 0, "CLOSED")
    again = position_event_fingerprint("jywg", CAPTURED, "600000", 500, 0, "CLOSED")
    different = position_event_fingerprint("jywg", CAPTURED, "600000", 500, 200, "REDUCED")
    assert first == again
    assert first != different


def test_duplicate_position_event_is_noop(fake_connection) -> None:
    repo = AdvisorLedgerRepository(fake_connection)
    assert repo.append_position_event(EVENT) is True
    assert repo.append_position_event(EVENT) is False
```

Use a small recording fake connection that emulates unique-fingerprint duplicate results; do not mock the domain functions.

- [ ] **Step 2: Run and verify missing repository symbols**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_memory_repository.py -q`

Expected: FAIL on missing imports.

- [ ] **Step 3: Implement canonical JSON hashing and repository SQL**

Use SHA-256 over UTF-8 canonical JSON (`sort_keys=True`, compact separators). Use `INSERT IGNORE` only for fingerprinted event inserts; cycle projection updates remain explicit and must verify one affected row.

- [ ] **Step 4: Run repository tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_memory_repository.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the repository task**

```bash
git add stock-ai/stock_ai/advisor_memory/repository.py stock-ai/tests/unit/test_advisor_memory_repository.py
git commit -m "feat(stock-ai): add advisor ledger repository"
```

### Task 5: Make broker synchronization generate position memory atomically

**Files:**
- Create: `stock_ai/advisor_memory/position_sync.py`
- Modify: `scripts/tools/portfolio_db.py`
- Modify: `scripts/tools/jywg_portfolio_sync.py`
- Modify: `tests/unit/test_jywg_portfolio_sync.py`
- Create: `tests/unit/test_advisor_position_sync.py`

**Interfaces:**
- Produces `diff_position_facts(previous: Mapping[str, PositionProjection], incoming: Sequence[BrokerPosition]) -> tuple[PositionEventDraft, ...]`, returning zero or more immutable drafts.
- Produces `sync_broker_facts_with_memory(positions, account, *, source: str, engine: Engine) -> dict[str, int]`.
- Changes `_sync_broker_facts_with_connection` so incoming rows with `shares == 0` are persisted as inactive projections.

- [ ] **Step 1: Add failing zero-share and transition tests**

```python
def test_positive_to_zero_creates_one_close_event() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500, cost="6.80")},
        [broker_position(shares=0, cost="0")],
    )
    assert [(event.event_type, event.shares_before, event.shares_after)] == [("CLOSED", 500, 0)]


def test_zero_share_row_is_not_active_after_sync(recording_connection) -> None:
    sync_broker_facts_with_memory([broker_position(shares=0)], ACCOUNT, source="jywg", engine=engine(recording_connection))
    assert recording_connection.last_position_active_value("600000") == 0


def test_repeat_capture_does_not_duplicate_close_event(recording_connection) -> None:
    sync_once(recording_connection)
    sync_once(recording_connection)
    assert recording_connection.position_event_count("CLOSED") == 1
```

- [ ] **Step 2: Run and verify failures reproduce the current zero-share bug**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_jywg_portfolio_sync.py tests/unit/test_advisor_position_sync.py -q`

Expected: at least the zero-share-active assertion FAILS before implementation.

- [ ] **Step 3: Implement transaction orchestration**

Within one `engine.begin()` block: lock current projections with `SELECT ts_code, name, shares, cost_price, broker_captured_at FROM portfolio_positions FOR UPDATE`, compute events, append position and decision events, close a linked cycle for `CLOSED`, then call `sync_broker_positions_and_account(positions, account, source=source, connection=conn)`. Count active positions separately from broker rows in returned stats.

- [ ] **Step 4: Run focused broker and memory tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_jywg_portfolio_sync.py tests/unit/test_advisor_position_sync.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the broker-memory task**

```bash
git add stock-ai/stock_ai/advisor_memory/position_sync.py stock-ai/scripts/tools/portfolio_db.py stock-ai/scripts/tools/jywg_portfolio_sync.py stock-ai/tests/unit/test_jywg_portfolio_sync.py stock-ai/tests/unit/test_advisor_position_sync.py
git commit -m "feat(stock-ai): persist broker position changes as memory"
```

### Task 6: Constrain holdings diagnosis with active decision memory

**Files:**
- Create: `stock_ai/advisor_memory/diagnosis.py`
- Modify: `scripts/analysis/analyze_holdings_v2.py`
- Modify: `scripts/tools/decision_context.py`
- Create: `tests/unit/test_advisor_memory_diagnosis.py`
- Modify: `tests/unit/test_diagnosis_news_prompt.py`

**Interfaces:**
- Produces `prepare_diagnosis(code, *, as_of, facts, repository) -> DiagnosisDecision`.
- Produces `format_memory_context(decision: DiagnosisDecision) -> str`.
- `DiagnosisDecision` exposes `cycle_day`, `next_review_date`, `previous_action`, `locked_action`, `relation`, `position_change`, `hard_events`, and `allowed_actions`.

- [ ] **Step 1: Write failing continuity and prompt tests**

```python
def test_diagnosis_keeps_action_without_hard_event(active_cycle, repo) -> None:
    out = prepare_diagnosis("600000", as_of=DAY_2, facts=ordinary_facts(), repository=repo)
    assert out.locked_action == active_cycle.current_action
    assert out.relation == "维持"


def test_prompt_contains_memory_and_cannot_delegate_action_to_ai() -> None:
    prompt = format_memory_context(DECISION)
    assert "当前周期第2/5日" in prompt
    assert "锁定动作：持有观察" in prompt
    assert "不得提出锁定集合之外的动作" in prompt
```

- [ ] **Step 2: Run and verify missing diagnosis coordinator failure**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_memory_diagnosis.py tests/unit/test_diagnosis_news_prompt.py -q`

Expected: FAIL on missing coordinator/signature.

- [ ] **Step 3: Implement the coordinator and deterministic report header**

Generate the report's operation line in Python from `locked_action`; the LLM response begins at “新增证据与路径分析”. If AI text contains a conflicting action phrase, append `AI_ACTION_REJECTED`, discard the conflicting line, and retain the state-machine action.

- [ ] **Step 4: Run focused diagnosis tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_memory_diagnosis.py tests/unit/test_diagnosis_news_prompt.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the diagnosis task**

```bash
git add stock-ai/stock_ai/advisor_memory/diagnosis.py stock-ai/scripts/analysis/analyze_holdings_v2.py stock-ai/scripts/tools/decision_context.py stock-ai/tests/unit/test_advisor_memory_diagnosis.py stock-ai/tests/unit/test_diagnosis_news_prompt.py
git commit -m "feat(stock-ai): constrain diagnosis with decision memory"
```

### Task 7: Add safe historical backfill and record the verified closures

**Files:**
- Create: `scripts/analysis/backfill_advisor_memory.py`
- Create: `tests/unit/test_backfill_advisor_memory.py`
- Modify: `docs/CAPABILITIES.md`

**Interfaces:**
- CLI flags: `--from-date YYYY-MM-DD`, `--to-date YYYY-MM-DD`, `--dry-run`, and `--apply`.
- Dry-run returns proposed event fingerprints and counts without printing personal rows unless `--verbose` is explicitly supplied.
- Apply mode only inserts missing events; it never updates event rows.

- [ ] **Step 1: Write failing backfill reconstruction tests**

```python
def test_backfill_reconstructs_close_from_last_positive_snapshot() -> None:
    proposed = reconstruct_events(
        prior_snapshots=[snapshot("600000", shares=500, cost="6.80")],
        broker_rows=[broker_row("600000", shares=0)],
    )
    assert proposed[0].event_type == "CLOSED"
    assert proposed[0].execution_price is None
    assert proposed[0].plan_compliance == "UNKNOWN"


def test_backfill_does_not_invent_missing_decision() -> None:
    cycle = recover_or_create_cycle(history=(), position_event=CLOSE_EVENT)
    assert cycle.source == "LEGACY_IMPORT"
    assert cycle.current_action == "UNKNOWN"
    assert cycle.status == "CLOSED"
```

- [ ] **Step 2: Run and verify missing CLI/module failure**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_backfill_advisor_memory.py -q`

Expected: FAIL because the backfill module does not exist.

- [ ] **Step 3: Implement read-only reconstruction and idempotent apply**

Read prior `portfolio_positions_daily`, current/inactive `portfolio_positions`, and any recoverable historical diagnosis rows. Keep execution price and realized PnL null unless a broker transaction source explicitly supplies them. Do not read or commit `output/jywg_positions_latest.json` as a required source.

- [ ] **Step 4: Run unit tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_backfill_advisor_memory.py -q`

Expected: PASS.

- [ ] **Step 5: Dry-run the runtime backfill**

Run: `cd stock-ai && .venv/bin/python -m scripts.analysis.backfill_advisor_memory --from-date 2026-08-12 --to-date 2026-08-13 --dry-run`

Expected: reports four proposed `CLOSED` events, zero invented execution prices, and no mutation.

- [ ] **Step 6: Apply twice and verify idempotency**

Run: `cd stock-ai && .venv/bin/python -m scripts.analysis.backfill_advisor_memory --from-date 2026-08-12 --to-date 2026-08-13 --apply`

Run the same command again.

Expected: first run inserts four position events and corresponding closure decision events; second run inserts zero events. Query counts and fingerprints only in logs; do not print personal rows in committed artifacts.

- [ ] **Step 7: Commit the backfill task**

```bash
git add stock-ai/scripts/analysis/backfill_advisor_memory.py stock-ai/tests/unit/test_backfill_advisor_memory.py stock-ai/docs/CAPABILITIES.md
git commit -m "feat(stock-ai): backfill advisor position memory"
```

### Task 8: Run complete verification and document operations

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md`
- Modify: `stock-ai/docs/SCHEDULING.md`

**Interfaces:**
- Documents cycle behavior, five hard events, append-only correction workflow, broker sync semantics, and backfill command.

- [ ] **Step 1: Add operational documentation**

Document that normal daily diagnosis maintains the current action, day 3 is scheduled review, day 5 is forced closure, and broker sync is the authority for position facts.

- [ ] **Step 2: Run the focused suite**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_ledger_schema.py tests/unit/test_advisor_memory_state_machine.py tests/unit/test_advisor_hard_events.py tests/unit/test_advisor_memory_repository.py tests/unit/test_advisor_position_sync.py tests/unit/test_advisor_memory_diagnosis.py tests/unit/test_backfill_advisor_memory.py tests/unit/test_jywg_portfolio_sync.py tests/unit/test_diagnosis_news_prompt.py -q`

Expected: all tests PASS with no warnings caused by this feature.

- [ ] **Step 3: Run relevant existing advisor tests**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_selection.py tests/unit/test_advisor_weekly_review.py tests/unit/test_limit_up_replay.py -q`

Expected: all tests PASS.

- [ ] **Step 4: Run a dry broker sync against a fictional fixture**

Run: `cd stock-ai && .venv/bin/pytest tests/unit/test_advisor_position_sync.py::test_repeat_capture_does_not_duplicate_close_event -q`

Expected: PASS and exactly one close event.

- [ ] **Step 5: Review the diff for private data**

Run: `git diff --check && git diff --name-only && git diff -- stock-ai stock-mysql`

Expected: manual diff review confirms that no account identifiers, real holding rows, share counts, account amounts, or personal decision events were introduced. Existing unrelated work must not be changed.

- [ ] **Step 6: Commit documentation**

```bash
git add stock-ai/docs/CAPABILITIES.md stock-ai/docs/SCHEDULING.md
git commit -m "docs(stock-ai): document stateful advisor memory"
```
