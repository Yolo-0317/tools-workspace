# QClaw Shareable A-Share Diagnosis Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained QClaw/OpenClaw Skill that diagnoses one A-share stock with optional manually supplied holdings and no MySQL, credentials, broker session, or workspace dependency.

**Architecture:** The Skill is an independently runnable Python package under `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/`. Deterministic modules validate public market data, classify the Shanghai trading session, compute indicators and an estimated CYQ distribution, then produce one versioned JSON result that QClaw renders without changing its numbers or decision.

**Tech Stack:** Python 3.10+ standard library, `unittest`, `urllib.request`, `zoneinfo`, QClaw/OpenClaw `SKILL.md`, Eastmoney public quote/K-line/search endpoints, bundled SSE calendar snapshot.

## Global Constraints

- Runtime code uses Python 3.10+ standard library only; no pandas, SQLAlchemy, PyMySQL, Tushare, OpenCLI, API key, `.env`, or MySQL.
- The Skill never reads broker pages, browser cookies, QClaw memories, credentials, or account files.
- The Skill never stores holding inputs, diagnosis results, or conversations; only public symbol metadata and completed daily bars may be cached.
- All timestamps use `Asia/Shanghai`; a weekday is not assumed to be a trading day when the calendar is unknown.
- CYQ values are deterministic estimates based on price, volume, and turnover decay, not exchange-disclosed investor costs.
- Every decision has `actionable: false`; the Skill never submits orders, schedules jobs, sends messages, or promises returns.
- All production behavior follows red-green-refactor TDD, and each task commits only its scoped files.
- Preserve unrelated WeChat assets and all other existing dirty workspace files.

---

## File Structure

Create the following isolated tree:

```text
a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/
├── .gitignore
├── README.md
├── SKILL.md
├── data/
│   └── sse_trade_calendar_2026.json
├── scripts/
│   ├── diagnose.py
│   └── package_skill.py
├── a_share_stock_diagnosis/
│   ├── __init__.py
│   ├── cache.py
│   ├── calendar.py
│   ├── chip.py
│   ├── cli.py
│   ├── decision.py
│   ├── eastmoney.py
│   ├── indicators.py
│   ├── models.py
│   ├── session.py
│   └── validation.py
└── tests/
    ├── fixtures/
    │   ├── daily_603011.json
    │   ├── quote_603011.json
    │   ├── search_ambiguous.json
    │   └── search_unique.json
    ├── test_calendar_session.py
    ├── test_cli.py
    ├── test_decision.py
    ├── test_eastmoney.py
    ├── test_indicators_chip.py
    ├── test_models_validation.py
    └── test_online.py
```

Each module has one responsibility: `models` defines immutable contracts; `validation` validates symbols and holding inputs; `calendar` reads the bundled SSE snapshot; `session` classifies time; `cache` stores only public data; `eastmoney` performs and validates HTTP access; `indicators` and `chip` perform pure calculations; `decision` applies the rules; `cli` orchestrates and serializes; wrapper scripts expose installation-neutral commands.

---

### Task 1: Independent Contracts and Input Validation

**Files:**
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/__init__.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/models.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/validation.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/test_models_validation.py`

**Interfaces:**
- Produces immutable `DailyBar`, `Quote`, `Security`, `HoldingInput`, `ChipMetrics`, `SessionContext`, and `DiagnosisResult` dataclasses.
- Produces `normalize_code(value: str) -> str`, `market_for_code(code: str) -> str`, and `validate_holding(shares: int | None, cost_price: float | None, available_shares: int | None) -> HoldingInput | None`.
- `DiagnosisResult` explicitly contains `schema_version`, `symbol`, `name`, `session`, `as_of`, `diagnosis_trade_date`, `data_freshness`, `quote`, `latest_bar`, `indicators`, `chip_estimate`, `decision`, `actionable`, `reason`, `next_action`, `levels`, `holding`, `warnings`, `source_refs`, and `errors`.
- `DiagnosisResult.to_dict() -> dict[str, object]` recursively emits JSON-compatible dates and datetimes.

- [ ] **Step 1: Write failing validation tests**

Add exact tests for `603011`, `sh603011`, and `603011.SH`; reject non-six-digit symbols and unsupported prefixes. Assert that no holding values returns `None`, shares plus cost accepts unknown available shares, a partial holding rejects missing shares or cost, and available shares outside `0..shares` rejects.

```python
def test_holding_accepts_unknown_available_shares(self):
    value = validate_holding(500, 22.75, None)
    self.assertEqual(value.shares, 500)
    self.assertEqual(value.cost_price, 22.75)
    self.assertIsNone(value.available_shares)

