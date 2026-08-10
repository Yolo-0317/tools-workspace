# Session-Aware Stock Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one stock-diagnosis entry point that identifies A-share pre-market, active intraday, midday break, post-market, or non-trading-day state and returns a conclusion constrained to that state.

**Architecture:** Extend the existing `stock_ai.trading_calendar` with a strict tri-state lookup while preserving its legacy weekday fallback API. Keep time classification in a pure `short_term_trading.session` module, route existing EOD and intraday decisions through a pure `session_diagnosis` policy layer, and place MySQL/OpenCLI wiring plus Chinese rendering in one CLI entry point.

**Tech Stack:** Python 3.10+, `zoneinfo`, dataclasses/enums, existing Tushare calendar cache, existing MySQL repositories, existing EOD/intraday engines, pytest 9.

## Global Constraints

- Use `Asia/Shanghai` for session boundaries; internal timestamps remain timezone-aware UTC.
- Session boundaries are exact: 09:30, 11:30, 13:00, and 15:00, using left-closed/right-open ranges.
- A weekday with unknown SSE calendar state is not assumed open; it degrades to a non-actionable diagnosis.
- Only active continuous-auction intervals can expose a computed `BUY_ALLOWED`; shadow mode remains `actionable=false` and renders `NO_TRADE` as the main signal.
- Pre-market, midday break, post-market, and non-trading day never produce actionable `BUY_ALLOWED`.
- Non-intraday prices are labelled as completed-session close data, never as current price.
- No scheduler, dashboard, push notification, or broker order action is added.
- No `.env`, password, Cookie, brokerage account, personal holding fixture, or browser session enters Git.
- Preserve unrelated workspace changes and stage only files named by the active task.

---

## File Structure

- Modify `stock-ai/stock_ai/trading_calendar.py` to expose strict tri-state calendar lookups and confirmed previous/next trading dates without changing existing callers.
- Modify `stock-ai/tests/unit/test_trading_calendar.py` for strict cached-open, cached-closed, unknown, previous, and next date behavior.
- Create `a-share-short-term-trading/short_term_trading/session.py` for pure session classification and calendar protocol definitions.
- Create `a-share-short-term-trading/tests/test_session.py` for all time boundaries and calendar-degradation behavior.
- Create `a-share-short-term-trading/short_term_trading/session_diagnosis.py` for unified result contracts, routing, signal policy, and Chinese rendering.
- Create `a-share-short-term-trading/tests/test_session_diagnosis.py` for routing and conclusion enforcement.
- Create `a-share-short-term-trading/short_term_trading/diagnosis_runtime.py` for existing MySQL/OpenCLI adapter composition.
- Create `a-share-short-term-trading/scripts/diagnose_stock.py` as the single CLI/chat entry point.
- Create `a-share-short-term-trading/tests/test_diagnose_stock_cli.py` for safe CLI behavior without external calls.
- Modify `a-share-short-term-trading/README.md` to document the one-command diagnosis flow and four user-visible states.

---

### Task 1: Strict Trading Calendar and Pure Session Classification

**Files:**
- Modify: `stock-ai/stock_ai/trading_calendar.py`
- Modify: `stock-ai/tests/unit/test_trading_calendar.py`
- Create: `a-share-short-term-trading/short_term_trading/session.py`
- Test: `a-share-short-term-trading/tests/test_session.py`

**Interfaces:**
- Produces: `trading_day_status(d: date, *, refresh: bool = True) -> bool | None`.
- Produces: `latest_confirmed_a_share_trade_date(on_or_before: date) -> date | None`.
- Produces: `next_confirmed_a_share_trade_date(on_or_after: date) -> date | None`.
- Produces: `TradingSession`, `TradingCalendar` protocol, `TradingSessionContext`, and `classify_trading_session(now: datetime, calendar: TradingCalendar) -> TradingSessionContext`.
- Consumers: Task 2 policy router and Task 3 runtime adapter.

- [ ] **Step 1: Write failing strict-calendar tests**

