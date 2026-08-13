#!/usr/bin/env python3
"""Backfill append-only advisor position memory from runtime snapshots."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from sqlalchemy import text

from stock_ai.advisor_memory.position_sync import (
    PositionEventDraft,
    PositionProjection,
    diff_position_facts,
)
from stock_ai.advisor_memory.repository import AdvisorLedgerRepository


@dataclass(frozen=True)
class LegacyCycleDraft:
    code: str
    name: str
    trade_date: date
    initial_action: str
    current_action: str = "已清仓"
    status: str = "CLOSED"
    source: str = "LEGACY_IMPORT"


def recover_legacy_cycle(
    *,
    code: str,
    name: str,
    trade_date: date,
    prior_action: str | None,
) -> LegacyCycleDraft:
    return LegacyCycleDraft(
        code=str(code).zfill(6),
        name=name,
        trade_date=trade_date,
        initial_action=str(prior_action or "").strip() or "UNKNOWN",
    )


def _as_decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _as_datetime(value: Any, fallback: datetime) -> datetime:
    return value if isinstance(value, datetime) else fallback


def reconstruct_events(
    *,
    prior_snapshots: Sequence[Mapping[str, Any]],
    broker_rows: Sequence[Mapping[str, Any]],
    source: str,
    captured_at: datetime,
) -> tuple[PositionEventDraft, ...]:
    broker_codes = {
        str(row["ts_code"]).zfill(6)
        for row in broker_rows
        if int(row.get("shares") or 0) == 0
    }
    previous: dict[str, PositionProjection] = {}
    prior_action: dict[str, str | None] = {}
    for row in prior_snapshots:
        code = str(row["ts_code"]).zfill(6)
        shares = int(row.get("shares") or 0)
        if shares <= 0 or code in previous or code not in broker_codes:
            continue
        previous[code] = PositionProjection(
            code=code,
            name=str(row.get("name") or code),
            shares=shares,
            cost_price=_as_decimal(row.get("cost_price")),
        )
        prior_action[code] = row.get("action_note")

    incoming = [
        SimpleNamespace(
            code=str(row["ts_code"]).zfill(6),
            name=str(row.get("name") or row["ts_code"]),
            shares=int(row.get("shares") or 0),
            cost_price=_as_decimal(row.get("cost_price")),
            broker_captured_at=_as_datetime(row.get("broker_captured_at"), captured_at),
        )
        for row in broker_rows
        if str(row["ts_code"]).zfill(6) in previous
    ]
    drafts = diff_position_facts(
        previous,
        incoming,
        source=source,
        captured_at=captured_at,
    )
    return tuple(
        PositionEventDraft(
            **{
                **draft.__dict__,
                "evidence": {
                    **dict(draft.evidence),
                    "prior_action": prior_action.get(draft.code),
                    "backfill": True,
                },
            }
        )
        for draft in drafts
        if draft.event_type == "CLOSED"
    )


def _load_runtime_rows(connection, start: date, end: date):
    prior_rows = connection.execute(
        text(
            """
            SELECT snapshot_date, snapshot_slot, ts_code, name, shares,
                   cost_price, action_note
            FROM portfolio_positions_daily
            WHERE snapshot_date >= :start AND snapshot_date < :end
            ORDER BY snapshot_date DESC,
                     FIELD(snapshot_slot, 'eod', 'sync', 'manual'), ts_code
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()
    current_rows = connection.execute(
        text(
            """
            SELECT ts_code, name, shares, cost_price, broker_captured_at
            FROM portfolio_positions
            WHERE source = 'jywg' AND shares = 0 AND is_active = 0
              AND DATE(broker_captured_at) BETWEEN :start AND :end
            ORDER BY ts_code
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()
    return prior_rows, current_rows


def apply_backfill(
    connection,
    events: Sequence[PositionEventDraft],
    *,
    apply: bool,
) -> dict[str, int]:
    repository = AdvisorLedgerRepository(connection)
    proposed = len(events)
    inserted_positions = 0
    inserted_decisions = 0
    if not apply:
        return {
            "proposed": proposed,
            "position_events": 0,
            "decision_events": 0,
            "duplicates": 0,
        }

    duplicates = 0
    for event in events:
        if repository.position_event_exists(event):
            duplicates += 1
            continue
        initial_action = str(event.evidence.get("prior_action") or "").strip() or "UNKNOWN"
        cycle_id = repository.open_legacy_closed_cycle(
            code=event.code,
            name=event.name,
            trade_date=event.broker_captured_at.date(),
            initial_action=initial_action,
        )
        if not repository.append_position_event(event, cycle_id=cycle_id):
            raise RuntimeError("position event fingerprint raced during backfill")
        inserted_positions += 1
        if repository.append_decision_event(
            cycle_id=cycle_id,
            event_type="HARD_EVENT",
            previous_action=initial_action,
            new_action="已清仓",
            reason={"hard_event_kind": "POSITION_CHANGE", "backfill": True},
            evidence={
                "event_type": "CLOSED",
                "shares_before": event.shares_before,
                "shares_after": 0,
                "execution_price_known": False,
            },
            source="LEGACY_IMPORT",
            observed_at=event.broker_captured_at,
            effective_trade_date=event.broker_captured_at.date(),
        ):
            inserted_decisions += 1
    return {
        "proposed": proposed,
        "position_events": inserted_positions,
        "decision_events": inserted_decisions,
        "duplicates": duplicates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="补录不可覆盖的投顾仓位记忆")
    parser.add_argument("--from-date", type=date.fromisoformat, required=True)
    parser.add_argument("--to-date", type=date.fromisoformat, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.to_date < args.from_date:
        parser.error("--to-date must be on or after --from-date")

    from scripts.tools.portfolio_db import get_engine

    engine = get_engine()
    if engine is None:
        raise RuntimeError("未配置 MYSQL_URL")
    fallback = datetime.combine(args.to_date, time(15, 0), tzinfo=timezone.utc)
    if args.apply:
        with engine.begin() as connection:
            prior, current = _load_runtime_rows(connection, args.from_date, args.to_date)
            capture_values = [row.get("broker_captured_at") for row in current]
            captured_at = max((x for x in capture_values if isinstance(x, datetime)), default=fallback)
            events = reconstruct_events(
                prior_snapshots=prior,
                broker_rows=current,
                source="LEGACY_IMPORT",
                captured_at=captured_at,
            )
            stats = apply_backfill(connection, events, apply=True)
    else:
        with engine.connect() as connection:
            prior, current = _load_runtime_rows(connection, args.from_date, args.to_date)
            capture_values = [row.get("broker_captured_at") for row in current]
            captured_at = max((x for x in capture_values if isinstance(x, datetime)), default=fallback)
            events = reconstruct_events(
                prior_snapshots=prior,
                broker_rows=current,
                source="LEGACY_IMPORT",
                captured_at=captured_at,
            )
            stats = apply_backfill(connection, events, apply=False)
    print(
        "advisor memory backfill: "
        f"proposed={stats['proposed']} position_events={stats['position_events']} "
        f"decision_events={stats['decision_events']} duplicates={stats['duplicates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
