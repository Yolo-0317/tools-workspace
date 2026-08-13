from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping


class CycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVIEW_DUE = "REVIEW_DUE"
    EXTENDED = "EXTENDED"
    CLOSED = "CLOSED"
    INVALIDATED = "INVALIDATED"


class HardEventKind(str, Enum):
    PRICE_TRIGGER = "PRICE_TRIGGER"
    POSITION_CHANGE = "POSITION_CHANGE"
    TREND_STRUCTURE = "TREND_STRUCTURE"
    COMPANY_EVENT = "COMPANY_EVENT"
    MARKET_SECTOR_REVERSAL = "MARKET_SECTOR_REVERSAL"


@dataclass(frozen=True)
class DecisionCycle:
    cycle_id: int | str
    code: str
    name: str
    started_trade_date: date
    review_trade_date: date
    expiry_trade_date: date
    initial_action: str
    current_action: str
    status: CycleStatus


@dataclass(frozen=True)
class HardEvent:
    kind: HardEventKind
    suggested_action: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    source: str = "advisor"
    observed_at: datetime | None = None


@dataclass(frozen=True)
class CycleTransition:
    status: CycleStatus
    action: str
    event_type: str
    relation: str
    hard_event: HardEvent | None = None
