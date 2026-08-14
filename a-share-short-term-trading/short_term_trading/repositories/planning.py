"""Persistence for market, planning, risk, and intraday decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from ..contracts import (
    CandidateV1,
    CandidateV2,
    CandidateV3,
    DecisionSnapshotV1,
    ForwardSelectionRunV1,
    IntradayDecisionV1,
    MarketStateV1,
    PlanEventV1,
    RiskDecisionV1,
    TradePlanV1,
    TradePlanV2,
    TradePlanV3,
    validate_code,
)
from .connection import (
    DatabaseHandle,
    contract_values,
    json_dumps,
    read_connection,
    restore_contract,
    utc_naive,
    write_connection,
)


@dataclass(frozen=True)
class BuyPointBundle:
    candidate: CandidateV3
    plan: TradePlanV3
    initial_event: PlanEventV1
    forward_run: ForwardSelectionRunV1


@dataclass(frozen=True)
class ForwardGateSummary:
    distinct_dates: int
    resolved_plans: int
    integrity_violations: int
    eligible: bool


class PlanningRepository:
    def __init__(self, connection: DatabaseHandle) -> None:
        self._connection = connection

    def _save(self, table: str, model: Any, json_fields: dict[str, str]) -> None:
        values = contract_values(model, json_fields)
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        with write_connection(self._connection) as connection:
            connection.execute(text(f"INSERT IGNORE INTO {table} ({columns}) VALUES ({parameters})"), values)

    def _get(self, table: str, key: str, value: str, model_type: Any, json_fields: dict[str, str]) -> Any:
        with read_connection(self._connection) as connection:
            row = connection.execute(
                text(f"SELECT * FROM {table} WHERE {key} = :value"), {"value": value}
            ).mappings().first()
        return None if row is None else restore_contract(model_type, row, json_fields)

    def save_market_state(self, state: MarketStateV1) -> None:
        self._save("stt_market_states", state, {"reasons": "reasons_json", "evidence_refs": "evidence_refs_json"})

    def get_market_state(self, state_id: str) -> MarketStateV1 | None:
        return self._get("stt_market_states", "state_id", state_id, MarketStateV1, {"reasons": "reasons_json", "evidence_refs": "evidence_refs_json"})

    def get_latest_market_state(
        self, trading_date: date, *, source: str | None = None
    ) -> MarketStateV1 | None:
        source_clause = " AND source = :source" if source is not None else ""
        statement = text(
            "SELECT * FROM stt_market_states "
            "WHERE trading_date = :trading_date AND data_status = 'VALID'"
            f"{source_clause} ORDER BY as_of DESC, created_at DESC LIMIT 1"
        )
        parameters: dict[str, object] = {"trading_date": trading_date}
        if source is not None:
            parameters["source"] = source
        with read_connection(self._connection) as connection:
            row = connection.execute(
                statement, parameters
            ).mappings().first()
        return None if row is None else restore_contract(
            MarketStateV1,
            row,
            {"reasons": "reasons_json", "evidence_refs": "evidence_refs_json"},
        )

    def save_candidate(self, candidate: CandidateV1) -> None:
        self._save("stt_candidates", candidate, {"rejected_reasons": "rejected_reasons_json", "evidence_refs": "evidence_refs_json"})

    def get_candidate(self, candidate_id: str) -> CandidateV1 | None:
        return self._get("stt_candidates", "candidate_id", candidate_id, CandidateV1, {"rejected_reasons": "rejected_reasons_json", "evidence_refs": "evidence_refs_json"})

    def upsert_candidate(self, candidate: CandidateV2) -> None:
        json_fields = {
            "source_strategies": "source_strategies_json",
            "rejected_reasons": "rejected_reasons_json",
            "evidence_refs": "evidence_refs_json",
        }
        values = contract_values(candidate, json_fields)
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        mutable = (
            "as_of",
            "data_status",
            "name",
            "setup_score",
            "liquidity_score",
            "trend_score",
            "catalyst_score",
            "sector",
            "source_strategies_json",
            "executable_status",
            "rejected_reasons_json",
            "evidence_refs_json",
        )
        updates = ", ".join(
            f"{name} = IF(source = VALUES(source), VALUES({name}), {name})"
            for name in mutable
        )
        statement = text(
            f"INSERT INTO stt_candidates ({columns}) VALUES ({parameters}) "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )
        with write_connection(self._connection) as connection:
            connection.execute(statement, values)

    def get_candidate_v2(self, candidate_id: str) -> CandidateV2 | None:
        return self._get(
            "stt_candidates",
            "candidate_id",
            candidate_id,
            CandidateV2,
            {
                "source_strategies": "source_strategies_json",
                "rejected_reasons": "rejected_reasons_json",
                "evidence_refs": "evidence_refs_json",
            },
        )

    @staticmethod
    def _candidate_v3_values(candidate: CandidateV3) -> dict[str, Any]:
        values = contract_values(
            candidate,
            {
                "sector_metrics": "sector_metrics_json",
                "missing_fields": "missing_fields_json",
                "rejected_reasons": "rejected_reasons_json",
                "evidence_refs": "evidence_refs_json",
            },
        )
        values.update(
            {
                "setup_score": candidate.pattern_quality * Decimal("100"),
                "liquidity_score": Decimal("0"),
                "trend_score": Decimal("0"),
                "catalyst_score": Decimal("0"),
                "sector": candidate.sector or "UNKNOWN",
                "source_strategies_json": json_dumps(("buy-point-selection",)),
            }
        )
        return values

    @staticmethod
    def _plan_v3_values(plan: TradePlanV3) -> dict[str, Any]:
        values = contract_values(plan, {"evidence_refs": "evidence_refs_json"})
        values.pop("valid_session_count")
        valid_until = datetime.combine(
            plan.valid_through_trade_date,
            time(23, 59, 59),
            tzinfo=timezone.utc,
        )
        values.update(
            {
                "status": "WAIT_ENTRY" if plan.plan_state == "PREPARED" else "NO_TRADE",
                "entry_ceiling": plan.trigger_price,
                "pullback_low": plan.invalidation_price,
                "pullback_high": plan.trigger_price,
                "first_reduce_price": plan.target_2r,
                "atr": plan.risk_distance,
                "chip_trade_date": plan.analysis_date,
                "portfolio_status": (
                    "APPROVED" if plan.selection_tier == "FORMAL" else "NOT_APPROVED"
                ),
                "valid_until": utc_naive(valid_until),
            }
        )
        return values

    @staticmethod
    def _event_values(event: PlanEventV1) -> dict[str, Any]:
        return contract_values(event, {"evidence_refs": "evidence_refs_json"})

    @staticmethod
    def _forward_run_values(run: ForwardSelectionRunV1) -> dict[str, Any]:
        return contract_values(
            run, {"integrity_violations": "integrity_violations_json"}
        )

    @staticmethod
    def _insert_ignore(connection: Any, table: str, values: dict[str, Any]) -> None:
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        connection.execute(
            text(f"INSERT IGNORE INTO {table} ({columns}) VALUES ({parameters})"),
            values,
        )

    def save_buy_point_bundle(self, bundle: BuyPointBundle) -> None:
        self.save_buy_point_run(
            ((bundle.candidate, bundle.plan, bundle.initial_event),),
            bundle.forward_run,
        )

    def save_buy_point_run(
        self,
        rows: tuple[
            tuple[CandidateV3, TradePlanV3 | None, PlanEventV1 | None], ...
        ],
        forward_run: ForwardSelectionRunV1,
    ) -> None:
        with write_connection(self._connection) as connection:
            for candidate, plan, initial_event in rows:
                self._insert_ignore(
                    connection, "stt_candidates", self._candidate_v3_values(candidate)
                )
                if plan is not None and initial_event is not None:
                    self._insert_ignore(
                        connection, "stt_trade_plans", self._plan_v3_values(plan)
                    )
                    self._insert_ignore(
                        connection,
                        "stt_buy_point_plan_events",
                        self._event_values(initial_event),
                    )
            self._insert_ignore(
                connection,
                "stt_buy_point_forward_runs",
                self._forward_run_values(forward_run),
            )

    def get_candidate_v3(self, candidate_id: str) -> CandidateV3 | None:
        return self._get(
            "stt_candidates",
            "candidate_id",
            candidate_id,
            CandidateV3,
            {
                "sector_metrics": "sector_metrics_json",
                "missing_fields": "missing_fields_json",
                "rejected_reasons": "rejected_reasons_json",
                "evidence_refs": "evidence_refs_json",
            },
        )

    def save_plan(self, plan: TradePlanV1) -> None:
        self._save("stt_trade_plans", plan, {"evidence_refs": "evidence_refs_json"})

    def get_plan(self, plan_id: str) -> TradePlanV1 | None:
        return self._get("stt_trade_plans", "plan_id", plan_id, TradePlanV1, {"evidence_refs": "evidence_refs_json"})

    def upsert_plan(self, plan: TradePlanV2) -> None:
        values = contract_values(plan, {"evidence_refs": "evidence_refs_json"})
        values["pullback_low"] = values["trigger_price"]
        values["pullback_high"] = values["entry_ceiling"]
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        mutable = (
            "as_of",
            "data_status",
            "status",
            "trigger_price",
            "entry_ceiling",
            "pullback_low",
            "pullback_high",
            "invalidation_price",
            "first_reduce_price",
            "risk_distance",
            "risk_reward_ratio",
            "atr",
            "chip_trade_date",
            "maximum_shares",
            "market_status",
            "portfolio_status",
            "valid_until",
            "evidence_refs_json",
        )
        updates = ", ".join(
            f"{name} = IF(source = VALUES(source), VALUES({name}), {name})"
            for name in mutable
        )
        statement = text(
            f"INSERT INTO stt_trade_plans ({columns}) VALUES ({parameters}) "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )
        with write_connection(self._connection) as connection:
            connection.execute(statement, values)

    def get_plan_v2(self, plan_id: str) -> TradePlanV2 | None:
        return self._get(
            "stt_trade_plans",
            "plan_id",
            plan_id,
            TradePlanV2,
            {"evidence_refs": "evidence_refs_json"},
        )

    def get_plan_v3(self, plan_id: str) -> TradePlanV3 | None:
        return self._get(
            "stt_trade_plans",
            "plan_id",
            plan_id,
            TradePlanV3,
            {"evidence_refs": "evidence_refs_json"},
        )

    def append_plan_event(self, event: PlanEventV1) -> None:
        status = "WAIT_ENTRY" if event.new_state == "PREPARED" else "NO_TRADE"
        with write_connection(self._connection) as connection:
            self._insert_ignore(
                connection,
                "stt_buy_point_plan_events",
                self._event_values(event),
            )
            connection.execute(
                text(
                    "UPDATE stt_trade_plans SET plan_state = :new_state, "
                    "status = :status, as_of = :as_of "
                    "WHERE plan_id = :plan_id AND structure_id = :structure_id"
                ),
                {
                    "new_state": event.new_state,
                    "status": status,
                    "as_of": utc_naive(event.observed_at),
                    "plan_id": event.plan_id,
                    "structure_id": event.structure_id,
                },
            )

    def forward_gate_summary(self, rule_version: str) -> ForwardGateSummary:
        statement = text(
            "SELECT COUNT(DISTINCT analysis_date) AS distinct_dates, "
            "COALESCE(SUM(resolved_count), 0) AS resolved_plans, "
            "COALESCE(SUM(JSON_LENGTH(integrity_violations_json)), 0) "
            "AS integrity_violations "
            "FROM stt_buy_point_forward_runs WHERE rule_version = :rule_version "
            "AND data_status = 'VALID'"
        )
        with read_connection(self._connection) as connection:
            row = connection.execute(
                statement, {"rule_version": rule_version}
            ).mappings().first()
        distinct_dates = int(row["distinct_dates"] if row else 0)
        resolved_plans = int(row["resolved_plans"] if row else 0)
        integrity_violations = int(row["integrity_violations"] if row else 0)
        return ForwardGateSummary(
            distinct_dates=distinct_dates,
            resolved_plans=resolved_plans,
            integrity_violations=integrity_violations,
            eligible=(
                distinct_dates >= 20
                and resolved_plans >= 20
                and integrity_violations == 0
            ),
        )

    def load_buy_point_structure_ids(self, rule_version: str) -> frozenset[str]:
        statement = text(
            "SELECT structure_id FROM stt_trade_plans "
            "WHERE schema_version = '1.3' AND rule_version = :rule_version "
            "AND structure_id IS NOT NULL"
        )
        with read_connection(self._connection) as connection:
            rows = connection.execute(
                statement, {"rule_version": rule_version}
            ).mappings()
            return frozenset(str(row["structure_id"]) for row in rows)

    def load_prepared_buy_point_plans(self, rule_version: str) -> tuple[TradePlanV3, ...]:
        statement = text(
            "SELECT * FROM stt_trade_plans WHERE schema_version = '1.3' "
            "AND rule_version = :rule_version AND plan_state = 'PREPARED' "
            "AND data_status = 'VALID' ORDER BY analysis_date, code"
        )
        with read_connection(self._connection) as connection:
            rows = list(
                connection.execute(statement, {"rule_version": rule_version}).mappings()
            )
        return tuple(
            restore_contract(
                TradePlanV3, row, {"evidence_refs": "evidence_refs_json"}
            )
            for row in rows
        )

    def get_latest_valid_plan(self, code: str, at: datetime) -> TradePlanV2 | None:
        statement = text(
            "SELECT * FROM stt_trade_plans "
            "WHERE code = :code AND schema_version = '1.2' "
            "AND data_status = 'VALID' AND status = 'WAIT_ENTRY' "
            "AND valid_until > :at "
            "ORDER BY trading_date DESC, as_of DESC LIMIT 1"
        )
        parameters = {"code": validate_code(code), "at": utc_naive(at)}
        with read_connection(self._connection) as connection:
            row = connection.execute(statement, parameters).mappings().first()
        return None if row is None else restore_contract(
            TradePlanV2,
            row,
            {"evidence_refs": "evidence_refs_json"},
        )

    def save_risk_decision(self, decision: RiskDecisionV1) -> None:
        self._save("stt_risk_decisions", decision, {"rejection_reasons": "rejection_reasons_json"})

    def get_risk_decision(self, risk_id: str) -> RiskDecisionV1 | None:
        return self._get("stt_risk_decisions", "risk_id", risk_id, RiskDecisionV1, {"rejection_reasons": "rejection_reasons_json"})

    def freeze_decision(self, snapshot: DecisionSnapshotV1) -> None:
        self._save("stt_decision_snapshots", snapshot, {"evidence_refs": "evidence_refs_json", "frozen_payload": "frozen_payload_json"})

    def get_decision(self, decision_id: str) -> DecisionSnapshotV1 | None:
        return self._get("stt_decision_snapshots", "decision_id", decision_id, DecisionSnapshotV1, {"evidence_refs": "evidence_refs_json", "frozen_payload": "frozen_payload_json"})

    def save_intraday(self, decision: IntradayDecisionV1) -> None:
        self._save("stt_intraday_decisions", decision, {"passed_gates": "passed_gates_json", "failed_gates": "failed_gates_json", "evidence_refs": "evidence_refs_json"})

    def get_intraday(self, intraday_id: str) -> IntradayDecisionV1 | None:
        return self._get("stt_intraday_decisions", "intraday_id", intraday_id, IntradayDecisionV1, {"passed_gates": "passed_gates_json", "failed_gates": "failed_gates_json", "evidence_refs": "evidence_refs_json"})
