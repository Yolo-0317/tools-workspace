# Stable Announcement Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manually triggered, announcement-only historical backfill that paces Eastmoney requests, cools down on HTTP 567, stops safely after exhausted rate-limit retries, resumes checkpoints, and then produces a valid five-day research artifact.

**Architecture:** Keep the raw provider responsible for request pacing and safe HTTP classification. Add a dedicated announcement-only synchronization function that reuses existing natural-day pagination, normalization, checkpoints, and sync-run audit while applying a five-minute rate-limit retry policy and circuit breaker. Route a new CLI dataset selector to this narrow function so sector and ST providers are never constructed during historical announcement repair.

**Tech Stack:** Python 3.11, argparse, requests, SQLAlchemy, PyMySQL, pytest, existing `stock_ai.buy_point_selection` reference-data modules.

## Global Constraints

- Preserve fail-closed page count, declared total, required field, duplicate identity, and point-in-time timestamp validation.
- `--datasets all` remains the default and preserves current sector/ST/announcement behavior.
- `--datasets announcement` writes only announcement checkpoints, announcement sync runs, and normalized announcement risk flags.
- Eastmoney requests wait 0.5 seconds between HTTP calls.
- HTTP 403, 429, and 567 are `PROVIDER_RATE_LIMITED`.
- Announcement-only rate-limit retries wait 300 seconds each and allow exactly three retries after the first failed attempt.
- Exhausted rate-limit retries stop the command with exit code 2 and do not touch later partitions.
- Existing complete checkpoints are skipped, including recent dates in historical announcement-only mode.
- Progress prints every ten processed natural-day partitions and once at termination.
- Do not change risk keywords, severity, effective dates, completeness thresholds, selection profiles, `TWO_R`, five-day evaluation logic, holdings, orders, schedules, notifications, advisor memory, or decision ledgers.
- Do not enable or call the deprecated Eastmoney eight-dimension diagnosis; Eastmoney remains a raw announcement source only.
- Preserve unrelated dirty-worktree changes, especially the existing modification in `tests/unit/test_buy_point_reference_cninfo.py`.
- Do not run the irreversible five-day `test` stage.

---

## File Map

- Modify `stock_ai/buy_point_selection/reference_eastmoney.py`: request pacing and HTTP 567 classification only.
- Modify `stock_ai/buy_point_selection/reference_sync.py`: announcement-only synchronization, rate-limit retries, circuit breaker, and progress values.
- Modify `stock_ai/buy_point_selection/__init__.py`: export the new public announcement-only interfaces.
- Modify `scripts/sync/sync_buy_point_reference_data.py`: `--datasets` parser contract, announcement-only routing, and progress output.
- Modify `tests/unit/test_buy_point_reference_eastmoney.py`: provider pacing and 567 regression tests.
- Modify `tests/unit/test_buy_point_alternative_reference_sync.py`: announcement-only resumption, cooldown, circuit-breaker, and progress tests.
- Modify `tests/unit/test_sync_buy_point_reference_data.py`: CLI parser and no-sector/no-ST routing tests.
- Modify `docs/CAPABILITIES.md`: manual stable backfill command and safety behavior.
- Modify `docs/PROJECT_LAYOUT.md`: point to announcement-only mode from the reference-data entry.
- Runtime only: `output/research/buy_point_five_day_returns/research-*.json`; ignored local artifact, never stage it.

---

### Task 1: Pace Eastmoney and classify HTTP 567 as rate limiting

**Files:**
- Modify: `tests/unit/test_buy_point_reference_eastmoney.py`
- Modify: `stock_ai/buy_point_selection/reference_eastmoney.py:1-85`

**Interfaces:**
- Consumes: an injected HTTP session with `get(...)`, plus injected `sleep(seconds)`.
- Produces: `EastmoneyAnnouncementProvider(..., request_interval_seconds: float = 0.5, sleep: Callable[[float], None] = time.sleep)`; `fetch_announcement_page()` sleeps only before the second and subsequent requests and maps HTTP 567 to `PROVIDER_RATE_LIMITED`.

