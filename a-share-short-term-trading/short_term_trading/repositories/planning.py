"""Persistence for market, planning, risk, and intraday decisions."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from ..contracts import (
    CandidateV1,
    CandidateV2,
    DecisionSnapshotV1,
    IntradayDecisionV1,
    MarketStateV1,
    RiskDecisionV1,
    TradePlanV1,
    TradePlanV2,
    validate_code,
)
from .connection import DatabaseHandle, contract_values, read_connection, restore_contract, utc_naive, write_connection


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
