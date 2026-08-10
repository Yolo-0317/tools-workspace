"""Shared strict contracts for the short-term trading system."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class DataStatus(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    STALE = "STALE"
    INVALID = "INVALID"
    CONFLICT = "CONFLICT"


class SignalStatus(str, Enum):
    NO_TRADE = "NO_TRADE"
    WAIT_ENTRY = "WAIT_ENTRY"
    BUY_ALLOWED = "BUY_ALLOWED"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"


class MarketStatus(str, Enum):
    ALLOW = "ALLOW"
    LIMITED = "LIMITED"
    FREEZE = "FREEZE"


class ReleaseMode(str, Enum):
    SHADOW = "SHADOW"
    LIVE = "LIVE"


class EvidenceKind(str, Enum):
    DAILY_BAR = "DAILY_BAR"
    STOCK_BASIC = "STOCK_BASIC"
    QUOTE = "QUOTE"
    FUND_FLOW = "FUND_FLOW"
    SECTOR = "SECTOR"
    CHIP = "CHIP"
    ORDER_BOOK = "ORDER_BOOK"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    BROKER_ACCOUNT = "BROKER_ACCOUNT"
    BROKER_POSITION = "BROKER_POSITION"


class ContractModel(BaseModel):
    """Base for immutable v1.1 payloads persisted or rendered by the system."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_encoders={Decimal: lambda value: format(value, "f")},
    )

    schema_version: Literal["1.1"] = "1.1"
    as_of: datetime
    source: str
    data_status: DataStatus

    @field_validator("as_of")
    @classmethod
    def require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(timezone.utc)


_CODE_PATTERN = re.compile(r"^(?P<code>\d{1,6})(?:\.(?:SH|SZ|BJ))?$", re.IGNORECASE)


def validate_code(value: str) -> str:
    """Normalize an A-share security code to exactly six digits."""

    match = _CODE_PATTERN.fullmatch(str(value).strip())
    if match is None:
        raise ValueError("code must be 1-6 digits with an optional SH, SZ, or BJ suffix")
    return match.group("code").zfill(6)


def utc_now() -> datetime:
    """Return an aware timestamp in UTC."""

    return datetime.now(timezone.utc)
