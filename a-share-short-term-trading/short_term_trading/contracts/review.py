"""Execution journal and review contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .base import ContractModel, validate_code


def _uuid_string(value: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("identifier must be a UUID string") from exc


class TradeJournalV1(ContractModel):
    journal_id: str
    decision_id: str
    code: str
    action: Literal["BUY", "SELL", "REDUCE", "EXIT"]
    user_confirmed: Literal[True]
    quantity: int = Field(gt=0)
    execution_price: Decimal = Field(gt=0)
    fees: Decimal = Field(ge=0)
    reason: str = Field(min_length=1)
    broker_evidence_ref: str = Field(min_length=1)

    _validate_journal_id = field_validator("journal_id")(_uuid_string)
    _validate_decision_id = field_validator("decision_id")(_uuid_string)
    _validate_code = field_validator("code")(validate_code)


class OutcomeObservationV1(ContractModel):
    observation_id: str
    decision_id: str
    code: str
    horizon: Literal["T1", "T3", "T5"]
    observed_at: AwareDatetime
    close_price: Decimal = Field(gt=0)
    triggered: bool
    max_favorable_excursion_pct: Decimal
    max_adverse_excursion_pct: Decimal

    _validate_observation_id = field_validator("observation_id")(_uuid_string)
    _validate_decision_id = field_validator("decision_id")(_uuid_string)
    _validate_code = field_validator("code")(validate_code)

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class PlanEvaluationV1(ContractModel):
    evaluation_id: str
    rule_version: str = Field(min_length=1)
    window_start: date
    window_end: date
    horizon: Literal["T1", "T3", "T5"]
    sample_size: int = Field(gt=0)
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    execution_deviation_pct: Decimal
    decision_refs: tuple[str, ...] = Field(min_length=1)
    review_tags: tuple[str, ...]

    _validate_evaluation_id = field_validator("evaluation_id")(_uuid_string)
    _validate_decision_refs = field_validator("decision_refs")(
        lambda values: tuple(_uuid_string(value) for value in values)
    )

    @model_validator(mode="after")
    def validate_window(self) -> "PlanEvaluationV1":
        if self.window_end < self.window_start:
            raise ValueError("window_end must not be earlier than window_start")
        return self
