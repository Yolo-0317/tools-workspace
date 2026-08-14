from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from stock_ai.buy_point_selection.reference_data import (
    ReferenceCheckpoint,
    ReferenceSyncRun,
    RiskFlag,
    SectorMembership,
)
from stock_ai.buy_point_selection.reference_sources import (
    Announcement,
    AnnouncementPage,
    IndustryCategory,
    IndustryChange,
    ProviderFailure,
    SecurityStatus,
)
from stock_ai.buy_point_selection.reference_sync import (
    AlternativeReferenceSyncRequest,
    sync_alternative_reference_data,
)


NOW = datetime(2025, 8, 11, 10, tzinfo=timezone.utc)


class MemoryRepository:
    def __init__(self) -> None:
        self.memberships: dict[tuple[str, date, str], SectorMembership] = {}
        self.flags: dict[tuple[str, str, date, str], RiskFlag] = {}
        self.runs: list[ReferenceSyncRun] = []
        self.checkpoints: dict[tuple[str, str, str], ReferenceCheckpoint] = {}
        self.membership_queries = 0
        self.bulk_checkpoint_queries = 0
        self.bulk_checkpoint_writes = 0

    def upsert_sector_memberships(self, rows, captured_at):
        for row in rows:
            self.memberships[(row.code, row.valid_from, row.source)] = row
        return len(rows)

    def upsert_risk_flags(self, rows, captured_at):
        for row in rows:
            self.flags[(row.code, row.flag_type, row.effective_from, row.source)] = row
        return len(rows)

    def save_sync_run(self, run):
        self.runs.append(run)

    def save_checkpoint(self, checkpoint):
        self.checkpoints[
            (checkpoint.provider, checkpoint.dataset, checkpoint.partition_key)
        ] = checkpoint

    def save_checkpoints(self, checkpoints):
        self.bulk_checkpoint_writes += 1
        for checkpoint in checkpoints:
            self.save_checkpoint(checkpoint)

    def load_checkpoint(self, provider, dataset, partition_key):
        return self.checkpoints.get((provider, dataset, partition_key))

    def load_checkpoints(self, provider, dataset, partition_keys):
        self.bulk_checkpoint_queries += 1
        return {
            key: checkpoint
            for key in partition_keys
            if (
                checkpoint := self.checkpoints.get((provider, dataset, key))
            ) is not None
        }

    def memberships_between(self, start, end):
        self.membership_queries += 1
        return tuple(
            row
            for row in self.memberships.values()
            if row.valid_from <= end and (row.valid_to is None or row.valid_to >= start)
        )


class FakeCninfoProvider:
    provider_name = "CNINFO"

    def __init__(self) -> None:
        self.industry_calls: list[str] = []
        self.announcement_calls: list[tuple[date, int]] = []
        self.failed_industry_code: str | None = None
        self.failed_announcement_day: date | None = None
        self.risky_announcement = False
        self.multiple_historical_changes = False

    def fetch_industry_categories(self):
        return (IndustryCategory("801000", "", "农林牧渔", 1, None),)

    def fetch_industry_changes(self, code, start, end):
        self.industry_calls.append(code)
        if code == self.failed_industry_code:
            raise ProviderFailure("CNINFO", "industry_changes", "PROVIDER_UNAVAILABLE")
        values = (
            IndustryChange(
                code,
                date(2024, 1, 2),
                "申银万国行业分类标准",
                "801000",
            ),
        )
        if self.multiple_historical_changes:
            values = (
                IndustryChange(
                    code,
                    date(2020, 1, 2),
                    "申银万国行业分类标准",
                    "801000",
                ),
                IndustryChange(
                    code,
                    date(2022, 1, 4),
                    "申银万国行业分类标准",
                    "801120",
                ),
            )
        return values

    def fetch_announcement_page(self, day, page_no):
        self.announcement_calls.append((day, page_no))
        if day == self.failed_announcement_day and page_no == 2:
            raise ProviderFailure("CNINFO", "announcements", "PROVIDER_UNAVAILABLE")
        if day == self.failed_announcement_day:
            return AnnouncementPage(
                records=(self._announcement(day, "first"),),
                total_count=2,
                page_no=1,
                page_size=1,
                page_count=2,
            )
        records = (
            (self._announcement(day, "risk"),) if self.risky_announcement else ()
        )
        return AnnouncementPage(
            records=records,
            total_count=len(records),
            page_no=page_no,
            page_size=30,
            page_count=1 if records else 0,
        )

    @staticmethod
    def _announcement(day: date, suffix: str) -> Announcement:
        return Announcement(
            "600001",
            f"{day.isoformat()}-{suffix}",
            "公司收到中国证监会立案调查告知书",
            datetime(day.year, day.month, day.day, 10, tzinfo=timezone.utc),
            f"https://static.cninfo.com.cn/{day.isoformat()}-{suffix}.PDF",
        )