Add tests that distinguish “cached closed” from “unknown” and never silently treat an unknown weekday as open:

```python
def test_strict_status_returns_none_when_refresh_cannot_resolve(monkeypatch, trade_cal_cache) -> None:
    monkeypatch.setattr("stock_ai.trading_calendar.refresh_trade_cal_cache", lambda *args: 0)
    assert trading_day_status(date(2026, 8, 10)) is None


def test_confirmed_dates_stop_at_an_unknown_calendar_day(monkeypatch, trade_cal_cache) -> None:
    trade_cal_cache.write_text(
        json.dumps({"days": {"2026-08-07": 1}}), encoding="utf-8"
    )
    monkeypatch.setattr("stock_ai.trading_calendar.refresh_trade_cal_cache", lambda *args: 0)
    assert latest_confirmed_a_share_trade_date(date(2026, 8, 10)) is None
```

- [ ] **Step 2: Run the calendar tests and confirm red state**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
  stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_trading_calendar.py
```

Expected: import failure for the three strict functions.

- [ ] **Step 3: Implement strict calendar functions without changing legacy behavior**

Use cache-first tri-state behavior:

```python
def trading_day_status(d: date, *, refresh: bool = True) -> bool | None:
    if d.weekday() >= 5:
        return False
    flag = _lookup_cached(d)
    if flag is None and refresh:
        refresh_trade_cal_cache(date(d.year, 1, 1), date(d.year, 12, 31))
        flag = _lookup_cached(d)
    return None if flag is None else flag == 1
```

Keep `is_a_share_trading_day()` backward compatible by mapping `None` to the current weekday fallback. The two confirmed-date helpers iterate at most 366 days but return `None` immediately when an intervening weekday is unknown, because skipping it could select the wrong trading date.

- [ ] **Step 4: Write failing session-boundary tests**

Create a fake calendar with explicit status and dates. Cover the exact local times:

```python
@pytest.mark.parametrize(
    ("clock", "expected"),
    [
        (time(9, 29, 59), TradingSession.PRE_MARKET),
        (time(9, 30), TradingSession.INTRADAY),
        (time(11, 29, 59), TradingSession.INTRADAY),
        (time(11, 30), TradingSession.MIDDAY_BREAK),
        (time(12, 59, 59), TradingSession.MIDDAY_BREAK),
        (time(13, 0), TradingSession.INTRADAY),
        (time(14, 59, 59), TradingSession.INTRADAY),
        (time(15, 0), TradingSession.POST_MARKET),
    ],
)
def test_trading_session_boundaries(clock: time, expected: TradingSession) -> None:
    context = classify_trading_session(shanghai_datetime(clock), OpenCalendar())
    assert context.session is expected
```

Also assert that a naive datetime raises `ValueError`, a cached holiday returns `NON_TRADING_DAY`, and unknown calendar status returns `NON_TRADING_DAY` with `calendar_confirmed=False`.

- [ ] **Step 5: Run session tests and confirm red state**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading \
  stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/test_session.py
```

Expected: import failure because `short_term_trading.session` is absent.

- [ ] **Step 6: Implement the pure classifier**

Define:

```python
class TradingSession(str, Enum):
    PRE_MARKET = "PRE_MARKET"
    INTRADAY = "INTRADAY"
    MIDDAY_BREAK = "MIDDAY_BREAK"
    POST_MARKET = "POST_MARKET"
    NON_TRADING_DAY = "NON_TRADING_DAY"


class TradingCalendar(Protocol):
    def status(self, value: date) -> bool | None:
        raise NotImplementedError

    def latest_on_or_before(self, value: date) -> date | None:
        raise NotImplementedError

    def next_on_or_after(self, value: date) -> date | None:
        raise NotImplementedError


@dataclass(frozen=True)
class TradingSessionContext:
    session: TradingSession
    now_utc: datetime
    local_now: datetime
    calendar_confirmed: bool
    diagnosis_trade_date: date | None
    next_trade_date: date | None
    reason: str
```