- [ ] **Step 1: Write failing provider tests**

Add imports and tests to `tests/unit/test_buy_point_reference_eastmoney.py`:

```python
def test_eastmoney_spaces_subsequent_requests_without_delaying_first() -> None:
    sleeps: list[float] = []
    session = FakeSession(FakeResponse(200, _payload(total=1)))
    provider = EastmoneyAnnouncementProvider(
        session=session,
        request_interval_seconds=0.5,
        sleep=sleeps.append,
    )

    provider.fetch_announcement_page(date(2024, 6, 12), 1)
    provider.fetch_announcement_page(date(2024, 6, 13), 1)

    assert sleeps == [0.5]
    assert len(session.requests) == 2


def test_eastmoney_rejects_negative_request_interval() -> None:
    with pytest.raises(ValueError, match="request_interval_seconds"):
        EastmoneyAnnouncementProvider(request_interval_seconds=-0.1)
```

Extend `test_eastmoney_announcement_failures_use_safe_codes` with this literal case:

```python
(FakeResponse(567, {}), "PROVIDER_RATE_LIMITED"),
```

The production mutations caught are removal of request pacing, sleeping before the first request, accepting a negative interval, and allowing HTTP 567 to fall through the generic 5xx branch.

- [ ] **Step 2: Run provider tests to verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_reference_eastmoney.py
```

Expected: failures because the constructor does not accept `request_interval_seconds` or `sleep`, and HTTP 567 currently produces `PROVIDER_UNAVAILABLE`.

- [ ] **Step 3: Implement minimal provider pacing**

In `stock_ai/buy_point_selection/reference_eastmoney.py`, add:

```python
from time import sleep as default_sleep
from typing import Any, Callable, Mapping

Sleep = Callable[[float], None]
```

Extend the constructor and state:

```python
def __init__(
    self,
    *,
    session: Any | None = None,
    page_size: int = 100,
    timeout_seconds: float = 20.0,
    request_interval_seconds: float = 0.5,
    sleep: Sleep = default_sleep,
) -> None:
    if page_size <= 0 or page_size > 100:
        raise ValueError("page_size must be in [1, 100]")
    if request_interval_seconds < 0:
        raise ValueError("request_interval_seconds must not be negative")
    self._session = session or requests.Session()
    self._page_size = page_size
    self._timeout_seconds = timeout_seconds
    self._request_interval_seconds = request_interval_seconds
    self._sleep = sleep
    self._request_started = False
```

Immediately before `self._session.get(...)`, add:

```python
if self._request_started and self._request_interval_seconds:
    self._sleep(self._request_interval_seconds)
self._request_started = True
```

Check rate-limit statuses before the generic `>= 500` branch:

```python
if response.status_code in {403, 429, 567}:
    raise ProviderFailure(
        self.provider_name, "announcements", "PROVIDER_RATE_LIMITED"
    )
```

Do not add provider-internal long retries; Task 2 owns cooldown and circuit-breaking.

- [ ] **Step 4: Run provider tests to verify GREEN**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point_reference_eastmoney.py
```

Expected: all provider tests pass with no real sleeping or network calls.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock_ai/buy_point_selection/reference_eastmoney.py \
  tests/unit/test_buy_point_reference_eastmoney.py