def test_partial_holding_is_rejected(self):
    with self.assertRaisesRegex(ValueError, "shares.*cost_price"):
        validate_holding(500, None, None)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run from the Skill root:

```bash
python3 -m unittest -v tests.test_models_validation
```

Expected: import failure because the package does not exist.

- [ ] **Step 3: Implement the minimal contracts and validators**

Use frozen dataclasses. `normalize_code` strips a single `sh`/`sz` prefix or `.SH`/`.SZ` suffix, then requires exactly six digits. Support Shanghai `60/68` and Shenzhen `00/30` common-stock prefixes; reject indices, funds, Beijing securities, and ambiguous types in v1. Validate finite positive prices with `math.isfinite`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Task 1 test module and `python3 -m compileall -q a_share_stock_diagnosis`; both exit 0.

- [ ] **Step 5: Commit Task 1**

```bash
git add a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis \
  a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/test_models_validation.py
git commit -m "feat(stt-share): define portable diagnosis contracts"
```

### Task 2: Strict SSE Calendar and Session Classification

**Files:**
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/data/sse_trade_calendar_2026.json`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/calendar.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/session.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/test_calendar_session.py`

**Interfaces:**
- Produces `BundledTradingCalendar.load(path: Path) -> BundledTradingCalendar`.
- Produces `status(value: date) -> bool | None`, `latest_on_or_before(value: date) -> date | None`, and `next_on_or_after(value: date) -> date | None`.
- Produces `classify_session(now: datetime, calendar: BundledTradingCalendar) -> SessionContext` with `PRE_MARKET`, `INTRADAY`, `MIDDAY_BREAK`, `POST_MARKET`, or `NON_TRADING_DAY`.

- [ ] **Step 1: Write failing calendar and clock tests**

Use fixed Asia/Shanghai datetimes for a confirmed Monday at 09:00, 10:00, 12:00, and 15:10; a Saturday; one 2026 SSE holiday; and a weekday outside the bundled year. Assert the outside date returns `calendar_confirmed=False`, `decision` callers can therefore fail closed, and pre-market uses the previous confirmed open date.

```python
def test_unknown_weekday_is_not_assumed_open(self):
    context = classify_session(
        datetime(2027, 1, 4, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        self.calendar,
    )
    self.assertFalse(context.calendar_confirmed)
    self.assertIsNone(context.diagnosis_trade_date)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run `python3 -m unittest -v tests.test_calendar_session`; expected failure is missing calendar/session modules.

- [ ] **Step 3: Add the audited 2026 calendar snapshot**

Generate all 2026 calendar dates with explicit `0/1` open flags from weekends plus the SSE annual closure notice, then cross-check every flag against the already confirmed workspace calendar. Retain only public date flags and add metadata fields `exchange="SSE"`, `year=2026`, `source_url` pointing to the SSE annual closure notice, and `generated_at`. Do not copy Tushare credentials or workspace paths.

- [ ] **Step 4: Implement strict calendar and session logic**

Weekend dates return closed. In-range weekdays use the JSON flag. Out-of-range weekdays return unknown. Use half-open clock ranges: before 09:30 pre-market; 09:30–11:30 and 13:00–15:00 intraday; 11:30–13:00 midday; from 15:00 post-market.

- [ ] **Step 5: Run focused tests and commit**

Run Task 2 tests plus Task 1 tests. Commit only Task 2 files with `feat(stt-share): classify sessions from bundled SSE calendar`.

### Task 3: Public Market Client and Safe Public-data Cache

**Files:**
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/cache.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/eastmoney.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/fixtures/search_unique.json`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/fixtures/search_ambiguous.json`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/fixtures/quote_603011.json`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/fixtures/daily_603011.json`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/test_eastmoney.py`

**Interfaces:**
- Produces `JsonHttpClient.get_json(url: str, params: Mapping[str, str], timeout: float = 10.0) -> object` with an injectable opener.
- Produces `EastmoneyClient.resolve_symbol(value: str) -> Security`, `fetch_quote(security: Security) -> Quote`, and `fetch_daily_bars(security: Security, limit: int = 210) -> list[DailyBar]`.
- Produces `PublicDataCache.read(kind: str, key: str, max_age: timedelta | None) -> object | None` and `write(kind: str, key: str, payload: object) -> None`.
- Raises typed `AmbiguousSymbolError(candidates)`, `DataSourceError(code, safe_message)`, and `DataValidationError(code, safe_message)`.