`classify_trading_session` converts an aware input to Shanghai time, asks the calendar once for the local date, and derives completed/next trading dates. Unknown status uses `NON_TRADING_DAY`, `calendar_confirmed=False`, and an explicit safe-degradation reason.

- [ ] **Step 7: Run Task 1 tests and commit**

Run both test files, then:

```bash
git add stock-ai/stock_ai/trading_calendar.py \
  stock-ai/tests/unit/test_trading_calendar.py \
  a-share-short-term-trading/short_term_trading/session.py \
  a-share-short-term-trading/tests/test_session.py
git commit -m "feat(stt): classify A-share trading sessions"
```

---

### Task 2: Unified Diagnosis Routing and Signal Policy

**Files:**
- Create: `a-share-short-term-trading/short_term_trading/session_diagnosis.py`
- Test: `a-share-short-term-trading/tests/test_session_diagnosis.py`

**Interfaces:**
- Consumes: `TradingSessionContext`, legacy `TradePlanDraft`, legacy `IntradayDecision`, and `ReleaseMode`.
- Produces: `diagnose_for_session(code: str, context: TradingSessionContext, *, static_diagnose: Callable[[str, TradingSessionContext], TradePlanDraft], intraday_diagnose: Callable[[str, TradingSessionContext], IntradayDecision] | None = None, is_holding: bool = False, release_mode: ReleaseMode = ReleaseMode.SHADOW) -> SessionAwareDiagnosis`.
- Produces: `render_session_diagnosis(result: SessionAwareDiagnosis) -> str`.
- Consumers: Task 3 runtime composition and CLI.

- [ ] **Step 1: Write failing routing tests**

Use real `TradePlanDraft` and `IntradayDecision` fixtures, with simple recording callables. Assert:

```python
def test_pre_market_uses_static_diagnosis_and_never_intraday() -> None:
    result = diagnose_for_session(
        "600000", pre_market_context(),
        static_diagnose=static_handler,
        intraday_diagnose=intraday_handler,
    )
    assert calls == ["static"]
    assert result.signal == "WAIT_ENTRY"
    assert result.actionable is False


def test_active_intraday_uses_intraday_diagnosis() -> None:
    result = diagnose_for_session(
        "600000", intraday_context(),
        static_diagnose=static_handler,
        intraday_diagnose=intraday_handler,
        release_mode=ReleaseMode.LIVE,
    )
    assert calls == ["intraday"]
    assert result.signal == "BUY_ALLOWED"
    assert result.actionable is True
```

Add independent cases for `MIDDAY_BREAK`, `POST_MARKET`, and `NON_TRADING_DAY`.

- [ ] **Step 2: Run routing tests and confirm red state**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading \
  stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/test_session_diagnosis.py
```

Expected: import failure for `session_diagnosis`.

- [ ] **Step 3: Write failing signal-policy tests**

Cover these observable policies:

```python
def test_shadow_buy_renders_no_trade_but_preserves_computed_signal() -> None:
    result = diagnose_for_session(
        "600000",
        intraday_context(),
        static_diagnose=static_handler,
        intraday_diagnose=buy_allowed_handler,
        release_mode=ReleaseMode.SHADOW,
    )
    assert result.signal == "NO_TRADE"
    assert result.computed_signal == "BUY_ALLOWED"
    assert result.actionable is False


@pytest.mark.parametrize("session", [
    TradingSession.PRE_MARKET,
    TradingSession.MIDDAY_BREAK,
    TradingSession.POST_MARKET,
    TradingSession.NON_TRADING_DAY,
])
def test_closed_session_suppresses_buy_allowed(session: TradingSession) -> None:
    result = diagnose_for_session(
        "600000",
        context_for(session),
        static_diagnose=buy_like_static_handler,
        intraday_diagnose=buy_allowed_handler,
        release_mode=ReleaseMode.LIVE,
    )
    assert result.signal != "BUY_ALLOWED"
    assert result.actionable is False