class FakeBaoStockProvider:
    provider_name = "BAOSTOCK"

    def __init__(self, missing: int = 0) -> None:
        self.calls: list[date] = []
        self.missing = missing

    def fetch_security_statuses(self, day):
        self.calls.append(day)
        count = max(0, 100 - self.missing)
        return tuple(
            SecurityStatus(f"{600001 + index:06d}", "普通股份", "1", day)
            for index in range(count)
        )


def _request(*days: date, size: int = 2, refresh: int = 2):
    universe = frozenset(f"{600001 + index:06d}" for index in range(size))
    return AlternativeReferenceSyncRequest(
        trade_dates=tuple(days),
        universe_by_date={day: universe for day in days},
        captured_at=NOW,
        minimum_coverage=Decimal("0.98"),
        refresh_recent_trade_dates=refresh,
    )


def test_sync_marks_daily_st_and_announcement_coverage_complete() -> None:
    request = _request(date(2025, 8, 5), date(2025, 8, 6))
    repository = MemoryRepository()

    runs = sync_alternative_reference_data(
        request,
        cninfo=FakeCninfoProvider(),
        baostock=FakeBaoStockProvider(),
        repository=repository,
        sleep=lambda _: None,
    )

    assert {(run.dataset, run.status) for run in runs} == {
        ("sector", "COMPLETE"),
        ("st", "COMPLETE"),
        ("announcement", "COMPLETE"),
    }
    assert repository.membership_queries == 1


def test_complete_checkpoint_skips_old_partition_but_refreshes_last_two() -> None:
    days = (date(2025, 8, 4), date(2025, 8, 5), date(2025, 8, 6))
    repository = MemoryRepository()
    for day in days:
        repository.save_checkpoint(
            ReferenceCheckpoint(
                "BAOSTOCK",
                "st",
                day.isoformat(),
                None,
                "COMPLETE",
                None,
                {"observed_count": 2, "expected_count": 2, "row_count": 0},
                NOW - timedelta(days=1),
            )
        )
    baostock = FakeBaoStockProvider()

    sync_alternative_reference_data(
        _request(*days, refresh=2),
        cninfo=FakeCninfoProvider(),
        baostock=baostock,
        repository=repository,
        sleep=lambda _: None,
    )

    assert baostock.calls == list(days[-2:])


def test_sector_checkpoint_lookup_is_batched_for_the_full_universe() -> None:
    repository = MemoryRepository()

    sync_alternative_reference_data(
        _request(date(2025, 8, 6), size=100),
        cninfo=FakeCninfoProvider(),
        baostock=FakeBaoStockProvider(),
        repository=repository,
        sleep=lambda _: None,
    )

    assert repository.bulk_checkpoint_queries == 1
    assert repository.bulk_checkpoint_writes == 2


def test_complete_sector_checkpoint_without_fact_is_refetched() -> None:
    day = date(2025, 8, 6)
    repository = MemoryRepository()
    repository.save_checkpoint(
        ReferenceCheckpoint(
            "CNINFO",
            "sector",
            "600001",
            None,
            "COMPLETE",
            None,
            {"membership_count": 1},
            NOW - timedelta(days=1),
        )
    )
    cninfo = FakeCninfoProvider()

    runs = sync_alternative_reference_data(
        _request(day, size=1),
        cninfo=cninfo,
        baostock=FakeBaoStockProvider(),
        repository=repository,
        sleep=lambda _: None,
    )

    assert cninfo.industry_calls == ["600001"]
    assert next(run for run in runs if run.dataset == "sector").status == "COMPLETE"


