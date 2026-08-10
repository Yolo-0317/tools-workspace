"""Market, candidate, and evidence contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, ValidationInfo, field_validator, model_validator

from .base import ContractModel, EvidenceKind, MarketStatus, validate_code


def _uuid_string(value: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("identifier must be a UUID string") from exc


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


class MarketStateV1(ContractModel):
    state_id: str
    trading_date: date
    index_change_pct: Decimal
    breadth_ratio: Decimal = Field(ge=0, le=1)
    turnover_ratio: Decimal = Field(ge=0)
    strong_sector_count: int = Field(ge=0)
    status: MarketStatus
    reasons: list[str]
    evidence_refs: list[str]

    _validate_state_id = field_validator("state_id")(_uuid_string)
    _validate_evidence_refs = field_validator("evidence_refs")(
        lambda values: [_uuid_string(value) for value in values]
    )


class CandidateV1(ContractModel):
    candidate_id: str
    trading_date: date
    code: str
    name: str = Field(min_length=1)
    candidate_type: Literal["BREAKOUT"]
    liquidity_score: Decimal = Field(ge=0, le=1)
    trend_score: Decimal = Field(ge=0, le=1)
    catalyst_score: Decimal = Field(ge=0, le=1)
    sector: str = Field(min_length=1)
    rejected_reasons: list[str]
    evidence_refs: list[str] = Field(min_length=1)

    _validate_candidate_id = field_validator("candidate_id")(_uuid_string)
    _validate_code = field_validator("code")(validate_code)
    _validate_evidence_refs = field_validator("evidence_refs")(
        lambda values: [_uuid_string(value) for value in values]
    )


class EvidenceSnapshotV1(ContractModel):
    evidence_id: str
    kind: EvidenceKind
    code: str | None
    payload: dict[str, Any]
    parser_version: str = Field(min_length=1)
    raw_reference: str = Field(min_length=1)
    expires_at: AwareDatetime
    freshness_seconds: int = Field(ge=0)
    quality_flags: list[str]

    _validate_evidence_id = field_validator("evidence_id")(_uuid_string)

    @field_validator("payload")
    @classmethod
    def normalize_kind_payload_numbers(
        cls, value: dict[str, Any], info: ValidationInfo
    ) -> dict[str, Any]:
        normalized = dict(value)
        if info.data.get("kind") is EvidenceKind.QUOTE and "last_price" in normalized:
            normalized["last_price"] = Decimal(str(normalized["last_price"]))
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        return None if value is None else validate_code(value)

    @field_validator("expires_at")
    @classmethod
    def normalize_expiry(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_kind_payload(self) -> "EvidenceSnapshotV1":
        if self.kind is not EvidenceKind.MARKET and self.code is None:
            raise ValueError("code is required for non-market evidence")
        if self.kind is EvidenceKind.MARKET and self.code is not None:
            raise ValueError("market evidence must not contain a code")

        required_key = {
            EvidenceKind.MARKET: "status",
            EvidenceKind.QUOTE: "last_price",
        }.get(self.kind)
        if required_key is not None and required_key not in self.payload:
            raise ValueError(f"{self.kind.value} payload requires {required_key}")
        if self.expires_at < self.as_of:
            raise ValueError("expires_at must not be earlier than as_of")
        return self