```

Also assert that an unknown calendar reason remains visible and that a missing intraday handler returns `NO_TRADE` instead of raising.

- [ ] **Step 4: Implement the unified result and routing policy**

Define an immutable result:

```python
@dataclass(frozen=True)
class SessionAwareDiagnosis:
    code: str
    session: TradingSession
    session_label: str
    as_of: str
    diagnosis_trade_date: str | None
    quote_as_of: str | None
    data_label: str
    signal: str
    computed_signal: str
    actionable: bool
    reason: str
    next_action: str
    details: dict[str, object]
```

`diagnose_for_session` calls the intraday handler only for `INTRADAY` and `MIDDAY_BREAK`; midday results are always non-actionable and a computed buy becomes `WAIT_ENTRY`. All other sessions call the static handler. `NON_TRADING_DAY` forces a non-holding entry conclusion to `NO_TRADE`. `SHADOW` converts an intraday computed buy to the user-visible `NO_TRADE` while retaining `computed_signal="BUY_ALLOWED"`.

- [ ] **Step 5: Write failing renderer tests**

Verify the card has exactly one main conclusion and correct price wording:

```python
def test_non_trading_day_renderer_labels_completed_close() -> None:
    text = render_session_diagnosis(non_trading_result())
    assert "非交易日" in text
    assert "最近交易日收盘" in text
    assert "现价" not in text
    assert "主结论：NO_TRADE" in text
```

- [ ] **Step 6: Implement Chinese rendering and run Task 2 tests**

Render five concise lines: current state, data basis, main conclusion, reason, and next action. Do not render `computed_signal` as a second main conclusion; for shadow hits include it in the reason line as “影子规则命中，仅用于验证”.

Run the Task 2 test file, all contract tests, and existing diagnosis/intraday tests. Commit:

```bash
git add a-share-short-term-trading/short_term_trading/session_diagnosis.py \
  a-share-short-term-trading/tests/test_session_diagnosis.py
git commit -m "feat(stt): route diagnosis by trading session"
```

---

### Task 3: Runtime Composition and Single Diagnosis CLI

**Files:**
- Create: `a-share-short-term-trading/short_term_trading/diagnosis_runtime.py`
- Create: `a-share-short-term-trading/scripts/diagnose_stock.py`
- Test: `a-share-short-term-trading/tests/test_diagnose_stock_cli.py`
- Modify: `a-share-short-term-trading/README.md`

**Interfaces:**
- Consumes: Task 1 calendar/session APIs, Task 2 router/renderer, `SqlAlchemyDailyBarRepository`, `SqlAlchemyEvidenceRepository`, `build_eod_trade_plan`, and `verify_intraday_plan`.
- Produces: `StockAiTradingCalendar` and `DiagnosisRuntime`.
- Produces: `build_runtime_diagnosis(code: str, runtime: DiagnosisRuntime, *, now: datetime, release_mode: ReleaseMode, is_holding: bool = False) -> SessionAwareDiagnosis`.
- Produces: CLI `diagnose_stock.py --code CODE [--output text|json]`.
- Consumers: chat-triggered individual-stock diagnosis.

- [ ] **Step 1: Write failing runtime composition tests**

Use injected fake repositories and collectors; do not mock the router itself. Test:

- Pre-market does not call the intraday collector and uses the latest confirmed completed date.
- Active intraday refreshes quote/fund evidence once before verification.
- Missing frozen plan safely returns `NO_TRADE` with `failed_gates=["plan"]`.
- Midday does not refresh external evidence and tells the user to retry after 13:00.
- Post-market uses today only when a complete daily bar exists; otherwise it labels the latest completed date.
- Unknown calendar status never calls OpenCLI.

- [ ] **Step 2: Run runtime tests and confirm red state**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading:stock-ai \
  stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/test_diagnose_stock_cli.py
```

Expected: imports fail because the runtime and CLI do not exist.

- [ ] **Step 3: Implement the strict calendar adapter and runtime**

`StockAiTradingCalendar` maps the strict functions from Task 1 to the `TradingCalendar` protocol. `DiagnosisRuntime` accepts repositories and an optional intraday refresh callable so tests and chat orchestration can inject them.

