from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.evidence import (
    CaptureRecorder,
    EvidenceSnapshot,
    is_chip_snapshot_for_trade_date,
    is_fresh,
)


class FakeRepository:
    def __init__(self) -> None:
        self.snapshots = []
        self.attempts = []

    def save_snapshot(self, snapshot) -> None:
        self.snapshots.append(snapshot)

    def save_capture_attempt(self, attempt) -> None:
        self.attempts.append(attempt)


def test_valid_quote_creates_snapshot_and_success_attempt() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 9, 9, 45, tzinfo=timezone.utc)
    snapshot = CaptureRecorder(repository).record_payload(
        kind="quote",
        code="600000.SH",
        source="eastmoney-opencli",
        parser_version="quote-v1",
        data={
            "price": 10.2,
            "change_pct": 1.0,
            "amount": 100.0,
            "turnover": 2.0,
            "volume_ratio": 1.5,
        },
        raw_evidence_ref="fixture:quote-600000",
        started_at=now - timedelta(seconds=2),
        finished_at=now,
    )

    assert snapshot is not None
    assert snapshot.code == "600000"
    assert repository.attempts[0].status == "SUCCESS"
    assert len(repository.snapshots) == 1
    assert is_fresh(snapshot, now + timedelta(seconds=299))
    assert not is_fresh(snapshot, now + timedelta(seconds=301))


def test_invalid_payload_is_audited_but_not_saved_as_snapshot() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 9, 9, 45, tzinfo=timezone.utc)
    snapshot = CaptureRecorder(repository).record_payload(
        kind="quote",
        code="600000",
        source="eastmoney-opencli",
        parser_version="quote-v1",
        data={"price": 10.2, "change_pct": 1.0},
        raw_evidence_ref="fixture:broken-quote",
        started_at=now,
        finished_at=now,
    )

    assert snapshot is None
    assert repository.attempts[0].status == "PARSE_ERROR"
    assert repository.attempts[0].field_completeness == 2 / 5
    assert repository.snapshots == []


def test_source_error_is_always_audited() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 9, 9, 45, tzinfo=timezone.utc)
    CaptureRecorder(repository).record_source_error(
        kind="order_book",
        code="600000",
        source="eastmoney-opencli",
        parser_version="order-book-v1",
        started_at=now,
        finished_at=now,
        error=RuntimeError("detached page"),
        retry_count=2,
    )

    assert repository.attempts[0].status == "SOURCE_ERROR"
    assert repository.attempts[0].retry_count == 2
    assert repository.snapshots == []


def test_chip_freshness_uses_the_expected_trading_date_not_wall_clock_hours() -> None:
    friday_close = datetime(2026, 8, 7, 7, 0, tzinfo=timezone.utc)
    snapshot = EvidenceSnapshot(
        snapshot_id="chip-friday",
        code="603011",
        kind="chip",
        as_of=friday_close,
        source="eastmoney-opencli",
        parser_version="chip-v1",
        data={
            "source_trade_date": "2026-08-07",
            "cost_90_low": 18.0,
            "cost_90_high": 22.0,
            "average_cost": 20.0,
            "profit_ratio": 70.0,
            "concentration": 10.0,
            "input_bar_count": 210,
            "method": "eastmoney-cyq-v1",
        },
        raw_evidence_ref="fixture:chip-friday",
    )

    assert not is_fresh(snapshot, datetime(2026, 8, 10, 1, 0, tzinfo=timezone.utc))
    assert is_chip_snapshot_for_trade_date(snapshot, date(2026, 8, 7))
    assert not is_chip_snapshot_for_trade_date(snapshot, date(2026, 8, 10))
