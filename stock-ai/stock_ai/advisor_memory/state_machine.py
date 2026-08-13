from __future__ import annotations

from datetime import date
from typing import Sequence

from .models import (
    CycleStatus,
    CycleTransition,
    DecisionCycle,
    HardEvent,
    HardEventKind,
)


OPEN_STATUSES = frozenset(
    {CycleStatus.ACTIVE, CycleStatus.REVIEW_DUE, CycleStatus.EXTENDED}
)


def resolve_cycle_dates(
    start: date,
    trading_days: Sequence[date],
) -> tuple[date, date]:
    """Return day-three review and day-five expiry from an ordered calendar."""
    ordered = tuple(trading_days)
    if any(current <= previous for previous, current in zip(ordered, ordered[1:])):
        raise ValueError("trading days must be strictly increasing")
    try:
        start_index = ordered.index(start)
    except ValueError as exc:
        raise ValueError("start date is not a trading day") from exc
    if start_index + 4 >= len(ordered):
        raise ValueError("five trading days are required")
    return ordered[start_index + 2], ordered[start_index + 4]


def _hard_event_transition(event: HardEvent) -> CycleTransition:
    status = (
        CycleStatus.CLOSED
        if event.kind is HardEventKind.POSITION_CHANGE
        and event.suggested_action == "已清仓"
        else CycleStatus.INVALIDATED
    )
    return CycleTransition(
        status=status,
        action=event.suggested_action,
        event_type="HARD_EVENT",
        relation="失效",
        hard_event=event,
    )


def advance_cycle(
    cycle: DecisionCycle,
    *,
    as_of: date,
    hard_events: Sequence[HardEvent],
    extend_at_review: bool,
) -> CycleTransition:
    """Resolve one deterministic decision transition for the supplied date."""
    if cycle.status not in OPEN_STATUSES:
        raise ValueError("cycle is not active")
    if as_of < cycle.started_trade_date:
        raise ValueError("as_of precedes cycle start")

    events = tuple(hard_events)
    if events:
        return _hard_event_transition(events[0])

    if as_of >= cycle.expiry_trade_date:
        return CycleTransition(
            status=CycleStatus.CLOSED,
            action=cycle.current_action,
            event_type="CYCLE_CLOSED",
            relation="到期",
        )

    if as_of >= cycle.review_trade_date:
        if extend_at_review:
            return CycleTransition(
                status=CycleStatus.EXTENDED,
                action=cycle.current_action,
                event_type="CYCLE_EXTENDED",
                relation="维持",
            )
        return CycleTransition(
            status=CycleStatus.CLOSED,
            action=cycle.current_action,
            event_type="CYCLE_CLOSED",
            relation="到期",
        )

    return CycleTransition(
        status=CycleStatus.ACTIVE,
        action=cycle.current_action,
        event_type="ACTION_MAINTAINED",
        relation="维持",
    )