- [ ] **Step 1: Write fixture-based failing parser tests**

Assert six-digit codes bypass search; an exact unique name resolves to the expected exchange/code/name; multiple plausible matches raise with candidates; quote integer fields are scaled correctly; 210 K-lines preserve turnover; malformed JSON, mismatched code, non-positive OHLC, invalid high/low ordering, and a response with no K-lines fail with typed errors.

```python
def test_quote_scaling_and_timestamp(self):
    quote = self.client.fetch_quote(Security("603011", "SH", "合锻智能"))
    self.assertEqual(quote.price, 23.95)
    self.assertEqual(quote.code, "603011")
    self.assertIsNotNone(quote.as_of.utcoffset())
```

- [ ] **Step 2: Run the focused test and verify RED**

Run `python3 -m unittest -v tests.test_eastmoney`; expected failure is missing market modules.

- [ ] **Step 3: Implement HTTP, parsing, validation, and cache**

Use `urllib.parse.urlencode`, an explicit desktop User-Agent, HTTPS domains only, 10-second timeout, and a 2 MiB response cap. Use Eastmoney search, quote, and unadjusted daily K-line routes; keep their request construction in named private functions so endpoint changes do not affect the decision engine. Cache symbol responses for at most 24 hours and completed K-lines by symbol/latest trade date. Realtime quotes never call `PublicDataCache.write`. Resolve the default cache root to `~/.cache/a-share-stock-diagnosis/` on macOS/Linux and `%LOCALAPPDATA%/a-share-stock-diagnosis/` on Windows; tests always inject a temporary root.

- [ ] **Step 4: Prove holdings never enter cache**

Write a test that calls all cache APIs with market payloads, enumerates the temporary cache files, and asserts none contains `shares`, `cost_price`, `available_shares`, or the test holding values. Reject cache kinds outside `symbols` and `daily`.

- [ ] **Step 5: Run focused tests and commit**

Run Tasks 1–3 tests. Commit the Task 3 files with `feat(stt-share): fetch validated public market data`.

### Task 4: Portable Indicators and CYQ Estimation

**Files:**
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/indicators.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/chip.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/test_indicators_chip.py`

**Interfaces:**
- Produces `calculate_indicators(bars: Sequence[DailyBar]) -> dict[str, float]` with `ma5`, `ma10`, `ma20`, `atr14`, `high20`, and `low10`.
- Produces `calculate_chip_metrics(bars: Sequence[DailyBar]) -> ChipMetrics` using `eastmoney-cyq-v1`.
- Both functions sort by trade date, reject duplicate dates, and require at least 20 valid completed bars.

- [ ] **Step 1: Write failing deterministic calculation tests**

Copy only the public algorithm expectations, not imports, from the existing standalone tests. Assert flat one-price bars, 50% latest turnover, zero effective turnover, invalid OHLC, unordered rows, duplicate dates, percentage units, and fixed MA/ATR/high/low values.

```python
def test_flat_limit_bars_have_one_cost(self):
    metrics = calculate_chip_metrics(self.flat_bars(price=10.0, count=20))
    self.assertEqual(metrics.cost_90_low, 10.0)
    self.assertEqual(metrics.cost_90_high, 10.0)
    self.assertEqual(metrics.average_cost, 10.0)
    self.assertEqual(metrics.method, "eastmoney-cyq-v1")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run `python3 -m unittest -v tests.test_indicators_chip`; expected import failure.

- [ ] **Step 3: Implement minimal pure calculations**

Use arithmetic means, 14 latest true ranges, 150 CYQ price buckets, daily turnover decay capped to `[0, 1]`, triangular allocation across each bar range, one-price allocation for `high == low`, and cumulative 5%/50%/95% cost quantiles. Round display prices to cents and percentages to four decimals.

- [ ] **Step 4: Run calculation regression and commit**

Run Task 4 plus Tasks 1–3 tests. Commit with `feat(stt-share): calculate portable indicators and CYQ`.

### Task 5: Entry and Holding Decision Engine