git diff --cached --check
git commit -m "fix(stock-ai): pace Eastmoney announcement requests"
```

---

### Task 2: Add announcement-only synchronization with cooldown and circuit breaker

**Files:**
- Modify: `tests/unit/test_buy_point_alternative_reference_sync.py`
- Modify: `stock_ai/buy_point_selection/reference_sync.py:25-590`
- Modify: `stock_ai/buy_point_selection/__init__.py`

**Interfaces:**
- Consumes: ordered trading dates, `captured_at`, a `CninfoReferenceSource`-compatible announcement provider, `ReferenceRepository`, injected sleep, and an optional progress callback.
- Produces: `AnnouncementSyncProgress`, `AnnouncementProgressCallback`, `ANNOUNCEMENT_RATE_LIMIT_DELAYS`, and `sync_announcement_reference_data(...) -> tuple[ReferenceSyncRun, ...]`.

- [ ] **Step 1: Write failing announcement-only resumption and progress tests**

Add imports to `tests/unit/test_buy_point_alternative_reference_sync.py`:

```python
from stock_ai.buy_point_selection.reference_sync import (
    AnnouncementSyncProgress,
    sync_announcement_reference_data,
)
```

Add a helper provider and literal tests:

```python
class EmptyAnnouncementProvider:
    provider_name = "EASTMONEY"

    def __init__(self) -> None:
        self.calls: list[tuple[date, int]] = []

    def fetch_announcement_page(self, day: date, page_no: int):
        self.calls.append((day, page_no))
        return AnnouncementPage((), 0, page_no, 100, 0)


def test_announcement_only_sync_skips_complete_partition_and_reports_progress() -> None:
    first = date(2025, 8, 4)
    days = tuple(first + timedelta(days=index) for index in range(12))
    repository = MemoryRepository()
    repository.save_checkpoint(
        ReferenceCheckpoint(
            "EASTMONEY",
            "announcement",
            first.isoformat(),
            "0",
            "COMPLETE",
            None,
            {"page_count": 0, "record_count": 0},
            NOW - timedelta(days=1),
        )
    )
    provider = EmptyAnnouncementProvider()
    progress: list[AnnouncementSyncProgress] = []

    runs = sync_announcement_reference_data(
        days,
        captured_at=NOW,
        announcement_source=provider,
        repository=repository,
        sleep=lambda _: None,
        progress=progress.append,
    )

    assert provider.calls[0] == (date(2025, 8, 5), 1)
    assert len(provider.calls) == 11
    assert progress == [
        AnnouncementSyncProgress(10, 9, 1, 0, 12, False),
        AnnouncementSyncProgress(12, 11, 1, 0, 12, True),
    ]
    assert all(run.dataset == "announcement" for run in runs)
```

The consecutive bounded calendar makes each loop iteration account for exactly
one natural-day partition, so the test independently proves the tenth-day
progress boundary. A complete first-day checkpoint is skipped even though it
is recent.

Add the rate-limit provider and circuit-breaker test before any production
change:

```python
class AlwaysRateLimitedAnnouncementProvider:
    provider_name = "EASTMONEY"

    def __init__(self) -> None:
        self.calls: list[tuple[date, int]] = []

    def fetch_announcement_page(self, day: date, page_no: int):
        self.calls.append((day, page_no))
        raise ProviderFailure(
            self.provider_name,
            "announcements",
            "PROVIDER_RATE_LIMITED",
        )


def test_announcement_only_rate_limit_cools_down_then_stops_before_later_days() -> None:
    first = date(2025, 8, 8)
    monday = date(2025, 8, 11)
    repository = MemoryRepository()
    provider = AlwaysRateLimitedAnnouncementProvider()
    sleeps: list[float] = []
    progress: list[AnnouncementSyncProgress] = []

    with pytest.raises(ProviderFailure) as caught:
        sync_announcement_reference_data(
            (first, monday),
            captured_at=NOW,
            announcement_source=provider,
            repository=repository,
            sleep=sleeps.append,
            progress=progress.append,
        )

    assert caught.value.error_code == "PROVIDER_RATE_LIMITED"
    assert provider.calls == [(first, 1)] * 4
    assert sleeps == [300.0, 300.0, 300.0]
    assert ("EASTMONEY", "announcement", first.isoformat()) in repository.checkpoints
    assert ("EASTMONEY", "announcement", "2025-08-09") not in repository.checkpoints
    assert len(repository.runs) == 1
    assert progress[-1] == AnnouncementSyncProgress(1, 0, 0, 1, 4, True)
