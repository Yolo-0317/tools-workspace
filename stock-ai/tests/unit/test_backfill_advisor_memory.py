from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from scripts.analysis.backfill_advisor_memory import (
    recover_legacy_cycle,
    reconstruct_events,
)


CAPTURED = datetime(2026, 8, 13, 5, 0, tzinfo=timezone.utc)


def test_backfill_reconstructs_close_from_last_positive_snapshot() -> None:
    proposed = reconstruct_events(
        prior_snapshots=[
            {
                "ts_code": "600000",
                "name": "测试股份",
                "shares": 500,
                "cost_price": Decimal("6.80"),
                "action_note": None,
            }
        ],
        broker_rows=[
            {
                "ts_code": "600000",
                "name": "测试股份",
                "shares": 0,
                "cost_price": Decimal("0"),
                "broker_captured_at": CAPTURED,
            }
        ],
        source="LEGACY_IMPORT",
        captured_at=CAPTURED,
    )

    assert len(proposed) == 1
    assert proposed[0].event_type == "CLOSED"
    assert proposed[0].shares_before == 500
    assert proposed[0].execution_price is None
    assert proposed[0].realized_pnl is None
    assert proposed[0].plan_compliance == "UNKNOWN"


def test_backfill_ignores_rows_that_were_already_zero() -> None:
    proposed = reconstruct_events(
        prior_snapshots=[
            {"ts_code": "600000", "name": "测试股份", "shares": 0, "cost_price": 0}
        ],
        broker_rows=[
            {"ts_code": "600000", "name": "测试股份", "shares": 0, "cost_price": 0}
        ],
        source="LEGACY_IMPORT",
        captured_at=CAPTURED,
    )

    assert proposed == ()


def test_backfill_does_not_invent_missing_decision() -> None:
    cycle = recover_legacy_cycle(
        code="600000",
        name="测试股份",
        trade_date=date(2026, 8, 13),
        prior_action=None,
    )

    assert cycle.source == "LEGACY_IMPORT"
    assert cycle.initial_action == "UNKNOWN"
    assert cycle.current_action == "已清仓"
    assert cycle.status == "CLOSED"


def test_backfill_preserves_recoverable_prior_action() -> None:
    cycle = recover_legacy_cycle(
        code="600000",
        name="测试股份",
        trade_date=date(2026, 8, 13),
        prior_action="减仓观察",
    )

    assert cycle.initial_action == "减仓观察"