def test_same_day_complete_empty_sector_checkpoint_is_not_reprobed() -> None:
    day = date(2025, 8, 6)
    repository = MemoryRepository()
    repository.save_checkpoint(
        ReferenceCheckpoint(
            "CNINFO",
            "sector",
            "600001",
            None,
            "COMPLETE",
            None,
            {"membership_count": 0},
            NOW,
        )
    )
    cninfo = FakeCninfoProvider()

    sync_alternative_reference_data(
        _request(day, size=1),
        cninfo=cninfo,
        baostock=FakeBaoStockProvider(),
        repository=repository,
        sleep=lambda _: None,
    )

    assert cninfo.industry_calls == []


def test_missing_announcement_page_fails_only_announcement_dataset() -> None:
    day = date(2025, 8, 6)
    cninfo = FakeCninfoProvider()
    cninfo.failed_announcement_day = day

    runs = sync_alternative_reference_data(
        _request(day),
        cninfo=cninfo,
        baostock=FakeBaoStockProvider(),
        repository=MemoryRepository(),
        sleep=lambda _: None,
    )

    assert all(run.status == "COMPLETE" for run in runs if run.dataset != "announcement")
    announcement = next(run for run in runs if run.dataset == "announcement")
    assert announcement.status == "FAILED"
    assert announcement.error_code == "PROVIDER_UNAVAILABLE"


def test_baostock_97_percent_coverage_is_not_complete() -> None:
    day = date(2025, 8, 6)
    runs = sync_alternative_reference_data(
        _request(day, size=100),
        cninfo=FakeCninfoProvider(),
        baostock=FakeBaoStockProvider(missing=3),
        repository=MemoryRepository(),
        sleep=lambda _: None,
    )

    st = next(run for run in runs if run.dataset == "st")
    assert st.status == "FAILED"
    assert st.coverage_ratio == Decimal("0.97")
    assert st.error_code == "COVERAGE_BELOW_THRESHOLD"


def test_weekend_announcement_partitions_are_included_in_monday() -> None:
    friday = date(2025, 8, 8)
    monday = date(2025, 8, 11)
    cninfo = FakeCninfoProvider()

    sync_alternative_reference_data(
        _request(friday, monday),
        cninfo=cninfo,
        baostock=FakeBaoStockProvider(),
        repository=MemoryRepository(),
        sleep=lambda _: None,
    )

    assert {day for day, page in cninfo.announcement_calls if page == 1} == {
        friday,
        date(2025, 8, 9),
        date(2025, 8, 10),
        monday,
    }


def test_failed_industry_code_prevents_broad_sector_complete_run() -> None:
    cninfo = FakeCninfoProvider()
    cninfo.failed_industry_code = "600002"

    runs = sync_alternative_reference_data(
        _request(date(2025, 8, 6)),
        cninfo=cninfo,
        baostock=FakeBaoStockProvider(),
        repository=MemoryRepository(),
        sleep=lambda _: None,
    )

    sector = next(run for run in runs if run.dataset == "sector")
    assert sector.status == "FAILED"
    assert sector.error_code == "PROVIDER_UNAVAILABLE"


def test_historical_industry_intervals_do_not_require_calendar_before_sync_window() -> None:
    cninfo = FakeCninfoProvider()
    cninfo.multiple_historical_changes = True
    original_categories = cninfo.fetch_industry_categories
    cninfo.fetch_industry_categories = lambda: original_categories() + (
        IndustryCategory("801120", "", "食品饮料", 1, None),
    )

    runs = sync_alternative_reference_data(
        _request(date(2025, 8, 5), date(2025, 8, 6)),
        cninfo=cninfo,
        baostock=FakeBaoStockProvider(),
        repository=MemoryRepository(),
        sleep=lambda _: None,
    )

    sector = next(run for run in runs if run.dataset == "sector")
    assert sector.status == "COMPLETE"


def test_repeated_sync_keeps_fact_keys_stable() -> None:
    day = date(2025, 8, 6)
    repository = MemoryRepository()
    cninfo = FakeCninfoProvider()
    cninfo.risky_announcement = True
    request = _request(day)

    first = sync_alternative_reference_data(
        request,
        cninfo=cninfo,
        baostock=FakeBaoStockProvider(),
        repository=repository,
        sleep=lambda _: None,
    )
    first_keys = set(repository.flags)
    second = sync_alternative_reference_data(
        request,
        cninfo=cninfo,
        baostock=FakeBaoStockProvider(),
        repository=repository,
        sleep=lambda _: None,
    )

    assert set(repository.flags) == first_keys
    assert [run.run_id for run in first] == [run.run_id for run in second]
