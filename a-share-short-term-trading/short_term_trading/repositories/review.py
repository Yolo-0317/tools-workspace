"""Persistence for journals, outcomes, and evaluations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from ..contracts import OutcomeObservationV1, PlanEvaluationV1, TradeJournalV1
from .connection import DatabaseHandle, contract_values, read_connection, restore_contract, write_connection


class ReviewRepository:
    def __init__(self, connection: DatabaseHandle) -> None:
        self._connection = connection

    def _save(self, table: str, model: Any, json_fields: dict[str, str] | None = None) -> None:
        values = contract_values(model, json_fields)
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        with write_connection(self._connection) as connection:
            connection.execute(text(f"INSERT IGNORE INTO {table} ({columns}) VALUES ({parameters})"), values)

    def _get(self, table: str, key: str, value: str, model_type: Any, json_fields: dict[str, str] | None = None) -> Any:
        with read_connection(self._connection) as connection:
            row = connection.execute(
                text(f"SELECT * FROM {table} WHERE {key} = :value"), {"value": value}
            ).mappings().first()
        return None if row is None else restore_contract(model_type, row, json_fields)

    def save_journal(self, entry: TradeJournalV1) -> None:
        self._save("stt_trade_journal", entry)

    def get_journal(self, journal_id: str) -> TradeJournalV1 | None:
        return self._get("stt_trade_journal", "journal_id", journal_id, TradeJournalV1)

    def save_outcome(self, observation: OutcomeObservationV1) -> None:
        self._save("stt_outcome_observations", observation)

    def get_outcome(self, observation_id: str) -> OutcomeObservationV1 | None:
        return self._get("stt_outcome_observations", "observation_id", observation_id, OutcomeObservationV1)

    def save_evaluation(self, evaluation: PlanEvaluationV1) -> None:
        self._save("stt_plan_evaluations", evaluation, {"decision_refs": "decision_refs_json", "review_tags": "review_tags_json"})

    def get_evaluation(self, evaluation_id: str) -> PlanEvaluationV1 | None:
        return self._get("stt_plan_evaluations", "evaluation_id", evaluation_id, PlanEvaluationV1, {"decision_refs": "decision_refs_json", "review_tags": "review_tags_json"})
