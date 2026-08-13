from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import text


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def _fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def position_event_fingerprint(
    source: str,
    captured_at: datetime,
    code: str,
    shares_before: int,
    shares_after: int,
    event_type: str,
) -> str:
    observed = captured_at
    if observed.tzinfo is not None and observed.utcoffset() is not None:
        observed = observed.astimezone(timezone.utc)
    return _fingerprint(
        {
            "source": source,
            "captured_at": observed.isoformat(),
            "code": str(code).zfill(6),
            "shares_before": int(shares_before),
            "shares_after": int(shares_after),
            "event_type": event_type,
        }
    )


def decision_event_fingerprint(
    cycle_id: int | str,
    event_type: str,
    effective_trade_date: date,
    action: str,
    evidence: Mapping[str, Any],
) -> str:
    return _fingerprint(
        {
            "cycle_id": str(cycle_id),
            "event_type": event_type,
            "effective_trade_date": effective_trade_date.isoformat(),
            "action": action,
            "evidence": evidence,
        }
    )


def _mysql_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class AdvisorLedgerRepository:
    """Append-only ledger writes over a caller-owned SQLAlchemy connection."""

    def __init__(self, connection) -> None:
        self.connection = connection

    def load_active_cycle(self, code: str):
        return self.connection.execute(
            text(
                """
                SELECT * FROM advisor_decision_cycles
                WHERE ts_code = :code
                  AND status IN ('ACTIVE', 'REVIEW_DUE', 'EXTENDED')
                ORDER BY cycle_id DESC LIMIT 1
                """
            ),
            {"code": str(code).zfill(6)},
        ).mappings().first()

    def open_legacy_closed_cycle(
        self,
        *,
        code: str,
        name: str,
        trade_date: date,
        source: str = "LEGACY_IMPORT",
    ) -> int:
        result = self.connection.execute(
            text(
                """
                INSERT INTO advisor_decision_cycles
                  (ts_code, name, started_trade_date, review_trade_date,
                   expiry_trade_date, initial_action, current_action,
                   status, source)
                VALUES
                  (:code, :name, :d, :d, :d, 'UNKNOWN', '已清仓', 'CLOSED', :source)
                """
            ),
            {"code": str(code).zfill(6), "name": name, "d": trade_date, "source": source},
        )
        return int(result.lastrowid)

    def append_position_event(self, event, *, cycle_id: int | None = None) -> bool:
        fingerprint = position_event_fingerprint(
            event.source,
            event.broker_captured_at,
            event.code,
            event.shares_before,
            event.shares_after,
            event.event_type,
        )
        result = self.connection.execute(
            text(
                """
                INSERT IGNORE INTO portfolio_position_events
                  (cycle_id, ts_code, name, event_type, shares_before, shares_after,
                   shares_delta, cost_before, cost_after, execution_price,
                   realized_pnl, plan_compliance, evidence_json, source,
                   broker_captured_at, event_fingerprint)
                VALUES
                  (:cycle_id, :code, :name, :event_type, :shares_before, :shares_after,
                   :shares_delta, :cost_before, :cost_after, :execution_price,
                   :realized_pnl, :plan_compliance, :evidence, :source,
                   :captured_at, :fingerprint)
                """
            ),
            {
                "cycle_id": cycle_id,
                "code": event.code,
                "name": event.name,
                "event_type": event.event_type,
                "shares_before": event.shares_before,
                "shares_after": event.shares_after,
                "shares_delta": event.shares_delta,
                "cost_before": event.cost_before,
                "cost_after": event.cost_after,
                "execution_price": event.execution_price,
                "realized_pnl": event.realized_pnl,
                "plan_compliance": event.plan_compliance,
                "evidence": json.dumps(event.evidence, ensure_ascii=False, default=_json_default),
                "source": event.source,
                "captured_at": _mysql_datetime(event.broker_captured_at),
                "fingerprint": fingerprint,
            },
        )
        return int(result.rowcount or 0) == 1

    def append_decision_event(
        self,
        *,
        cycle_id: int,
        event_type: str,
        previous_action: str | None,
        new_action: str | None,
        reason: Mapping[str, Any],
        evidence: Mapping[str, Any],
        source: str,
        observed_at: datetime,
        effective_trade_date: date,
    ) -> bool:
        fingerprint = decision_event_fingerprint(
            cycle_id,
            event_type,
            effective_trade_date,
            new_action or "",
            evidence,
        )
        result = self.connection.execute(
            text(
                """
                INSERT IGNORE INTO advisor_decision_events
                  (cycle_id, event_type, previous_action, new_action, reason_json,
                   evidence_json, source, observed_at, effective_trade_date,
                   event_fingerprint)
                VALUES
                  (:cycle_id, :event_type, :previous_action, :new_action, :reason,
                   :evidence, :source, :observed_at, :effective_date, :fingerprint)
                """
            ),
            {
                "cycle_id": cycle_id,
                "event_type": event_type,
                "previous_action": previous_action,
                "new_action": new_action,
                "reason": json.dumps(reason, ensure_ascii=False, default=_json_default),
                "evidence": json.dumps(evidence, ensure_ascii=False, default=_json_default),
                "source": source,
                "observed_at": _mysql_datetime(observed_at),
                "effective_date": effective_trade_date,
                "fingerprint": fingerprint,
            },
        )
        return int(result.rowcount or 0) == 1

    def close_cycle(self, cycle_id: int, *, action: str = "已清仓") -> None:
        result = self.connection.execute(
            text(
                """
                UPDATE advisor_decision_cycles
                SET current_action = :action, status = 'CLOSED'
                WHERE cycle_id = :cycle_id
                  AND status IN ('ACTIVE', 'REVIEW_DUE', 'EXTENDED')
                """
            ),
            {"cycle_id": cycle_id, "action": action},
        )
        if int(result.rowcount or 0) not in (0, 1):
            raise RuntimeError("unexpected cycle update count")

    def load_memory_context(self, code: str, *, limit: int = 20) -> dict[str, Any]:
        cycle = self.load_active_cycle(code)
        rows = self.connection.execute(
            text(
                """
                SELECT e.* FROM advisor_decision_events e
                JOIN advisor_decision_cycles c ON c.cycle_id = e.cycle_id
                WHERE c.ts_code = :code
                ORDER BY e.event_id DESC LIMIT :limit_rows
                """
            ),
            {"code": str(code).zfill(6), "limit_rows": int(limit)},
        ).mappings().all()
        return {"active_cycle": dict(cycle) if cycle else None, "decision_events": [dict(row) for row in rows]}
