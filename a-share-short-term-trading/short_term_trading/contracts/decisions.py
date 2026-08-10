"""Plan, risk, frozen-decision, and intraday contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .base import ContractModel, MarketStatus, ReleaseMode, SignalStatus, validate_code


def _uuid_string(value: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("identifier must be a UUID string") from exc


def _uuid_list(values: list[str]) -> list[str]:
    return [_uuid_string(value) for value in values]


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


class TradePlanV1(ContractModel):
    plan_id: str
    candidate_id: str
    trading_date: date
    code: str
    status: SignalStatus
    trigger_price: Decimal = Field(gt=0)
    entry_ceiling: Decimal = Field(gt=0)
    pullback_low: Decimal = Field(gt=0)
    pullback_high: Decimal = Field(gt=0)
    invalidation_price: Decimal = Field(gt=0)
    first_reduce_price: Decimal = Field(gt=0)
    risk_distance: Decimal = Field(gt=0)
    valid_until: AwareDatetime
    rule_version: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)

    _validate_plan_id = field_validator("plan_id")(_uuid_string)
    _validate_candidate_id = field_validator("candidate_id")(_uuid_string)
    _validate_code = field_validator("code")(validate_code)
    _validate_evidence_refs = field_validator("evidence_refs")(_uuid_list)
    _normalize_valid_until = field_validator("valid_until")(_utc)

    @model_validator(mode="after")
    def validate_end_of_day_state_and_prices(self) -> "TradePlanV1":
        if self.status not in {SignalStatus.NO_TRADE, SignalStatus.WAIT_ENTRY}:
            raise ValueError("end-of-day plan status must be NO_TRADE or WAIT_ENTRY")
        if self.pullback_low > self.pullback_high:
            raise ValueError("pullback_low must not exceed pullback_high")
        if self.valid_until <= self.as_of:
            raise ValueError("valid_until must be later than as_of")
        return self


class RiskDecisionV1(ContractModel):
    risk_id: str
    plan_id: str
    code: str
    market_status: MarketStatus
    account_exposure: Decimal = Field(ge=0)
    theme_exposure: Decimal = Field(ge=0)
    open_trade_slots: int = Field(ge=0)
    max_shares: int = Field(ge=0)
    allowed: bool
    rejection_reasons: list[str]

    _validate_risk_id = field_validator("risk_id")(_uuid_string)
    _validate_plan_id = field_validator("plan_id")(_uuid_string)
    _validate_code = field_validator("code")(validate_code)

    @model_validator(mode="after")
    def require_rejection_reason(self) -> "RiskDecisionV1":
        if not self.allowed and not self.rejection_reasons:
            raise ValueError("a rejected risk decision requires a reason")
        if self.allowed and self.market_status is MarketStatus.FREEZE:
            raise ValueError("FREEZE market cannot allow a new trade")
        return self


class DecisionSnapshotV1(ContractModel):
    decision_id: str
    trading_date: date
    code: str
    candidate_id: str
    plan_id: str
    risk_id: str
    evidence_refs: list[str] = Field(min_length=1)
    frozen_payload: dict[str, Any]

    _validate_decision_id = field_validator("decision_id")(_uuid_string)
    _validate_candidate_id = field_validator("candidate_id")(_uuid_string)
    _validate_plan_id = field_validator("plan_id")(_uuid_string)
    _validate_risk_id = field_validator("risk_id")(_uuid_string)
    _validate_code = field_validator("code")(validate_code)
    _validate_evidence_refs = field_validator("evidence_refs")(_uuid_list)


class IntradayDecisionV1(ContractModel):
    intraday_id: str
    decision_id: str
    code: str
    status: SignalStatus
    release_mode: ReleaseMode
    actionable: bool
    passed_gates: list[str]
    failed_gates: list[str]
    evidence_refs: list[str] = Field(min_length=1)
    max_shares: int = Field(ge=0)
    valid_until: AwareDatetime
    reduce_shares: int | None = Field(default=None, gt=0)
    reduce_ratio: Decimal | None = Field(default=None, gt=0, le=1)

    _validate_intraday_id = field_validator("intraday_id")(_uuid_string)
    _validate_decision_id = field_validator("decision_id")(_uuid_string)
    _validate_code = field_validator("code")(validate_code)
    _validate_evidence_refs = field_validator("evidence_refs")(_uuid_list)
    _normalize_valid_until = field_validator("valid_until")(_utc)

    @model_validator(mode="after")
    def validate_state(self) -> "IntradayDecisionV1":
        if self.release_mode is ReleaseMode.SHADOW and self.actionable:
            raise ValueError("shadow decisions cannot be actionable")
        if self.actionable and not (
            self.release_mode is ReleaseMode.LIVE and self.status is SignalStatus.BUY_ALLOWED
        ):
            raise ValueError("only a live BUY_ALLOWED decision can be actionable")
        if self.status is SignalStatus.REDUCE and self.reduce_shares is None and self.reduce_ratio is None:
            raise ValueError("REDUCE requires reduce_shares or reduce_ratio")
        if self.status is not SignalStatus.REDUCE and (
            self.reduce_shares is not None or self.reduce_ratio is not None
        ):
            raise ValueError("reduction size is only valid for REDUCE")
        if self.valid_until <= self.as_of:
            raise ValueError("valid_until must be later than as_of")
        return self