```

The production mutations caught are short 1/2/4 rate-limit waits, advancing
to August 9 after exhausting August 8, omitting the failed audit record, or
touching all later partitions.

- [ ] **Step 2: Run both announcement-only tests to verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_alternative_reference_sync.py \
  -k "announcement_only_sync or announcement_only_rate_limit"
```

Expected: collection/import failure because `AnnouncementSyncProgress` and
`sync_announcement_reference_data` do not exist.

- [ ] **Step 3: Define progress and announcement page retry interfaces**

In `reference_sync.py`, add:

```python
ANNOUNCEMENT_RATE_LIMIT_DELAYS = (300.0, 300.0, 300.0)


@dataclass(frozen=True)
class AnnouncementSyncProgress:
    processed: int
    complete: int
    skipped: int
    failed: int
    total: int
    terminal: bool


AnnouncementProgressCallback = Callable[[AnnouncementSyncProgress], None]
```

Add a dedicated page retry helper that keeps existing unavailable retries but applies the confirmed five-minute policy only to rate limits:

```python
def _retry_announcement_page(
    operation: Callable[[], T],
    sleep: Callable[[float], None],
    rate_limit_delays: Sequence[float],
) -> T:
    unavailable_attempt = 0
    rate_limit_attempt = 0
    while True:
        try:
            return operation()
        except ProviderFailure as exc:
            if exc.error_code == "PROVIDER_RATE_LIMITED":
                if rate_limit_attempt == len(rate_limit_delays):
                    raise
                sleep(float(rate_limit_delays[rate_limit_attempt]))
                rate_limit_attempt += 1
                continue
            if exc.error_code == "PROVIDER_UNAVAILABLE":
                if unavailable_attempt == len(RETRY_DELAYS):
                    raise
                sleep(RETRY_DELAYS[unavailable_attempt])
                unavailable_attempt += 1
                continue
            raise
```

Validate that `rate_limit_delays` contains exactly three non-negative values in the public function. This keeps the production policy explicit while allowing unit tests to inject `(300.0, 300.0, 300.0)` with a no-wait sleeper.

- [ ] **Step 4: Extend the existing day synchronizer without changing all-dataset defaults**

Add keyword-only parameters to `_sync_announcement_day`:

```python
rate_limit_delays: Sequence[float] | None = None,
stop_on_rate_limit: bool = False,
```

Choose the page loader once inside the function:

```python
def fetch_page(natural_day: date, page_no: int) -> AnnouncementPage:
    operation = lambda: announcement_source.fetch_announcement_page(
        natural_day, page_no
    )
    if rate_limit_delays is None:
        return _retry(operation, sleep)
    return _retry_announcement_page(operation, sleep, rate_limit_delays)
```

Use `fetch_page` for page 1 and every later page. Track literal lists:

```python
skipped_partitions: list[str] = []
fetched_partitions: list[str] = []
failed_partitions: list[str] = []
rate_limit_exhausted = False
```

When a complete checkpoint is skipped, append its key to `skipped_partitions`. After full validation and checkpoint persistence, append to `fetched_partitions`. In the exception branch, persist the failed checkpoint, append its key to `failed_partitions`, and when this condition is true, break the natural-day loop immediately:

```python
rate_limit_exhausted = (
    stop_on_rate_limit
    and isinstance(exc, ProviderFailure)
    and exc.error_code == "PROVIDER_RATE_LIMITED"
)
if rate_limit_exhausted:
    break
```

Preserve the existing `completed_partitions` integer and add these details to the returned run:

```python
"skipped_partitions": skipped_partitions,
"fetched_partitions": fetched_partitions,
"failed_partitions": failed_partitions,
"rate_limit_exhausted": rate_limit_exhausted,
```

The existing `sync_alternative_reference_data` call passes neither new argument, so its behavior stays unchanged.

