from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.capture import (
    ChipPayload,
    QuoteFundPayload,
    capture_chip,
    capture_quote_and_fund,
)
from short_term_trading.chip import ChipMetrics
from short_term_trading.evidence import CaptureRecorder


class FakeRepository:
    def __init__(self) -> None:
        self.snapshots = []
        self.attempts = []

    def save_snapshot(self, snapshot) -> None:
        self.snapshots.append(snapshot)

    def save_capture_attempt(self, attempt) -> None:
        self.attempts.append(attempt)


def test_capture_writes_valid_quote_and_fund_snapshots() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)
    capture_quote_and_fund(
        "600000",
        CaptureRecorder(repository),
        fetcher=lambda code: QuoteFundPayload(
            code="600000",
            price=10.2,
            change_pct=1.0,
            info_text="成交额：12345 换手率：2.3 量比：1.8",
            fund_flow_text="主力净流入：23.5",
        ),
        now=now,
    )

    assert [snapshot.kind for snapshot in repository.snapshots] == ["quote", "fund_flow"]
    assert [attempt.status for attempt in repository.attempts] == ["SUCCESS", "SUCCESS"]


def test_capture_audits_missing_page_field_without_snapshot() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)
    capture_quote_and_fund(
        "600000",
        CaptureRecorder(repository),
        fetcher=lambda code: QuoteFundPayload(
            code="600000",
            price=10.2,
            change_pct=1.0,
            info_text="成交额：12345",
            fund_flow_text="主力净流入：23.5",
        ),
        now=now,
    )

    assert [snapshot.kind for snapshot in repository.snapshots] == ["fund_flow"]
    assert repository.attempts[0].status == "PARSE_ERROR"


def chip_payload(*, concentration: float = 17.1) -> ChipPayload:
    return ChipPayload(
        code="603011",
        metrics=ChipMetrics(
            source_trade_date=date(2026, 8, 10),
            cost_90_low=18.6,
            cost_90_high=23.5,
            average_cost=21.4,
            profit_ratio=72.3,
            concentration=concentration,
            input_bar_count=210,
        ),
        raw_evidence_ref="eastmoney-opencli:kline:603011:2026-08-10",
    )


def test_capture_writes_a_valid_chip_snapshot_with_audit_fields() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 10, 10, 30, tzinfo=timezone.utc)

    capture_chip(
        "603011",
        CaptureRecorder(repository),
        fetcher=lambda code: chip_payload(),
        now=now,
    )

    assert [snapshot.kind for snapshot in repository.snapshots] == ["chip"]
    assert repository.snapshots[0].data == {
        "source_trade_date": "2026-08-10",
        "cost_90_low": 18.6,
        "cost_90_high": 23.5,
        "average_cost": 21.4,
        "profit_ratio": 72.3,
        "concentration": 17.1,
        "input_bar_count": 210,
        "method": "eastmoney-cyq-v1",
    }
    assert repository.attempts[0].status == "SUCCESS"


def test_capture_rejects_an_out_of_range_chip_percentage() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 10, 10, 30, tzinfo=timezone.utc)

    capture_chip(
        "603011",
        CaptureRecorder(repository),
        fetcher=lambda code: chip_payload(concentration=101.0),
        now=now,
    )

    assert repository.snapshots == []
    assert repository.attempts[0].status == "PARSE_ERROR"
    assert "concentration" in (repository.attempts[0].error_message or "")


def test_capture_audits_a_chip_source_failure() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 10, 10, 30, tzinfo=timezone.utc)

    def broken_fetcher(code: str) -> ChipPayload:
        raise RuntimeError("detached page")

    capture_chip(
        "603011",
        CaptureRecorder(repository),
        fetcher=broken_fetcher,
        now=now,
    )

    assert repository.snapshots == []
    assert repository.attempts[0].kind == "chip"
    assert repository.attempts[0].status == "SOURCE_ERROR"
