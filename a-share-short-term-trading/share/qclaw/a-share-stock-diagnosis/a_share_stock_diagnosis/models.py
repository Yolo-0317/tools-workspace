"""Immutable contracts shared by the portable diagnosis modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class Security:
    code: str
    market: str
    name: str


@dataclass(frozen=True)
class DailyBar:
    trade_date: date
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    change_pct: float
    turnover_rate: float


@dataclass(frozen=True)
class Quote:
    code: str
    name: str
    price: float
    open: float
    high: float
    low: float
    previous_close: float
    change_pct: float
    turnover_rate: float
    as_of: datetime
    source: str = "eastmoney-public"


@dataclass(frozen=True)
class HoldingInput:
    shares: int
    cost_price: float
    available_shares: int | None = None


@dataclass(frozen=True)
class ChipMetrics:
    source_trade_date: date
    cost_90_low: float
    cost_90_high: float
    average_cost: float
    profit_ratio: float
    concentration: float
    input_bar_count: int
    method: str = "eastmoney-cyq-v1"


@dataclass(frozen=True)
class SessionContext:
    session: str
    local_now: datetime
    calendar_confirmed: bool
    diagnosis_trade_date: date | None
    next_trade_date: date | None
    reason: str


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class DiagnosisResult:
    schema_version: str
    symbol: str
    name: str
    session: str
    as_of: datetime
    diagnosis_trade_date: date | None
    data_freshness: str
    quote: dict[str, Any] | None
    latest_bar: dict[str, Any] | None
    indicators: dict[str, float]
    chip_estimate: dict[str, Any] | None
    decision: str
    actionable: bool
    reason: str
    next_action: str
    levels: dict[str, float | None]
    holding: dict[str, Any] | None
    warnings: list[str]
    source_refs: dict[str, str]
    errors: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))

