# Five-Day Benchmark Index Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make five-day research, frozen-test input loading, and forward input loading use the existing BaoStock-primary/raw-Eastmoney-empty-series benchmark adapter so the exact three-index market snapshots can become point-in-time complete.

**Architecture:** Keep `BENCHMARK_INDEX_CODES` and `load_mysql_five_day_inputs(...)` unchanged. Characterize the existing fail-closed fallback, then inject `_load_benchmark_index_bars` into both CLI-owned MySQL input loaders through the existing `benchmark_loader` keyword. Verify the change with focused regressions and one new `research` artifact only.

**Tech Stack:** Python 3.11, pytest/monkeypatch, BaoStock, raw Eastmoney index K-lines through OpenCLI, SQLAlchemy/PyMySQL read-only access, deterministic JSON research artifacts.

## Global Constraints

- Run implementation commands from `/Users/huan.yu/dev/tools-workspace/stock-ai`.
- Benchmarks remain exactly `sh.000001`, `sz.399001`, and `sh.000688`.
- BaoStock remains primary; raw Eastmoney index K-lines may fill only an entirely empty primary series and never overwrite or patch a non-empty primary series.
- Missing, malformed, or unavailable fallback data remains empty and keeps downstream point-in-time completeness fail-closed.
- Use only raw Eastmoney index K-lines. The deprecated Eastmoney eight-dimension and every Eastmoney stock-diagnosis framework remain forbidden to AI.
- Do not add MySQL persistence, cache, schema, synchronization, scheduling, notifications, orders, holdings writes, executable shares, advisor memory, or decision-memory writes.
- Do not change candidate discovery, profiles, thresholds, labels, `TWO_R`, position sizing, or short-term trading advice.
- Runtime MySQL access is read-only. Derive credentials from `.env` without printing them and override only host/port to `192.168.1.13:3306` in process memory.
- Run only the `research` stage for runtime acceptance. Do not invoke `freeze` or the one-shot `test` stage.
- Preserve every unrelated dirty-worktree change. Stage and commit only the exact files named by each task; specifically do not edit or stage the pre-existing dirty `tests/unit/test_buy_point_reference_cninfo.py`.
- Generated artifacts under `output/research/buy_point_five_day_returns/` remain ignored and must never be staged.
- Use TDD for the missing loader wiring and keep commits scoped.

---

### Task 1: Characterize the Existing Fail-Closed Benchmark Adapter

**Files:**
- Modify: `tests/unit/test_review_buy_point_case_cli.py:1-20,500-540`
- Test: `tests/unit/test_review_buy_point_case_cli.py`

**Interfaces:**
- Consumes: `_load_benchmark_index_bars(start: date, end: date) -> dict[str, tuple[IndexBar, ...]]`, `BaoStockReferenceProvider`, and `fetch_index_kline_rows_opencli(codes, *, limit)`.
- Produces: regression evidence that a fallback transport failure preserves non-empty BaoStock data and leaves missing benchmark series empty.

- [ ] **Step 1: Add the imports required by the characterization test**

Add `nullcontext`, the private loader, and the two modules whose runtime symbols are patched:

```python
from contextlib import nullcontext

from scripts.analysis.review_buy_point_case import (
    CaseReviewInputs,
    DefaultRuntime,
    _build_case_research_layers,
    _build_daily_recall,
    _build_resistance_profiles,
    _load_benchmark_index_bars,
    _load_holdings_by_date,
    _merge_missing_index_bars,
    main,
)
from scripts.tools import fetch_eastmoney_quotes
from stock_ai.buy_point_selection import reference_baostock
```

- [ ] **Step 2: Write the fail-closed characterization test**

Append beside `test_eastmoney_index_rows_only_fill_missing_baostock_series`:

```python
def test_benchmark_loader_leaves_missing_series_empty_when_fallback_fails(
    monkeypatch,
) -> None:
    primary_bar = IndexBar(
        "sh.000001",
        date(2026, 8, 3),
        Decimal("3550.12"),
        Decimal("0.35"),
    )

    class FakeProvider:
        def session(self):
            return nullcontext()

        def fetch_index_bars(self, code: str, start: date, end: date):
            del start, end
            return (primary_bar,) if code == "sh.000001" else ()

    def fail_fallback(codes, *, limit):
        del codes, limit
        raise RuntimeError("fallback unavailable")

    monkeypatch.setattr(
        reference_baostock,
        "BaoStockReferenceProvider",
        FakeProvider,
    )
    monkeypatch.setattr(
        fetch_eastmoney_quotes,
        "fetch_index_kline_rows_opencli",
        fail_fallback,
    )

    loaded = _load_benchmark_index_bars(
        date(2026, 8, 1),
        date(2026, 8, 7),
    )

    assert loaded == {
        "sh.000001": (primary_bar,),
        "sz.399001": (),
        "sh.000688": (),
    }
```

