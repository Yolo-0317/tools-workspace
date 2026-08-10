from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.capture import QuoteFundPayload, capture_quote_and_fund
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
