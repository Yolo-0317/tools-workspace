from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.daily_sync import DailyBar, synchronize_critical_daily_bars


def _bar(trade_date: str) -> DailyBar:
    return DailyBar(
        ts_code="600000",
        exch_code="SH",
        trade_date=date.fromisoformat(trade_date),
        open=10.0,
        high=10.5,
        low=9.8,
        close=10.2,
        pre_close=10.0,
        change_amount=0.2,
        pct_chg=2.0,
        vol=1000,
        amount=100.0,
    )


class FakeRepository:
    def __init__(self, bars: list[DailyBar] | None = None) -> None:
        self.bars = bars or []
        self.runs: list[dict[str, object]] = []

    def get_recent_bars(self, code: str, limit: int) -> list[DailyBar]:
        return sorted(
            [bar for bar in self.bars if bar.ts_code == code],
            key=lambda bar: bar.trade_date,
            reverse=True,
        )[:limit]

    def upsert_daily_bars(self, bars: list[DailyBar]) -> int:
        existing = {(bar.ts_code, bar.trade_date): bar for bar in self.bars}
        for bar in bars:
            existing[(bar.ts_code, bar.trade_date)] = bar
        self.bars = list(existing.values())
        return len(bars)

    def record_sync_run(self, payload: dict[str, object]) -> None:
        self.runs.append(payload)


def _rows(last_date: str = "2026-08-07") -> list[list[str]]:
    return [
        ["2026-08-05", "9.90", "10.00", "10.20", "9.80", "1000", "100000", "", "1.00", "0.10"],
        ["2026-08-06", "10.00", "10.10", "10.30", "9.90", "1100", "110000", "", "1.00", "0.10"],
        [last_date, "10.10", "10.20", "10.50", "9.80", "1200", "120000", "", "0.99", "0.10"],
    ]


def test_ready_database_does_not_fetch() -> None:
    repository = FakeRepository([_bar("2026-08-07"), _bar("2026-08-06"), _bar("2026-08-05")])

    def unexpected_fetcher(codes: list[str], limit: int) -> dict[str, list[list[str]]]:
        raise AssertionError("fetcher should not run")

    result = synchronize_critical_daily_bars(
        repository,
        ["600000"],
        target_date=date(2026, 8, 7),
        fetcher=unexpected_fetcher,
    )

    assert result["status"] == "READY"
    assert result["upserted_rows"] == 0
    assert len(repository.runs) == 1


def test_stale_database_uses_fetcher_and_upserts() -> None:
    repository = FakeRepository()
    result = synchronize_critical_daily_bars(
        repository,
        ["600000"],
        target_date=date(2026, 8, 7),
        fetcher=lambda codes, limit: {"600000": _rows()},
    )

    assert result["status"] == "UPDATED"
    assert result["ready_codes"] == ["600000"]
    assert result["upserted_rows"] == 3
    assert repository.get_recent_bars("600000", 1)[0].amount == 120.0


def test_mismatched_latest_source_date_fails_safely() -> None:
    repository = FakeRepository()
    result = synchronize_critical_daily_bars(
        repository,
        ["600000"],
        target_date=date(2026, 8, 7),
        fetcher=lambda codes, limit: {"600000": _rows("2026-08-06")},
    )

    assert result["status"] == "FAILED"
    assert result["failed_codes"] == ["600000"]
    assert "latest source date" in result["failure_reasons"]["600000"]