- [ ] **Step 5: Implement the public announcement-only loop**

Add this signature:

```python
def sync_announcement_reference_data(
    trade_dates: Sequence[date],
    *,
    captured_at: datetime,
    announcement_source: CninfoReferenceSource,
    repository: ReferenceRepository,
    sleep: Callable[[float], None] = default_sleep,
    rate_limit_delays: Sequence[float] = ANNOUNCEMENT_RATE_LIMIT_DELAYS,
    progress_every: int = 10,
    progress: AnnouncementProgressCallback | None = None,
) -> tuple[ReferenceSyncRun, ...]:
```

Validate non-empty strictly increasing dates, `progress_every > 0`, and exactly three non-negative delay values. Compute total natural partitions with:

```python
ordered = tuple(trade_dates)
total = (ordered[-1] - ordered[0]).days + 1
```

Loop over the trading dates with the same `previous` logic as the existing all-dataset path. Call `_sync_announcement_day` with `refresh_days=frozenset()`, `rate_limit_delays=rate_limit_delays`, and `stop_on_rate_limit=True`. Save each returned sync run before examining its error.

Aggregate counts from the new details keys. Emit progress at the next
trade-date boundary whenever `processed` crosses another multiple of
`progress_every`; emit a final `terminal=True` value at success or immediately
before raising on exhausted rate limiting. When the run contains
`rate_limit_exhausted=True`, raise:

```python
raise ProviderFailure(
    announcement_source.provider_name,
    "announcements",
    "PROVIDER_RATE_LIMITED",
)
```

This must occur after saving the failed checkpoint and run, and before iterating to the next trading date.

Export these names from `stock_ai/buy_point_selection/__init__.py`:

```python
AnnouncementSyncProgress
sync_announcement_reference_data
```

- [ ] **Step 6: Run both announcement-only tests to verify GREEN**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_alternative_reference_sync.py \
  -k "announcement_only_sync or announcement_only_rate_limit"
```

Expected: two passing tests.

- [ ] **Step 7: Run the complete alternative-reference focused suite**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_reference_eastmoney.py \
  tests/unit/test_buy_point_alternative_reference_sync.py
```

Expected: zero failures, including old all-dataset, weekend, checkpoint, pagination, and coverage behavior.

- [ ] **Step 8: Commit Task 2**

```bash
git add stock_ai/buy_point_selection/reference_sync.py \
  stock_ai/buy_point_selection/__init__.py \
  tests/unit/test_buy_point_alternative_reference_sync.py
git diff --cached --check
git commit -m "feat(stock-ai): add announcement-only backfill"
```

---

### Task 3: Expose the stable manual CLI and documentation

**Files:**
- Modify: `tests/unit/test_sync_buy_point_reference_data.py`
- Modify: `scripts/sync/sync_buy_point_reference_data.py:45-225`
- Modify: `docs/CAPABILITIES.md:350-380`
- Modify: `docs/PROJECT_LAYOUT.md:30-50`

**Interfaces:**
- Consumes: `sync_announcement_reference_data(...)` and `AnnouncementSyncProgress` from Task 2.
- Produces: parser option `--datasets {all,announcement}`, announcement-only routing, and stable progress lines.

- [ ] **Step 1: Write failing parser tests**

Add:

```python
def test_reference_cli_defaults_to_all_datasets() -> None:
    module = _load_script()

    args = module.build_parser().parse_args(
        ["--start", "2024-01-02", "--end", "latest"]
    )

    assert args.datasets == "all"


def test_reference_cli_accepts_announcement_only_dataset() -> None:
    module = _load_script()

    args = module.build_parser().parse_args(
        [
            "--start",
            "2023-12-26",
            "--end",
            "2026-08-04",
            "--datasets",
            "announcement",
            "--announcement-provider",
            "eastmoney",
        ]
    )

    assert args.datasets == "announcement"
```