**Files:**
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/decision.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/test_decision.py`

**Interfaces:**
- Produces `diagnose(security: Security, context: SessionContext, bars: Sequence[DailyBar], quote: Quote | None, holding: HoldingInput | None, *, as_of: datetime) -> DiagnosisResult`.
- Produces `build_entry_levels(indicators: Mapping[str, float], chip: ChipMetrics) -> dict[str, float | None]`.
- Produces `round_sell_quantity(requested: int, available: int) -> int`.

- [ ] **Step 1: Write failing entry decision tests**

Assert complete static data produces `WAIT_ENTRY` only when `(trigger-invalidation)/trigger` is within 1.5%–5.0%; otherwise `NO_TRADE`. Missing/wrong-date bars, calendar unknown, missing CYQ, or stale/mismatched quote fails closed. Assert every result has `actionable=False`.

- [ ] **Step 2: Write failing holding decision tests**

Cover profitable hold, first-target reduction, support-loss reduction, invalidation exit, range holding, unknown available shares, zero available shares, and sell quantity rounding. Concrete quantity assertions must satisfy `quantity % 100 == 0` and `quantity <= available_shares`.

```python
def test_unknown_available_shares_never_emits_sell_quantity(self):
    result = diagnose(
        self.security, self.context, self.bars, self.quote,
        HoldingInput(shares=500, cost_price=22.75, available_shares=None),
        as_of=self.now,
    )
    self.assertIsNone(result.holding["suggested_sell_shares"])
    self.assertFalse(result.actionable)
```

- [ ] **Step 3: Run focused tests and verify RED**

Run `python3 -m unittest -v tests.test_decision`; expected import failure.

- [ ] **Step 4: Implement deterministic decision rules**

Calculate resistance as `max(high20, cost_90_high)`, trigger as resistance plus `0.10 * ATR14` rounded up to cents, entry ceiling as trigger plus `0.50 * ATR14`, support as `max(low10, cost_90_low, ma10)`, invalidation as support minus `0.10 * ATR14` rounded down to cents, and first-reduce as trigger plus twice the trigger-to-invalidation risk. The usable price is a fresh same-symbol quote during intraday; otherwise it is the latest completed close and the result is labelled non-realtime. Holding rules are ordered: calendar/data unknown or missing available shares when a sell condition exists gives `OBSERVE`; price at or below invalidation gives `EXIT`; price below support or at/above first-reduce gives `REDUCE`; otherwise gives `HOLD`. Use at most half the available position for `REDUCE`, rounded down to 100 shares, and all available board-lot shares for `EXIT`. If available shares are zero, emit no sell quantity and return `OBSERVE` with a T+1 warning.

- [ ] **Step 5: Verify decision suite and commit**

Run Tasks 1–5 tests. Commit with `feat(stt-share): guide manual holdings safely`.

### Task 6: Stable CLI and QClaw Skill Instructions

**Files:**
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/a_share_stock_diagnosis/cli.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/scripts/diagnose.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/test_cli.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/SKILL.md`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/README.md`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/.gitignore`

**Interfaces:**
- Produces `build_parser() -> argparse.ArgumentParser`, `run(argv: Sequence[str] | None = None, *, client=None, calendar=None, now=None) -> int`, and `main() -> int`.
- `scripts/diagnose.py` inserts the Skill root into `sys.path`, imports `a_share_stock_diagnosis.cli.main`, and exits with its return code.
- Standard output is exactly one UTF-8 JSON object conforming to `schema_version="1.0"`; diagnostics go to standard error.

- [ ] **Step 1: Write failing CLI contract tests**

Inject fixture clients and fixed clocks. Assert code and exact-name invocations, optional holding args, timezone-aware `--at`, invalid partial holdings, ambiguous-name error candidates, datasource failure, JSON key presence, `actionable=false`, and zero stdout text outside the JSON document.

- [ ] **Step 2: Run CLI tests and verify RED**

Run `python3 -m unittest -v tests.test_cli`; expected failure is missing CLI.

- [ ] **Step 3: Implement orchestration and safe failure JSON**

Resolve the symbol, classify session before market diagnosis, fetch completed daily bars, fetch realtime quote only for intraday or holding current-price needs, and call `diagnose`. When an intraday quote fails but completed bars remain valid, label the result non-realtime; ordinary diagnosis may use the completed close, while holding diagnosis must degrade to `OBSERVE`. Convert all expected validation/source failures into schema-valid `NO_TRADE` or `OBSERVE` JSON with safe messages. Unexpected exceptions use error code `UNEXPECTED_RUNTIME_ERROR`, omit exception internals from stdout, and exit nonzero.

- [ ] **Step 4: Write QClaw/OpenClaw instructions**

Use frontmatter name `a-share-stock-diagnosis` and a Chinese description covering “个股诊断、股票分析、持仓建议、减仓、止损、支撑压力”。Require QClaw to collect at least shares and cost for holdings, ask for only one missing value at a time, execute the bundled script, preserve script numbers and direction, disclose data time and CYQ estimation, and never replace failed output with free-form price claims.

