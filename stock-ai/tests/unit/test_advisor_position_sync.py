from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from scripts.tools.jywg_portfolio_sync import BrokerPosition
from stock_ai.advisor_memory.position_sync import (
    PositionProjection,
    diff_position_facts,
)


CAPTURED = datetime(2026, 8, 13, 5, 0, tzinfo=timezone.utc)


def broker_position(
    *,
    shares: int,
    cost: str = "6.80",
    code: str = "600000",
) -> BrokerPosition:
    return BrokerPosition(
        code=code,
        name="测试股份",
        asset_type="stock",
        shares=shares,
        available_shares=shares,
        cost_price=Decimal(cost),
        current_price=Decimal("7.01"),
        market_value=Decimal("0") if shares == 0 else Decimal("3505.00"),
        position_pnl=None,
        position_pnl_pct=None,
        daily_pnl=None,
        daily_pnl_pct=None,
        status="",
        action="",
        broker_captured_at=CAPTURED,
    )


def projection(*, shares: int, cost: str = "6.80") -> PositionProjection:
    return PositionProjection(
        code="600000",
        name="测试股份",
        shares=shares,
        cost_price=Decimal(cost),
        broker_captured_at=datetime(2026, 8, 12, 7, 0),
    )


def test_positive_to_zero_creates_close_event_without_inventing_execution_price() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500)},
        [broker_position(shares=0, cost="0")],
        source="jywg",
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "CLOSED"
    assert (event.shares_before, event.shares_after, event.shares_delta) == (500, 0, -500)
    assert event.execution_price is None
    assert event.realized_pnl is None
    assert event.plan_compliance == "UNKNOWN"


def test_share_increase_and_reduction_have_distinct_event_types() -> None:
    added = diff_position_facts(
        {"600000": projection(shares=500)},
        [broker_position(shares=700)],
        source="jywg",
    )
    reduced = diff_position_facts(
        {"600000": projection(shares=500)},
        [broker_position(shares=200)],
        source="jywg",
    )

    assert added[0].event_type == "ADDED"
    assert added[0].shares_delta == 200
    assert reduced[0].event_type == "REDUCED"
    assert reduced[0].shares_delta == -300


def test_new_positive_position_creates_open_event() -> None:
    events = diff_position_facts({}, [broker_position(shares=500)], source="jywg")

    assert events[0].event_type == "OPENED"
    assert events[0].shares_before == 0


def test_unchanged_shares_with_changed_cost_creates_cost_adjustment() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500, cost="6.80")},
        [broker_position(shares=500, cost="6.75")],
        source="jywg",
    )

    assert events[0].event_type == "COST_ADJUSTED"
    assert events[0].shares_delta == 0


def test_unchanged_position_creates_no_event() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500, cost="6.80")},
        [broker_position(shares=500, cost="6.80")],
        source="jywg",
    )

    assert events == ()


def test_missing_incoming_row_closes_previous_active_position() -> None:
    events = diff_position_facts(
        {"600000": projection(shares=500)},
        [],
        source="jywg",
        captured_at=CAPTURED,
    )

    assert events[0].event_type == "CLOSED"
    assert events[0].shares_after == 0