- [ ] **Step 2: Run parser tests to verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_sync_buy_point_reference_data.py::test_reference_cli_defaults_to_all_datasets \
  tests/unit/test_sync_buy_point_reference_data.py::test_reference_cli_accepts_announcement_only_dataset
```

Expected: failures because `datasets` is absent and the parser rejects `--datasets`.

- [ ] **Step 3: Add the parser contract**

In `build_parser()` add:

```python
parser.add_argument(
    "--datasets",
    choices=("all", "announcement"),
    default="all",
    help="all 同步行业、ST和公告；announcement 仅断点回补公告",
)
```

In `main()`, reject `--provider tushare --datasets announcement` with:

```python
if args.datasets == "announcement" and args.provider != "cninfo-baostock":
    raise ValueError("公告专用模式仅支持 cninfo-baostock 提供器族")
```

Expected CLI output remains a safe single-line failure and exit code 2.

- [ ] **Step 4: Run parser tests to verify GREEN**

Run the two tests from Step 2. Expected: two passing tests.

- [ ] **Step 5: Write the failing routing test**

Add a test that makes any unrelated construction fail immediately and asserts observable progress output:

```python
def test_announcement_only_cli_does_not_build_universe_or_baostock(
    monkeypatch,
    capsys,
) -> None:
    module = _load_script()
    day = date(2025, 8, 6)
    engine = object()
    repository = object()

    monkeypatch.setattr(module, "_engine", lambda: engine)
    monkeypatch.setattr(module, "_trade_dates", lambda *_: (day,))
    monkeypatch.setattr(
        module,
        "_universe_by_date",
        lambda *_: (_ for _ in ()).throw(AssertionError("universe called")),
    )
    monkeypatch.setattr(
        module,
        "_baostock",
        lambda: (_ for _ in ()).throw(AssertionError("baostock called")),
    )
    monkeypatch.setattr(module, "_eastmoney", lambda: object())
    monkeypatch.setattr(module, "SQLReferenceRepository", lambda _: repository)

    def run_announcements(*args, progress, **kwargs):
        progress(module.AnnouncementSyncProgress(1, 1, 0, 0, 1, True))
        return ()

    monkeypatch.setattr(
        module,
        "sync_announcement_reference_data",
        run_announcements,
    )

    result = module.main(
        [
            "--start",
            day.isoformat(),
            "--end",
            day.isoformat(),
            "--datasets",
            "announcement",
            "--announcement-provider",
            "eastmoney",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out.splitlines() == [
        "announcement-progress: processed=1 complete=1 skipped=0 failed=0 total=1 terminal=true"
    ]
```

This test exercises the real CLI branch and fails if the branch constructs the historical universe or BaoStock provider.

- [ ] **Step 6: Run the routing test to verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_sync_buy_point_reference_data.py::test_announcement_only_cli_does_not_build_universe_or_baostock
```

Expected: failure because the all-dataset path still calls `_universe_by_date`.

- [ ] **Step 7: Implement announcement-only routing and progress output**

Import the Task 2 interfaces:

```python
from stock_ai.buy_point_selection.reference_sync import (
    AlternativeReferenceSyncRequest,
    AnnouncementSyncProgress,
    sync_alternative_reference_data,
    sync_announcement_reference_data,
)
```

Add:

```python
def _print_announcement_progress(value: AnnouncementSyncProgress) -> None:
    terminal = "true" if value.terminal else "false"
    print(
        "announcement-progress: "
        f"processed={value.processed} complete={value.complete} "
        f"skipped={value.skipped} failed={value.failed} "
        f"total={value.total} terminal={terminal}"
    )
```

After loading trade dates, timestamp, and repository, branch before `_universe_by_date`:

```python
if args.datasets == "announcement":
    announcement_source = (
        _eastmoney() if args.announcement_provider == "eastmoney" else _cninfo()
    )
    runs = sync_announcement_reference_data(
        trade_dates,
        captured_at=captured_at,
        announcement_source=announcement_source,
        repository=repository,
        progress=_print_announcement_progress,
    )
elif args.provider == "tushare":
    runs = sync_reference_data(...)
else:
    runs = sync_alternative_reference_data(...)
```

Keep existing final per-run summaries for successfully returned runs. On exhausted rate limiting, the progress callback prints the terminal state and the existing safe error handler prints `点时参考数据同步失败：PROVIDER_RATE_LIMITED`.

- [ ] **Step 8: Run all CLI tests to verify GREEN**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_sync_buy_point_reference_data.py
```

Expected: zero failures, including old provider defaults and safe error output.

- [ ] **Step 9: Document the manual command and safety behavior**

Add this command to the existing point-in-time reference-data section of `docs/CAPABILITIES.md`:

```bash
PYTHONPATH=. .venv/bin/python scripts/sync/sync_buy_point_reference_data.py \
  --start 2023-12-26 --end 2026-08-04 \
  --provider cninfo-baostock --announcement-provider eastmoney \
  --datasets announcement
```

State immediately below it:

- only announcement checkpoints, announcement sync runs, and normalized risk flags are written;
- completed partitions are skipped;
- Eastmoney pages are spaced by 0.5 seconds;
- 403/429/567 cool down for five minutes and stop after three exhausted retries;
- the command is manual and does not install scheduling or invoke Eastmoney AI diagnosis.

Update the reference-data command in `docs/PROJECT_LAYOUT.md` to mention `--datasets announcement` for historical announcement repair.

- [ ] **Step 10: Run focused Task 1-3 tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_reference_eastmoney.py \
  tests/unit/test_buy_point_alternative_reference_sync.py \
  tests/unit/test_sync_buy_point_reference_data.py
```

Expected: zero failures.

- [ ] **Step 11: Commit Task 3**

```bash
git add scripts/sync/sync_buy_point_reference_data.py \
  tests/unit/test_sync_buy_point_reference_data.py \
  docs/CAPABILITIES.md docs/PROJECT_LAYOUT.md
git diff --cached --check
git commit -m "feat(stock-ai): expose stable announcement backfill"
```

---

### Task 4: Verify, resume the live backfill, and rebuild research

**Files:**
- Verify only: all Task 1-3 files.
- Runtime output: MySQL reference tables and ignored `output/research/buy_point_five_day_returns/research-*.json`.

**Interfaces:**
- Consumes: the manual announcement-only CLI from Task 3 and five-day research CLI from commit `7007b5c`.
- Produces: complete announcement coverage for all required research dates and a new research artifact; no freeze or test artifact.

- [ ] **Step 1: Read the completion-verification skill and run static scope checks**

Read `/Users/huan.yu/.codex/skills/verification-before-completion/SKILL.md`, then run:

```bash
git diff --check
rg -n "send_to_lark|notify|schedule|advisor_memory|portfolio_positions|orders" \
  stock_ai/buy_point_selection/reference_eastmoney.py \
  stock_ai/buy_point_selection/reference_sync.py \
  scripts/sync/sync_buy_point_reference_data.py
```

Review every match. Imports or calls that mutate portfolio, advisor memory, orders, notifications, or scheduling are forbidden.

- [ ] **Step 2: Run the full buy-point regression**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_buy_point*.py \
  tests/unit/test_review_buy_point*.py \
  tests/unit/test_generate_buy_point_observations_cli.py \
  tests/unit/test_backtest_buy_point_selection_cli.py \
  tests/unit/test_sync_buy_point_reference_data.py
```

Expected: zero failures. Do not edit or stage the unrelated existing changes in `tests/unit/test_buy_point_reference_cninfo.py`.

- [ ] **Step 3: Probe Eastmoney once before a bounded live batch**

Use the production provider for one page. Expected: HTTP 200 and a valid `AnnouncementPage`. If HTTP 567 persists, do not bypass it with proxies or header evasion; wait and retry manually later.

```bash
PYTHONPATH=. .venv/bin/python -c '
from datetime import date
from stock_ai.buy_point_selection.reference_eastmoney import EastmoneyAnnouncementProvider
page = EastmoneyAnnouncementProvider().fetch_announcement_page(date(2024, 4, 15), 1)
print(f"provider=EASTMONEY pages={page.page_count} total={page.total_count}")
'
```

- [ ] **Step 4: Run a bounded announcement-only live batch**

Preserve credentials from `.env` while overriding only the previously
confirmed LAN host and port for this process:

```bash
MYSQL_URL="$(.venv/bin/python -c '
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
value = dotenv_values(Path(".env")).get("MYSQL_URL")
print(make_url(value).set(host="192.168.1.13", port=3306).render_as_string(hide_password=False))
')" PYTHONPATH=. .venv/bin/python \
  scripts/sync/sync_buy_point_reference_data.py \
  --start 2024-04-15 --end 2024-04-19 \
  --provider cninfo-baostock --announcement-provider eastmoney \
  --datasets announcement
```

Expected: progress lines, complete or skipped checkpoints, no sector/ST run lines, and exit 0. If the circuit breaker exits 2, keep the checkpoint and stop until the WAF cooldown clears.

- [ ] **Step 5: Verify the bounded invocation wrote no sector/ST run**

Query the latest captured timestamp for the bounded invocation and assert every row in that batch has `dataset='announcement'`. Also verify completed Eastmoney checkpoints increased or were reported as skipped. Use `SELECT` only for verification.

- [ ] **Step 6: Resume the full historical backfill**

Run the same safe temporary MySQL host override with:

```bash
MYSQL_URL="$(.venv/bin/python -c '
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
value = dotenv_values(Path(".env")).get("MYSQL_URL")
print(make_url(value).set(host="192.168.1.13", port=3306).render_as_string(hide_password=False))
')" PYTHONPATH=. .venv/bin/python \
  scripts/sync/sync_buy_point_reference_data.py \
  --start 2023-12-26 --end 2026-08-04 \
  --provider cninfo-baostock --announcement-provider eastmoney \
  --datasets announcement
```

Expected: existing 194 complete partitions are skipped, progress advances in ten-partition increments, and exit 0 after all remaining partitions validate. A rate-limit exit 2 is a safe paused state; rerun manually after cooldown rather than weakening the policy.

- [ ] **Step 7: Verify research-date announcement coverage**

Using `SQLReferenceRepository.coverage_between(...)`, assert for the 504 train-plus-validation dates:

```text
research_dates=504
sector_complete=504
st_complete=504
announcement_complete=504
complete=504
```

Do not proceed if any count is lower.

- [ ] **Step 8: Rerun only the five-day research stage**

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

Expected: a new `research-<identity>.json` whose split is `378/126/126`, `point_in_time_complete` is true, and `test_outcomes_read` is false. Observation count may legitimately be zero only if complete downstream discovery rejection evidence proves that result; announcement coverage may no longer explain it.

- [ ] **Step 9: Stop before freeze and test**

Report:

- completed, skipped, failed, and total announcement partitions;
- the 504-date coverage counts;
- the new research artifact path and identity;
- observation count and four validation profile metrics;
- confirmation that no schedule, notification, holding, order, advisor-memory, freeze, or test artifact was created.

Do not run `freeze` until the new research artifact is reviewed. Never run the irreversible one-shot `test` stage as part of implementation verification.

---

## Stop Conditions

- Stop coding when any TDD RED failure is caused by a typo or fixture error rather than the missing behavior; repair the test before production changes.
- Stop when an old all-dataset, checkpoint, pagination, normalization, or buy-point regression fails.
- Stop live backfill on exhausted rate limiting; do not bypass the provider WAF.
- Stop before research if announcement coverage is below 504/504.
- Stop before freeze if `point_in_time_complete` is false.
- Stop before every one-shot `test` invocation; it requires a separate explicit user confirmation after artifact review.
