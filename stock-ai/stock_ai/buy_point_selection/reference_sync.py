"""Resumable CNInfo and BaoStock point-in-time reference synchronization."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from time import sleep as default_sleep
from typing import TypeVar
from uuid import NAMESPACE_URL, uuid5

from .reference_data import (
    ReferenceCheckpoint,
    ReferenceRepository,
    ReferenceSyncRun,
    SectorMembership,
    membership_on,
)
from .reference_normalization import (
    normalize_baostock_risk_flags,
    normalize_cninfo_announcement_flags,
    normalize_cninfo_memberships,
)
from .reference_sources import (
    Announcement,
    AnnouncementPage,
    BaoStockReferenceSource,
    CninfoReferenceSource,
    ProviderFailure,
)


RETRYABLE_PROVIDER_ERRORS = frozenset(
    {"PROVIDER_RATE_LIMITED", "PROVIDER_UNAVAILABLE"}
)
RETRY_DELAYS = (1, 2, 4)
CHECKPOINT_WRITE_BATCH_SIZE = 50
T = TypeVar("T")


@dataclass(frozen=True)
class AlternativeReferenceSyncRequest:
    trade_dates: tuple[date, ...]
    universe_by_date: Mapping[date, frozenset[str]]
    captured_at: datetime
    minimum_coverage: Decimal = Decimal("0.98")
    refresh_recent_trade_dates: int = 2

    def __post_init__(self) -> None:
        if not self.trade_dates or any(
            current <= previous
            for previous, current in zip(self.trade_dates, self.trade_dates[1:])
        ):
            raise ValueError("trade_dates must be non-empty and strictly increasing")
        if any(day not in self.universe_by_date for day in self.trade_dates):
            raise ValueError("universe_by_date must cover every trading date")
        if not Decimal("0") < self.minimum_coverage <= Decimal("1"):
            raise ValueError("minimum_coverage must be in (0, 1]")
        if self.refresh_recent_trade_dates < 0:
            raise ValueError("refresh_recent_trade_dates must not be negative")


def _retry(operation: Callable[[], T], sleep: Callable[[float], None]) -> T:
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return operation()
        except ProviderFailure as exc:
            if (
                exc.error_code not in RETRYABLE_PROVIDER_ERRORS
                or attempt == len(RETRY_DELAYS)
            ):
                raise
            sleep(RETRY_DELAYS[attempt])
    raise AssertionError("unreachable")


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, ProviderFailure):
        return exc.error_code
    return "PROVIDER_SCHEMA_CHANGED"


def _checkpoint(
    *,
    provider: str,
    dataset: str,
    partition_key: str,
    status: str,
    captured_at: datetime,
    error_code: str | None = None,
    cursor_value: str | None = None,
    details: Mapping[str, object] | None = None,
) -> ReferenceCheckpoint:
    return ReferenceCheckpoint(
        provider=provider,
        dataset=dataset,
        partition_key=partition_key,
        cursor_value=cursor_value,
        status=status,
        error_code=error_code,
        details=dict(details or {}),
        updated_at=captured_at,
    )


def _run(
    *,
    dataset: str,
    provider: str,
    start: date,
    end: date,
    status: str,
    row_count: int,
    captured_at: datetime,
    error_code: str | None = None,
    expected_count: int | None = None,
    coverage_ratio: Decimal | None = None,
    details: Mapping[str, object] | None = None,
) -> ReferenceSyncRun:
    identity = f"buy-point-reference:{provider}:{dataset}:{start}:{end}"
    return ReferenceSyncRun(
        run_id=str(uuid5(NAMESPACE_URL, identity)),
        dataset=dataset,
        start_date=start,
        end_date=end,
        status=status,
        row_count=row_count,
        error_code=error_code,
        captured_at=captured_at,
        provider=provider,
        expected_count=expected_count,
        coverage_ratio=coverage_ratio,
        details=dict(details or {}),
    )


def _ratio(observed: int, expected: int) -> Decimal:
    return Decimal("1") if expected == 0 else Decimal(observed) / Decimal(expected)


def _next_weekday(value: date) -> date:
    candidate = value + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _sync_sector(
    request: AlternativeReferenceSyncRequest,
    cninfo: CninfoReferenceSource,
    repository: ReferenceRepository,
    sleep: Callable[[float], None],
) -> ReferenceSyncRun:
    start, end = request.trade_dates[0], request.trade_dates[-1]
    codes = tuple(sorted(set().union(*(request.universe_by_date[d] for d in request.trade_dates))))
    existing = repository.memberships_between(start, end)
    existing_codes = {row.code for row in existing}
    checkpoints = repository.load_checkpoints("CNINFO", "sector", codes)
    confirmed_empty_codes: set[str] = set()

    def checkpoint_has_current_empty_result(checkpoint: ReferenceCheckpoint) -> bool:
        try:
            membership_count = int(checkpoint.details.get("membership_count", -1))
        except (TypeError, ValueError):
            return False
        return (
            membership_count == 0
            and checkpoint.updated_at.date() == request.captured_at.date()
        )

    pending = tuple(
        code
        for code in codes
        if not (
            (checkpoint := checkpoints.get(code))
            and checkpoint.status == "COMPLETE"
            and (
                code in existing_codes
                or checkpoint_has_current_empty_result(checkpoint)
            )
        )
    )
    confirmed_empty_codes.update(
        code
        for code in codes
        if (
            (checkpoint := checkpoints.get(code))
            and checkpoint.status == "COMPLETE"
            and checkpoint_has_current_empty_result(checkpoint)
        )
    )
    new_rows: list[SectorMembership] = []
    failures: list[tuple[str, str]] = []
    checkpoint_buffer: list[ReferenceCheckpoint] = []

    def save_sector_checkpoint(checkpoint: ReferenceCheckpoint) -> None:
        checkpoint_buffer.append(checkpoint)
        if len(checkpoint_buffer) >= CHECKPOINT_WRITE_BATCH_SIZE:
            repository.save_checkpoints(tuple(checkpoint_buffer))
            checkpoint_buffer.clear()

    try:
        categories = _retry(cninfo.fetch_industry_categories, sleep) if pending else ()
    except Exception as exc:  # noqa: BLE001 - converted to a safe audit code
        error_code = _safe_error(exc)
        for code in pending:
            save_sector_checkpoint(
                _checkpoint(
                    provider="CNINFO",
                    dataset="sector",
                    partition_key=code,
                    status="FAILED",
                    captured_at=request.captured_at,
                    error_code=error_code,
                )
            )
            failures.append((code, error_code))
        categories = ()

    def previous_trade_date(value: date) -> date | None:
        return max(
            (day for day in request.trade_dates if day < value),
            default=value - timedelta(days=1),
        )

    if categories:
        for code in pending:
            try:
                changes = _retry(
                    lambda code=code: cninfo.fetch_industry_changes(
                        code, date(1990, 1, 1), end
                    ),
                    sleep,
                )
                rows = normalize_cninfo_memberships(
                    categories,
                    {code: changes},
                    previous_trade_date=previous_trade_date,
                )
                new_rows.extend(rows)
                if not rows:
                    confirmed_empty_codes.add(code)
                save_sector_checkpoint(
                    _checkpoint(
                        provider="CNINFO",
                        dataset="sector",
                        partition_key=code,
                        status="COMPLETE",
                        captured_at=request.captured_at,
                        details={"membership_count": len(rows)},
                    )
                )
            except Exception as exc:  # noqa: BLE001 - converted to safe audit data
                error_code = _safe_error(exc)
                failures.append((code, error_code))
                save_sector_checkpoint(
                    _checkpoint(
                        provider="CNINFO",
                        dataset="sector",
                        partition_key=code,
                        status="FAILED",
                        captured_at=request.captured_at,
                        error_code=error_code,
                    )
                )

    if checkpoint_buffer:
        repository.save_checkpoints(tuple(checkpoint_buffer))
        checkpoint_buffer.clear()
    row_count = repository.upsert_sector_memberships(new_rows, request.captured_at)
    all_rows = tuple(existing) + tuple(new_rows)
    expected = 0
    observed = 0
    mapped = 0
    unclassified = 0
    try:
        for day in request.trade_dates:
            active = membership_on(all_rows, day)
            universe = request.universe_by_date[day]
            expected += len(universe)
            mapped_on_day = universe.intersection(active)
            unclassified_on_day = universe.intersection(confirmed_empty_codes)
            mapped += len(mapped_on_day)
            unclassified += len(unclassified_on_day)
            observed += len(mapped_on_day.union(unclassified_on_day))
        coverage = _ratio(observed, expected)
    except Exception as exc:  # noqa: BLE001
        coverage = Decimal("0")
        failures.append(("coverage", _safe_error(exc)))

    error_code = failures[0][1] if failures else None
    if error_code is None and coverage < request.minimum_coverage:
        error_code = "COVERAGE_BELOW_THRESHOLD"
    return _run(
        dataset="sector",
        provider="CNINFO",
        start=start,
        end=end,
        status="FAILED" if error_code else "COMPLETE",
        row_count=row_count,
        captured_at=request.captured_at,
        error_code=error_code,
        expected_count=expected,
        coverage_ratio=coverage,
        details={
            "partition_count": len(codes),
            "failed_partitions": [code for code, _ in failures],
            "observed_count": observed,
            "mapped_count": mapped,
            "unclassified_count": unclassified,
        },
    )


def _recent_days(request: AlternativeReferenceSyncRequest) -> frozenset[date]:
    count = request.refresh_recent_trade_dates
    return frozenset(request.trade_dates[-count:] if count else ())


def _sync_st_day(
    request: AlternativeReferenceSyncRequest,
    day: date,
    baostock: BaoStockReferenceSource,
    repository: ReferenceRepository,
    sleep: Callable[[float], None],
    refresh_days: frozenset[date],
) -> ReferenceSyncRun:
    universe = request.universe_by_date[day]
    checkpoint = repository.load_checkpoint("BAOSTOCK", "st", day.isoformat())
    if checkpoint and checkpoint.status == "COMPLETE" and day not in refresh_days:
        observed = int(checkpoint.details.get("observed_count", 0))
        expected = int(checkpoint.details.get("expected_count", len(universe)))
        coverage = _ratio(observed, expected)
        return _run(
            dataset="st",
            provider="BAOSTOCK",
            start=day,
            end=day,
            status="COMPLETE" if coverage >= request.minimum_coverage else "FAILED",
            row_count=int(checkpoint.details.get("row_count", 0)),
            captured_at=request.captured_at,
            error_code=(
                None if coverage >= request.minimum_coverage else "COVERAGE_BELOW_THRESHOLD"
            ),
            expected_count=expected,
            coverage_ratio=coverage,
            details={"partition_key": day.isoformat(), "skipped": True},
        )

    try:
        statuses = _retry(lambda: baostock.fetch_security_statuses(day), sleep)
        by_code = {row.code: row for row in statuses}
        if len(by_code) != len(statuses):
            raise ValueError("duplicate BaoStock status")
        observed = len(universe.intersection(by_code))
        expected = len(universe)
        coverage = _ratio(observed, expected)
        relevant = tuple(by_code[code] for code in sorted(universe.intersection(by_code)))
        flags = normalize_baostock_risk_flags(relevant)
        row_count = repository.upsert_risk_flags(flags, request.captured_at)
        error_code = (
            None
            if coverage >= request.minimum_coverage
            else "COVERAGE_BELOW_THRESHOLD"
        )
    except Exception as exc:  # noqa: BLE001
        observed, expected, coverage, row_count = 0, len(universe), Decimal("0"), 0
        error_code = _safe_error(exc)

    status = "FAILED" if error_code else "COMPLETE"
    repository.save_checkpoint(
        _checkpoint(
            provider="BAOSTOCK",
            dataset="st",
            partition_key=day.isoformat(),
            status=status,
            captured_at=request.captured_at,
            error_code=error_code,
            details={
                "observed_count": observed,
                "expected_count": expected,
                "row_count": row_count,
            },
        )
    )
    return _run(
        dataset="st",
        provider="BAOSTOCK",
        start=day,
        end=day,
        status=status,
        row_count=row_count,
        captured_at=request.captured_at,
        error_code=error_code,
        expected_count=expected,
        coverage_ratio=coverage,
        details={"partition_key": day.isoformat(), "observed_count": observed},
    )


def _validate_announcement_pages(pages: Sequence[AnnouncementPage]) -> tuple[Announcement, ...]:
    if not pages:
        raise ValueError("announcement pages are required")
    first = pages[0]
    if first.page_no != 1:
        raise ValueError("announcement page sequence is incomplete")
    if first.page_count == 0:
        if first.total_count or first.records or len(pages) != 1:
            raise ValueError("empty announcement page is inconsistent")
        return ()
    if first.page_count != len(pages):
        raise ValueError("announcement page sequence is incomplete")
    records: list[Announcement] = []
    for expected_page, page in enumerate(pages, start=1):
        if (
            page.page_no != expected_page
            or page.page_count != first.page_count
            or page.total_count != first.total_count
            or page.page_size != first.page_size
        ):
            raise ValueError("announcement page metadata changed")
        records.extend(page.records)
    identities = [row.announcement_id for row in records]
    if len(records) != first.total_count or len(identities) != len(set(identities)):
        raise ValueError("announcement records do not match declared total")
    return tuple(records)


def _calendar_days(previous: date | None, current: date) -> tuple[date, ...]:
    start = current if previous is None else previous + timedelta(days=1)
    return tuple(start + timedelta(days=index) for index in range((current - start).days + 1))


def _sync_announcement_day(
    request: AlternativeReferenceSyncRequest,
    day: date,
    previous: date | None,
    announcement_source: CninfoReferenceSource,
    repository: ReferenceRepository,
    sleep: Callable[[float], None],
    refresh_days: frozenset[date],
) -> ReferenceSyncRun:
    partitions = _calendar_days(previous, day)
    all_records: list[Announcement] = []
    failures: list[tuple[str, str]] = []
    completed = 0
    force_refresh = day in refresh_days

    for natural_day in partitions:
        key = natural_day.isoformat()
        provider_name = announcement_source.provider_name
        checkpoint = repository.load_checkpoint(provider_name, "announcement", key)
        if checkpoint and checkpoint.status == "COMPLETE" and not force_refresh:
            completed += 1
            continue
        try:
            first = _retry(
                lambda natural_day=natural_day: announcement_source.fetch_announcement_page(
                    natural_day, 1
                ),
                sleep,
            )
            pages = [first]
            for page_no in range(2, first.page_count + 1):
                pages.append(
                    _retry(
                        lambda natural_day=natural_day, page_no=page_no: announcement_source.fetch_announcement_page(
                            natural_day, page_no
                        ),
                        sleep,
                    )
                )
            records = _validate_announcement_pages(pages)
            all_records.extend(records)
            completed += 1
            repository.save_checkpoint(
                _checkpoint(
                    provider=provider_name,
                    dataset="announcement",
                    partition_key=key,
                    status="COMPLETE",
                    captured_at=request.captured_at,
                    cursor_value=str(first.page_count),
                    details={
                        "page_count": first.page_count,
                        "record_count": len(records),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            error_code = _safe_error(exc)
            failures.append((key, error_code))
            repository.save_checkpoint(
                _checkpoint(
                    provider=provider_name,
                    dataset="announcement",
                    partition_key=key,
                    status="FAILED",
                    captured_at=request.captured_at,
                    error_code=error_code,
                )
            )

    trade_dates = frozenset(request.trade_dates)

    def next_trade_date(value: date) -> date:
        return min((item for item in request.trade_dates if item > value), default=_next_weekday(value))

    try:
        flags = normalize_cninfo_announcement_flags(
            all_records,
            is_trade_date=lambda value: value in trade_dates,
            next_trade_date=next_trade_date,
            fallback_date=day,
            source=announcement_source.provider_name,
        )
        row_count = repository.upsert_risk_flags(flags, request.captured_at)
    except Exception as exc:  # noqa: BLE001
        row_count = 0
        failures.append(("normalization", _safe_error(exc)))

    expected = len(partitions)
    coverage = _ratio(completed, expected)
    error_code = failures[0][1] if failures else None
    if error_code is None and coverage < request.minimum_coverage:
        error_code = "COVERAGE_BELOW_THRESHOLD"
    return _run(
        dataset="announcement",
        provider=announcement_source.provider_name,
        start=day,
        end=day,
        status="FAILED" if error_code else "COMPLETE",
        row_count=row_count,
        captured_at=request.captured_at,
        error_code=error_code,
        expected_count=expected,
        coverage_ratio=coverage,
        details={
            "partition_keys": [value.isoformat() for value in partitions],
            "failed_partitions": [key for key, _ in failures],
            "completed_partitions": completed,
        },
    )


def sync_alternative_reference_data(
    request: AlternativeReferenceSyncRequest,
    *,
    cninfo: CninfoReferenceSource,
    announcement_source: CninfoReferenceSource | None = None,
    baostock: BaoStockReferenceSource,
    repository: ReferenceRepository,
    sleep: Callable[[float], None] = default_sleep,
) -> tuple[ReferenceSyncRun, ...]:
    """Synchronize independent datasets without letting one failure mask another."""

    runs: list[ReferenceSyncRun] = []
    sector = _sync_sector(request, cninfo, repository, sleep)
    repository.save_sync_run(sector)
    runs.append(sector)

    refresh_days = _recent_days(request)
    session_factory = getattr(baostock, "session", None)
    session_manager = session_factory() if callable(session_factory) else nullcontext()
    with session_manager:
        for day in request.trade_dates:
            st = _sync_st_day(request, day, baostock, repository, sleep, refresh_days)
            repository.save_sync_run(st)
            runs.append(st)

    resolved_announcement_source = announcement_source or cninfo
    previous = None
    for day in request.trade_dates:
        announcement = _sync_announcement_day(
            request,
            day,
            previous,
            resolved_announcement_source,
            repository,
            sleep,
            refresh_days,
        )
        repository.save_sync_run(announcement)
        runs.append(announcement)
        previous = day
    return tuple(runs)
