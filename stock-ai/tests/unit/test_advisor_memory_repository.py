from __future__ import annotations

from datetime import date, datetime, timezone

from stock_ai.advisor_memory.repository import (
    decision_event_fingerprint,
    position_event_fingerprint,
)


CAPTURED = datetime(2026, 8, 13, 5, 0, tzinfo=timezone.utc)


def test_position_fingerprint_is_stable_and_sensitive_to_delta() -> None:
    first = position_event_fingerprint("jywg", CAPTURED, "600000", 500, 0, "CLOSED")
    again = position_event_fingerprint("jywg", CAPTURED, "600000", 500, 0, "CLOSED")
    different = position_event_fingerprint("jywg", CAPTURED, "600000", 500, 200, "REDUCED")

    assert first == again
    assert len(first) == 64
    assert first != different


def test_decision_fingerprint_normalizes_mapping_order() -> None:
    first = decision_event_fingerprint(
        "cycle-1",
        "HARD_EVENT",
        date(2026, 8, 13),
        "已清仓",
        {"shares_before": 500, "shares_after": 0},
    )
    second = decision_event_fingerprint(
        "cycle-1",
        "HARD_EVENT",
        date(2026, 8, 13),
        "已清仓",
        {"shares_after": 0, "shares_before": 500},
    )

    assert first == second