The static path invokes:

```python
build_eod_trade_plan(
    code,
    daily_repository.get_recent_bars(code, 120),
    evidence_repository.get_latest_valid_snapshot(code, "chip"),
    profile=risk_profile,
    now=context.now_utc,
)
```

The active intraday path refreshes quote/fund evidence, then calls `verify_intraday_plan` with the frozen plan and persisted quote, fund-flow, sector, chip, and last-five-minute order-book snapshots. If the frozen plan or risk gate is unavailable, construct a deterministic `NO_TRADE` decision; never infer approval.

- [ ] **Step 4: Implement the single CLI**

The CLI loads `stock-ai/.env` without printing it, inserts both project roots into `sys.path`, and accepts:

```text
--code CODE                  required
--output text|json           default text
--plan-json PATH             optional frozen legacy plan
--market-status ALLOW|LIMITED|FREEZE   default FREEZE
--maximum-shares N           default 0
--portfolio-approved         default false
--is-holding                 default false
--release-mode SHADOW|LIVE   default SHADOW
--no-intraday-refresh        test/manual fallback
--at ISO8601                 deterministic test override; must contain timezone
```

The command automatically selects the session; there is no `--session` switch. A missing MySQL URL produces a JSON/text `NO_TRADE` conclusion without echoing configuration.

- [ ] **Step 5: Verify CLI behavior without external calls**

Use a temporary calendar cache and `--at` values for pre-market, midday, post-market, and holiday cases. Run the CLI through its `main(argv)` function with injected runtime dependencies so unit tests never contact MySQL/OpenCLI.

Assert JSON has one `signal`, contains `session`, `data_label`, `actionable`, and `next_action`, and unknown arguments exit 2 without leaking environment values.

- [ ] **Step 6: Update README and run regression tests**

Document:

```bash
PYTHONPATH=a-share-short-term-trading:stock-ai \
  stock-ai/.venv/bin/python a-share-short-term-trading/scripts/diagnose_stock.py \
  --code 600000
```

Explain that the command determines the session automatically, midday is non-actionable, non-trading days use the latest confirmed close, and the default release mode is `SHADOW`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading:stock-ai \
  stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests \
  stock-ai/tests/unit/test_trading_calendar.py \
  stock-ai/tests/unit/test_jywg_portfolio_sync.py
```

- [ ] **Step 7: Run household MySQL rollback acceptance**

Run all existing integration tests with `STT_MYSQL_INTEGRATION=1`, then execute one read-only CLI diagnosis in a non-actionable state. Verify no `stt_*` test rows remain, no DDL grant returns to `stt_app`, and no output contains a password, URL, Cookie, or account identifier.

- [ ] **Step 8: Commit runtime and documentation**

```bash
git add a-share-short-term-trading/short_term_trading/diagnosis_runtime.py \
  a-share-short-term-trading/scripts/diagnose_stock.py \
  a-share-short-term-trading/tests/test_diagnose_stock_cli.py \
  a-share-short-term-trading/README.md
git commit -m "feat(stt): add session-aware diagnosis entry point"
```

---

## Completion Gate

The feature is complete only when:

- Every boundary from 09:29:59 through 15:00 maps to the specified state.
- A cached weekday holiday is `NON_TRADING_DAY` and an unknown weekday safely degrades without OpenCLI access.
- Pre-market, midday break, post-market, and non-trading day cannot expose actionable `BUY_ALLOWED`.
- Active intraday can compute `BUY_ALLOWED`, while default shadow mode renders one `NO_TRADE` main conclusion.
- Non-intraday output labels prices as completed-session close data and never as current price.
- The one CLI command selects the session without user input and always returns a conclusion.
- Existing contract, diagnosis, intraday, repository, migration, permission, and brokerage tests remain green.
- Household MySQL tests roll back completely and `stt_app` retains DML-only grants.
- The staged diff and command output contain no credential, Cookie, full account identifier, or personal holding data.
