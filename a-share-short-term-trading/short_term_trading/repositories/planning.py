"""Persistence for market, planning, risk, and intraday decisions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from ..contracts import (
    CandidateV1,
    DecisionSnapshotV1,
    IntradayDecisionV1,
    MarketStateV1,
    RiskDecisionV1,
    TradePlanV1,
)
from .connection import DatabaseHandle, contract_values, read_connection, restore_contract, write_connection


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

    def save_candidate(self, candidate: CandidateV1) -> None:
        self._save("stt_candidates", candidate, {"rejected_reasons": "rejected_reasons_json", "evidence_refs": "evidence_refs_json"})

    def get_candidate(self, candidate_id: str) -> CandidateV1 | None:
        return self._get("stt_candidates", "candidate_id", candidate_id, CandidateV1, {"rejected_reasons": "rejected_reasons_json", "evidence_refs": "evidence_refs_json"})

    def save_plan(self, plan: TradePlanV1) -> None:
        self._save("stt_trade_plans", plan, {"evidence_refs": "evidence_refs_json"})

    def get_plan(self, plan_id: str) -> TradePlanV1 | None:
        return self._get("stt_trade_plans", "plan_id", plan_id, TradePlanV1, {"evidence_refs": "evidence_refs_json"})

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
