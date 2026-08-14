from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Mapping, Sequence

from sqlalchemy import text

from .repository import AdvisorLedgerRepository
from .state_machine import resolve_cycle_dates


@dataclass(frozen=True)
class PositionProjection:
    code: str
    name: str
    shares: int
    cost_price: Decimal
    broker_captured_at: datetime | None = None


@dataclass(frozen=True)
class PositionEventDraft:
    code: str
    name: str
    event_type: str
    shares_before: int
    shares_after: int
    shares_delta: int
    cost_before: Decimal | None
    cost_after: Decimal | None
    execution_price: Decimal | None
    realized_pnl: Decimal | None
    plan_compliance: str
    source: str
    broker_captured_at: datetime
    evidence: Mapping[str, Any] = field(default_factory=dict)


def _event_type(before: int, after: int) -> str | None:
    if before == after:
        return None
    if before == 0 and after > 0:
        return "OPENED"
    if before > 0 and after == 0:
        return "CLOSED"
    if after > before:
        return "ADDED"
    return "REDUCED"


def diff_position_facts(
    previous: Mapping[str, PositionProjection],
    incoming: Sequence[Any],
    *,
    source: str,
    captured_at: datetime | None = None,
) -> tuple[PositionEventDraft, ...]:
    """Compare current projections with one complete broker position capture."""
    incoming_by_code = {str(item.code).zfill(6): item for item in incoming}
    if captured_at is None and incoming:
        captured_at = incoming[0].broker_captured_at
    if captured_at is None:
        raise ValueError("captured_at is required for an empty incoming capture")

    codes = sorted(set(previous) | set(incoming_by_code))
    events: list[PositionEventDraft] = []
    for code in codes:
        old = previous.get(code)
        new = incoming_by_code.get(code)
        before = int(old.shares if old else 0)
        after = int(new.shares if new else 0)
        before_cost = old.cost_price if old else None
        after_cost = new.cost_price if new else None
        kind = _event_type(before, after)
        if kind is None and before > 0 and before_cost != after_cost:
            kind = "COST_ADJUSTED"
        if kind is None:
            continue
        name = str((new.name if new else old.name) or code)
        events.append(
            PositionEventDraft(
                code=code,
                name=name,
                event_type=kind,
                shares_before=before,
                shares_after=after,
                shares_delta=after - before,
                cost_before=before_cost,
                cost_after=after_cost,
                execution_price=None,
                realized_pnl=None,
                plan_compliance="UNKNOWN",
                source=source,
                broker_captured_at=captured_at,
                evidence={"capture": "broker_position"},
            )
        )
    return tuple(events)


def _load_active_projections(connection) -> dict[str, PositionProjection]:
    rows = connection.execute(
        text(
            """
            SELECT ts_code, name, shares, cost_price, broker_captured_at
            FROM portfolio_positions
            WHERE is_active = 1
            FOR UPDATE
            """
        )
    ).mappings().all()
    return {
        str(row["ts_code"]).zfill(6): PositionProjection(
            code=str(row["ts_code"]).zfill(6),
            name=str(row["name"] or row["ts_code"]),
            shares=int(row["shares"] or 0),
            cost_price=Decimal(str(row["cost_price"] or 0)),
            broker_captured_at=row["broker_captured_at"],
        )
        for row in rows
    }


def _confirmed_cycle_dates(start: date) -> tuple[date, ...] | None:
    from stock_ai.trading_calendar import next_confirmed_a_share_trade_date

    dates: list[date] = []
    cursor = start
    for _ in range(5):
        confirmed = next_confirmed_a_share_trade_date(cursor)
        if confirmed is None:
            return None
        dates.append(confirmed)
        cursor = confirmed + timedelta(days=1)
    return tuple(dates)


