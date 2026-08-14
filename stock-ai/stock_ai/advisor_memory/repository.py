from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import text

from .models import CycleStatus, CycleTransition, DecisionCycle


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

    def load_active_cycle_model(self, code: str) -> DecisionCycle | None:
        row = self.load_active_cycle(code)
        if row is None:
            return None
        trigger_plan = row.get("trigger_plan_json")
        if isinstance(trigger_plan, str):
            try:
                trigger_plan = json.loads(trigger_plan)
            except json.JSONDecodeError:
                trigger_plan = {}
        return DecisionCycle(
            cycle_id=int(row["cycle_id"]),
            code=str(row["ts_code"]).zfill(6),
            name=str(row["name"] or row["ts_code"]),
            started_trade_date=row["started_trade_date"],
            review_trade_date=row["review_trade_date"],
            expiry_trade_date=row["expiry_trade_date"],
            initial_action=str(row["initial_action"]),
            current_action=str(row["current_action"]),
            status=CycleStatus(str(row["status"])),
            trigger_plan=dict(trigger_plan or {}),
        )

    def open_cycle(
        self,
        *,
        code: str,
        name: str,
        started_trade_date: date,
        review_trade_date: date,
        expiry_trade_date: date,
        initial_action: str,
        current_action: str,
        trigger_plan: Mapping[str, Any] | None = None,
        selection_source: str | None = None,
        selection_plan_id: str | None = None,
    ) -> DecisionCycle:
        result = self.connection.execute(
            text(
                """
                INSERT INTO advisor_decision_cycles
                  (ts_code, name, started_trade_date, review_trade_date,
                   expiry_trade_date, initial_action, current_action,
                   trigger_plan_json, selection_source, selection_plan_id,
                   status, source)
                VALUES
                  (:code, :name, :started, :review, :expiry,
                   :initial_action, :current_action, :trigger_plan,
                   :selection_source, :selection_plan_id, 'ACTIVE', 'advisor')
                """
            ),
            {
                "code": str(code).zfill(6),
                "name": name,
                "started": started_trade_date,
                "review": review_trade_date,
                "expiry": expiry_trade_date,
                "initial_action": initial_action,
                "current_action": current_action,
                "trigger_plan": json.dumps(trigger_plan or {}, ensure_ascii=False, default=_json_default),
                "selection_source": selection_source,
                "selection_plan_id": selection_plan_id,
            },
        )
        cycle_id = int(result.lastrowid)
        self.append_decision_event(
            cycle_id=cycle_id,
            event_type="CYCLE_OPENED",
            previous_action=None,
            new_action=current_action,
            reason={"cycle_days": "3-5"},
            evidence={"trigger_plan": dict(trigger_plan or {})},
            source="advisor",
            observed_at=datetime.combine(started_trade_date, datetime.min.time()),
            effective_trade_date=started_trade_date,
        )
        return DecisionCycle(
            cycle_id=cycle_id,
            code=str(code).zfill(6),
            name=name,
            started_trade_date=started_trade_date,
            review_trade_date=review_trade_date,
            expiry_trade_date=expiry_trade_date,
            initial_action=initial_action,
            current_action=current_action,
            status=CycleStatus.ACTIVE,
            trigger_plan=dict(trigger_plan or {}),
        )

    def load_latest_triggered_buy_point_plan(self, code: str):
        return self.connection.execute(
            text(
                """
                SELECT plan_id, code, structure_id, trigger_price,
                       invalidation_price, target_2r, risk_distance,
                       maximum_shares, valid_through_trade_date, rule_version
                FROM stt_trade_plans
                WHERE code = :code
                  AND schema_version = '1.3'
                  AND plan_state = 'TRIGGERED'
                  AND data_status = 'VALID'
                ORDER BY analysis_date DESC, as_of DESC LIMIT 1
                """
            ),
            {"code": str(code).zfill(6)},
        ).mappings().first()

    def attach_trigger_plan(
        self,
        cycle: DecisionCycle,
        trigger_plan: Mapping[str, Any],
        *,
        as_of: date,
        observed_at: datetime,
    ) -> None:
        """Backfill a plan only when an older active cycle has none."""
        result = self.connection.execute(
            text(
                """
                UPDATE advisor_decision_cycles
                SET trigger_plan_json = :plan
                WHERE cycle_id = :cycle_id
                  AND (trigger_plan_json IS NULL OR JSON_LENGTH(trigger_plan_json) = 0)
                """
            ),
            {
                "cycle_id": int(cycle.cycle_id),
                "plan": json.dumps(trigger_plan, ensure_ascii=False, default=_json_default),
            },
        )
        if int(result.rowcount or 0) == 1:
            self.append_decision_event(
                cycle_id=int(cycle.cycle_id),
                event_type="CORRECTION",
                previous_action=cycle.current_action,
                new_action=cycle.current_action,
                reason={"relation": "补齐执行计划"},
                evidence={"trigger_plan": dict(trigger_plan)},
                source="advisor_plan_backfill",
                observed_at=observed_at,
                effective_trade_date=as_of,
            )

    def record_transition(
        self,
        cycle: DecisionCycle,
        transition: CycleTransition,
        *,
        as_of: date,
        observed_at: datetime,
    ) -> None:
        evidence = (
            dict(transition.hard_event.evidence)
            if transition.hard_event is not None
            else {"relation": transition.relation}
        )
        source = transition.hard_event.source if transition.hard_event else "advisor"
        self.append_decision_event(
            cycle_id=int(cycle.cycle_id),
            event_type=transition.event_type,
            previous_action=cycle.current_action,
            new_action=transition.action,
            reason={"relation": transition.relation},
            evidence=evidence,
            source=source,
            observed_at=observed_at,
            effective_trade_date=as_of,
        )
        if transition.status != cycle.status or transition.action != cycle.current_action:
            self.connection.execute(
                text(
                    """
                    UPDATE advisor_decision_cycles
                    SET current_action=:action, status=:status
                    WHERE cycle_id=:cycle_id
                    """
                ),
                {
                    "cycle_id": int(cycle.cycle_id),
                    "action": transition.action,
                    "status": transition.status.value,
                },
            )

    def open_legacy_closed_cycle(
        self,
        *,
        code: str,
        name: str,
        trade_date: date,
        initial_action: str = "UNKNOWN",
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
                  (:code, :name, :d, :d, :d, :initial_action, '已清仓', 'CLOSED', :source)
                """
            ),
            {
                "code": str(code).zfill(6),
                "name": name,
                "d": trade_date,
                "initial_action": initial_action,
                "source": source,
            },
        )
        return int(result.lastrowid)

    def position_event_exists(self, event) -> bool:
        fingerprint = position_event_fingerprint(
            event.source,
            event.broker_captured_at,
            event.code,
            event.shares_before,
            event.shares_after,
            event.event_type,
        )
        value = self.connection.execute(
            text(
                "SELECT 1 FROM portfolio_position_events "
                "WHERE event_fingerprint = :fingerprint LIMIT 1"
            ),
            {"fingerprint": fingerprint},
        ).scalar()
        return value is not None

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