- [ ] **Step 3: Run the existing merge test and the new characterization test**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_review_buy_point_case_cli.py::test_eastmoney_index_rows_only_fill_missing_baostock_series \
  tests/unit/test_review_buy_point_case_cli.py::test_benchmark_loader_leaves_missing_series_empty_when_fallback_fails \
  -q
```

Expected: `2 passed`. The second test locks existing behavior; if it fails, stop and diagnose the adapter before wiring it into additional stages.

- [ ] **Step 4: Commit only the characterization test**

```bash
git add tests/unit/test_review_buy_point_case_cli.py
git diff --cached --check
git commit -m "test(stock-ai): lock benchmark fallback failure"
```

Expected: the commit contains only `tests/unit/test_review_buy_point_case_cli.py`.

---

### Task 2: Inject the Shared Benchmark Adapter Into Both Five-Day Input Paths

**Files:**
- Modify: `tests/unit/test_research_five_day_return_shadow_cli.py:1-55,180-230`
- Modify: `scripts/analysis/research_five_day_return_shadow.py:15-40,119-146`
- Test: `tests/unit/test_research_five_day_return_shadow_cli.py`

**Interfaces:**
- Consumes: `_load_benchmark_index_bars(start: date, end: date)` from `scripts.analysis.review_buy_point_case` and the existing keyword-only `benchmark_loader` parameter on `load_mysql_five_day_inputs(...)`.
- Produces: `_load_mysql_research_inputs(...)` and `_load_mysql_range_inputs(...)` that both pass `benchmark_loader=_load_benchmark_index_bars` while preserving their existing date boundaries and return type.

- [ ] **Step 1: Write the failing loader-wiring test**

Append after the parser tests. The fake MySQL loader intentionally asserts the missing behavior:

```python
@pytest.mark.parametrize(
    "loader_name",
    ("_load_mysql_research_inputs", "_load_mysql_range_inputs"),
)
def test_mysql_input_loaders_share_benchmark_fallback(
    monkeypatch,
    loader_name: str,
) -> None:
    module = _load_module()
    signal_dates = tuple(
        date(2024, 1, 1) + timedelta(days=index)
        for index in range(630)
    )
    benchmark_loader = object()
    captured: list[tuple[tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(
        module,
        "_mysql_signal_dates",
        lambda start, end: signal_dates,
    )
    monkeypatch.setattr(
        module,
        "_load_benchmark_index_bars",
        benchmark_loader,
    )

    def fake_mysql_loader(*args, **kwargs):
        captured.append((args, kwargs))
        return "loaded"

    monkeypatch.setattr(module, "load_mysql_five_day_inputs", fake_mysql_loader)

    result = getattr(module, loader_name)(
        signal_dates[0],
        signal_dates[-1],
        signal_dates[-1] + timedelta(days=10),
    )

    assert result == "loaded"
    assert len(captured) == 1
    assert captured[0][1] == {"benchmark_loader": benchmark_loader}
```

- [ ] **Step 2: Run the new test to verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_research_five_day_return_shadow_cli.py::test_mysql_input_loaders_share_benchmark_fallback \
  -q
```

Expected: both parameter cases fail because the module does not yet expose `_load_benchmark_index_bars` and neither loader passes `benchmark_loader`.

- [ ] **Step 3: Import the existing adapter into the five-day CLI**

Add this import near the other module imports in `research_five_day_return_shadow.py`:

```python
from scripts.analysis.review_buy_point_case import _load_benchmark_index_bars
```

Do not copy the adapter, move it, or introduce a new provider abstraction in this task.

- [ ] **Step 4: Pass the adapter through both existing loader calls**

Keep all four positional date arguments unchanged and add only the keyword dependency:

```python
return load_mysql_five_day_inputs(
    signal_dates,
    split.train[0] - timedelta(days=180),
    split.validation[-1],
    split.test[9],
    benchmark_loader=_load_benchmark_index_bars,
)
```

```python
return load_mysql_five_day_inputs(
    signal_dates,
    signal_start - timedelta(days=180),
    signal_end,
    outcome_cutoff,
    benchmark_loader=_load_benchmark_index_bars,
)
```

- [ ] **Step 5: Run the loader-wiring test to verify GREEN**

Run the Step 2 command again.

Expected: `2 passed`.

- [ ] **Step 6: Run both focused CLI test files**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_research_five_day_return_shadow_cli.py \
  tests/unit/test_review_buy_point_case_cli.py \
  -q
```

Expected: zero failures. No test may make a live BaoStock, Eastmoney, OpenCLI, or MySQL request.

- [ ] **Step 7: Commit only the wiring and its test**

```bash
git add \
  scripts/analysis/research_five_day_return_shadow.py \
  tests/unit/test_research_five_day_return_shadow_cli.py
git diff --cached --check
git commit -m "fix(stock-ai): load complete benchmark inputs"
```

Expected: the commit contains exactly the two declared files.

---

### Task 3: Verify Regressions and Produce a Research-Only Artifact

**Files:**
- Verify: `scripts/analysis/research_five_day_return_shadow.py`
- Verify: `stock_ai/buy_point_selection/five_day_return_runtime.py`
- Verify: `output/research/buy_point_five_day_returns/research-*.json` (ignored runtime artifact; never stage)

**Interfaces:**
- Consumes: both committed tasks, `.env` credentials retained locally, read-only MySQL at `192.168.1.13:3306`, BaoStock for `sh.000001` and `sz.399001`, and raw Eastmoney index K-lines only for empty `sh.000688`.
- Produces: a new auditable `research-<identity>.json` with complete market inputs and a report of observations, rejection evidence, profile metrics, identity, and fingerprint. It produces no freeze or test artifact.

- [ ] **Step 1: Run the focused five-day runtime regression**

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_five_day_return_runtime.py \
  tests/unit/test_five_day_return_validation.py \
  tests/unit/test_five_day_return_report.py \
  tests/unit/test_research_five_day_return_shadow_cli.py \
  tests/unit/test_review_buy_point_case_cli.py \
  -q
```

Expected: zero failures. Stop on any regression; do not start live research while tests fail.

- [ ] **Step 2: Verify the exact three-index source result over the research window**

Call `_load_benchmark_index_bars(date(2023, 6, 29), date(2026, 2, 6))` and print only code, bar count, first date, and last date. Do not print URLs, credentials, raw response bodies, or stock-diagnosis output.

Expected:

```text
sh.000001 count=636
sz.399001 count=636
sh.000688 count=636
```

If any series is empty or does not cover all 504 train-plus-validation dates, stop. Do not substitute another index or weaken completeness.

- [ ] **Step 3: Run only the five-day research stage**

Derive a process-local URL from `.env`, replacing only the host and port, and pass it directly to the research process without logging it:

```bash
MYSQL_URL="$(.venv/bin/python -c '
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
value = dotenv_values(Path(".env")).get("MYSQL_URL")
print(make_url(value).set(host="192.168.1.13", port=3306).render_as_string(hide_password=False))
')" PYTHONPATH=. .venv/bin/python \
  scripts/analysis/research_five_day_return_shadow.py research \
  --signal-start 2023-12-26 --signal-end 2026-08-04
```

Expected: exit 0 and exactly one new ignored `research-<identity>.json`. Do not run `freeze`, `test`, `forward-screen`, or `forward-settlement`.

- [ ] **Step 4: Inspect the new artifact without reading test outcomes**

Read the newest research JSON and report:

```text
artifact path and artifact_identity
input_fingerprint
split sizes: 378/126/126
test_outcomes_read=false
point_in_time_complete=true
observation count > 0
rejection counts and incomplete dates
each of the four validation profiles: total/triggered samples, expectancy,
profit factor, drawdown, qualification, and reasons
```

Profile qualification is evidence-driven and may remain false. Do not alter thresholds or pad candidates to force qualification. If observations remain zero, preserve the artifact and diagnose the next fail-closed stage from its rejection evidence before proposing any change.

- [ ] **Step 5: Verify the safety boundary and report the checkpoint**

Confirm no file matching `freeze-*.json`, `test-*.json`, `forward-screen-*.json`, or `forward-settlement-*.json` was created by this invocation. Confirm no code or artifact is staged after Task 2.

Report the new artifact identity and its comparison with the prior zero-observation artifact `b30d6473e62c7009f052dceede03def0232cf0e2b07d43f3598243dd813a4a1e`. Stop for user review before any freeze or test action.

---

## Stop Conditions

- Stop implementation if the new loader-wiring test fails for fixture or import reasons unrelated to the missing `benchmark_loader` keyword; repair the test before changing production code.
- Stop if fallback retrieval tries to overwrite or patch a non-empty BaoStock series.
- Stop if Eastmoney fallback failure is converted into fabricated bars or a complete market snapshot.
- Stop if a focused regression fails.
- Stop live research if any of the three exact benchmark series lacks required research-date coverage.
- Stop after the new research artifact. Never run `freeze` or consume the one-shot test set without a separate explicit review and confirmation.