- [ ] **Step 5: Write installation documentation and run all offline tests**

Document copying the whole folder to `~/.openclaw/workspace/skills/a-share-stock-diagnosis/` on macOS and `%USERPROFILE%\.openclaw\workspace\skills\a-share-stock-diagnosis\` on Windows. Include Python version checks, two example commands, QClaw discovery checks via its bundled wrapper, cache location, and uninstall by removing only this Skill folder. Run `python3 -m unittest discover -s tests -v` and compile all Python files.

- [ ] **Step 6: Commit Task 6**

Commit Task 6 files with `feat(stt-share): add QClaw diagnosis entry point`.

### Task 7: Online Smoke Test, Security Review, and Share Archive

**Files:**
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/tests/test_online.py`
- Create: `a-share-short-term-trading/share/qclaw/a-share-stock-diagnosis/scripts/package_skill.py`
- Create outside Git: `a-share-short-term-trading/dist/a-share-stock-diagnosis-qclaw.zip`

**Interfaces:**
- Online tests run only when `A_SHARE_DIAGNOSIS_ONLINE=1`; otherwise they skip without network access.
- `package_skill.py --output PATH` creates a deterministic ZIP containing only the Skill tree and prints its SHA-256 digest.

- [ ] **Step 1: Add an opt-in online test and verify default skip**

Test one Shanghai symbol (`603011`) and one Shenzhen symbol (`000001`). Require a non-empty name, at least 20 valid daily bars, source dates in ascending order, and a finite positive quote when the market source supplies one. Run without the environment flag and confirm two skips.

- [ ] **Step 2: Run real online smoke tests**

Run:

```bash
A_SHARE_DIAGNOSIS_ONLINE=1 python3 -m unittest -v tests.test_online
```

Expected: both symbols pass, or a typed source outage is reported without leaking response bodies or local configuration. A source outage blocks release and is retried once after confirming ordinary network access.

- [ ] **Step 3: Add deterministic packaging and test it**

The packager recursively includes `SKILL.md`, `README.md`, `data/`, `scripts/`, `a_share_stock_diagnosis/`, and `tests/`; excludes `.git`, `.cache`, `__pycache__`, `.pytest_cache`, `.env`, bytecode, logs, and existing ZIP files. Archive paths start at `a-share-stock-diagnosis/` and use stable sorted order.

- [ ] **Step 4: Run complete verification**

From the Skill root, run:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q a_share_stock_diagnosis scripts tests
python3 scripts/diagnose.py --symbol 603011 --output json
python3 scripts/diagnose.py --symbol 603011 --shares 500 --cost-price 22.75 --available-shares 500 --output json
```

Then copy the Skill to a temporary standalone directory and repeat the two CLI commands with `PYTHONPATH` unset. Validate `SKILL.md` frontmatter and run QClaw `skills check` against an approved temporary installation or, if installation approval is not granted, run its read-only structural checks and report the unexecuted discovery check explicitly.

- [ ] **Step 5: Run security and scope checks**

Review every file in the Skill. Confirm network destinations are named public HTTPS domains; no `eval`, `exec`, subprocess shell, credential reads, browser state, account files, absolute workspace paths, IP-address endpoints, or package installers exist. Scan for `MYSQL_URL`, `MYSQL_ROOT_PASSWORD`, `TUSHARE_TOKEN`, `shares=500`, `22.75`, `.env`, cookies, authorization headers, and private hostnames; test fixtures may use synthetic holding values but the packaged production files must not contain real holdings.

- [ ] **Step 6: Build archive and commit scoped source**

Create `a-share-short-term-trading/dist/a-share-stock-diagnosis-qclaw.zip`, record its SHA-256 in the handoff, and keep the generated ZIP untracked. Commit Task 7 source files with `test(stt-share): verify portable QClaw skill`. Do not stage unrelated assets.

## Final Acceptance

- The complete offline suite passes with only Python 3.10+ standard library.
- Opt-in live tests pass for one Shanghai and one Shenzhen stock.
- Both CLI modes emit one schema-valid JSON result and always set `actionable=false`.
- A copied standalone Skill runs without repository modules, MySQL, `.env`, Tushare, or OpenCLI.
- QClaw recognizes the standard Skill structure, or the only remaining blocked check is explicitly identified as requiring installation approval.
- The ZIP excludes caches, secrets, personal holdings, browser data, and workspace paths; its SHA-256 is reported.
- Existing full MySQL diagnosis code and unrelated dirty files remain unchanged.
