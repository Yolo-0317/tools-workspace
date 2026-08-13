from __future__ import annotations

from datetime import date

import pytest

from stock_ai.advisor_memory.models import (
    CycleStatus,
    DecisionCycle,
    HardEvent,
    HardEventKind,
)
from stock_ai.advisor_memory.state_machine import advance_cycle, resolve_cycle_dates


TRADING_DAYS = tuple(
    date(2026, 8, day) for day in (10, 11, 12, 13, 14, 17)
)


def active_cycle(*, status: CycleStatus = CycleStatus.ACTIVE) -> DecisionCycle:
    return DecisionCycle(
        cycle_id=1,
        code="600000",
        name="测试股份",
        started_trade_date=TRADING_DAYS[0],
        review_trade_date=TRADING_DAYS[2],
        expiry_trade_date=TRADING_DAYS[4],
        initial_action="持有观察",
        current_action="持有观察",
        status=status,
    )


def test_cycle_dates_use_trading_days_instead_of_calendar_days() -> None:
    review, expiry = resolve_cycle_dates(TRADING_DAYS[0], TRADING_DAYS)

    assert review == date(2026, 8, 12)
    assert expiry == date(2026, 8, 14)


def test_cycle_date_resolution_rejects_incomplete_calendar() -> None:
    with pytest.raises(ValueError, match="five trading days"):
        resolve_cycle_dates(TRADING_DAYS[0], TRADING_DAYS[:4])


def test_normal_day_cannot_change_action() -> None:
    transition = advance_cycle(
        active_cycle(),
        as_of=TRADING_DAYS[1],
        hard_events=(),
        extend_at_review=False,
    )

    assert transition.action == "持有观察"
    assert transition.status is CycleStatus.ACTIVE
    assert transition.event_type == "ACTION_MAINTAINED"
    assert transition.relation == "维持"


def test_review_day_can_extend_to_day_five() -> None:
    transition = advance_cycle(
        active_cycle(),
        as_of=TRADING_DAYS[2],
        hard_events=(),
        extend_at_review=True,
    )

    assert transition.status is CycleStatus.EXTENDED
    assert transition.event_type == "CYCLE_EXTENDED"
    assert transition.action == "持有观察"


def test_review_day_closes_when_not_extended() -> None:
    transition = advance_cycle(
        active_cycle(),
        as_of=TRADING_DAYS[2],
        hard_events=(),
        extend_at_review=False,
    )

    assert transition.status is CycleStatus.CLOSED
    assert transition.event_type == "CYCLE_CLOSED"


def test_stop_loss_interrupts_before_review() -> None:
    event = HardEvent(
        kind=HardEventKind.PRICE_TRIGGER,
        suggested_action="退出观察",
        evidence={"trigger": "stop_loss", "price": 9.5},
        source="price_rule",
    )

    transition = advance_cycle(
        active_cycle(),
        as_of=TRADING_DAYS[1],
        hard_events=(event,),
        extend_at_review=False,
    )

    assert transition.status is CycleStatus.INVALIDATED
    assert transition.action == "退出观察"
    assert transition.event_type == "HARD_EVENT"
    assert transition.relation == "失效"


def test_position_close_closes_cycle_instead_of_invalidating_it() -> None:
    event = HardEvent(
        kind=HardEventKind.POSITION_CHANGE,
        suggested_action="已清仓",
        evidence={"shares_before": 500, "shares_after": 0},
        source="jywg",
    )

    transition = advance_cycle(
        active_cycle(),
        as_of=TRADING_DAYS[1],
        hard_events=(event,),
        extend_at_review=False,
    )

    assert transition.status is CycleStatus.CLOSED
    assert transition.action == "已清仓"
    assert transition.relation == "失效"


def test_day_five_must_close_even_when_extension_is_requested() -> None:
    transition = advance_cycle(
        active_cycle(status=CycleStatus.EXTENDED),
        as_of=TRADING_DAYS[4],
        hard_events=(),
        extend_at_review=True,
    )

    assert transition.status is CycleStatus.CLOSED
    assert transition.event_type == "CYCLE_CLOSED"


def test_closed_cycle_cannot_advance() -> None:
    with pytest.raises(ValueError, match="not active"):
        advance_cycle(
            active_cycle(status=CycleStatus.CLOSED),
            as_of=TRADING_DAYS[4],
            hard_events=(),
            extend_at_review=False,
        )