def _open_confirmed_buy_point_cycle(
    repository: AdvisorLedgerRepository,
    draft: PositionEventDraft,
    captured_at: datetime,
) -> int | None:
    plan = repository.load_latest_triggered_buy_point_plan(draft.code)
    if plan is None:
        return None
    trading_days = _confirmed_cycle_dates(captured_at.date())
    if trading_days is None:
        return None
    started = trading_days[0]
    review, expiry = resolve_cycle_dates(started, trading_days)
    trigger_plan = {
        key: plan[key]
        for key in (
            "plan_id",
            "structure_id",
            "trigger_price",
            "invalidation_price",
            "target_2r",
            "risk_distance",
            "maximum_shares",
            "valid_through_trade_date",
            "rule_version",
        )
        if key in plan
    }
    cycle = repository.open_cycle(
        code=draft.code,
        name=draft.name,
        started_trade_date=started,
        review_trade_date=review,
        expiry_trade_date=expiry,
        initial_action="持有观察",
        current_action="持有观察",
        trigger_plan=trigger_plan,
        selection_source="buy_point_v3",
        selection_plan_id=str(plan["plan_id"]),
    )
    return int(cycle.cycle_id)


def _sync_with_connection(positions, account, *, source: str, connection) -> dict[str, int]:
    from scripts.tools.portfolio_db import sync_broker_positions_and_account

    captured_at = account.broker_captured_at
    previous = _load_active_projections(connection)
    drafts = diff_position_facts(
        previous,
        positions,
        source=source,
        captured_at=captured_at,
    )
    repository = AdvisorLedgerRepository(connection)
    position_event_count = 0
    decision_event_count = 0

    for draft in drafts:
        active_cycle = repository.load_active_cycle(draft.code)
        cycle_id = int(active_cycle["cycle_id"]) if active_cycle else None
        if draft.event_type == "OPENED" and cycle_id is None:
            cycle_id = _open_confirmed_buy_point_cycle(
                repository,
                draft,
                captured_at,
            )
        if draft.event_type == "CLOSED" and cycle_id is None:
            cycle_id = repository.open_legacy_closed_cycle(
                code=draft.code,
                name=draft.name,
                trade_date=captured_at.date(),
            )
        inserted = repository.append_position_event(draft, cycle_id=cycle_id)
        if not inserted:
            continue
        position_event_count += 1
        if draft.event_type == "CLOSED" and cycle_id is not None:
            previous_action = (
                str(active_cycle["current_action"])
                if active_cycle
                else "UNKNOWN"
            )
            if repository.append_decision_event(
                cycle_id=cycle_id,
                event_type="HARD_EVENT",
                previous_action=previous_action,
                new_action="已清仓",
                reason={"hard_event_kind": "POSITION_CHANGE"},
                evidence={
                    "event_type": "CLOSED",
                    "shares_before": draft.shares_before,
                    "shares_after": draft.shares_after,
                },
                source=source,
                observed_at=captured_at,
                effective_trade_date=captured_at.date(),
            ):
                decision_event_count += 1
            if active_cycle:
                repository.close_cycle(cycle_id, action="已清仓")

    stats = sync_broker_positions_and_account(
        positions,
        account,
        source=source,
        connection=connection,
    )
    stats["position_events"] = position_event_count
    stats["decision_events"] = decision_event_count
    stats["active_positions"] = sum(1 for item in positions if int(item.shares) > 0)
    return stats


def sync_broker_facts_with_memory(
    positions,
    account,
    *,
    source: str = "jywg",
    engine=None,
    connection=None,
) -> dict[str, int]:
    """Atomically append position memory and update current broker projections."""
    normalized_source = (source or "jywg").strip() or "jywg"
    if connection is not None:
        return _sync_with_connection(
            positions,
            account,
            source=normalized_source,
            connection=connection,
        )
    if engine is None:
        from scripts.tools.portfolio_db import get_engine

        engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL，无法同步")
    with engine.begin() as conn:
        return _sync_with_connection(
            positions,
            account,
            source=normalized_source,
            connection=conn,
        )
