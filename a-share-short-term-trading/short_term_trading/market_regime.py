"""Immutable market-regime views used by session-aware diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from .gates import MarketStatus


@dataclass(frozen=True)
class MarketStateView:
    status: MarketStatus
    trading_date: date | None
    as_of: datetime
    expires_at: datetime
    indexes_above_ma20: int | None
    breadth_pct: float | None
    amount_ratio: float | None
    strong_sector_count: int | None
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()
    emotion_label: str | None = None


class MarketStateProvider(Protocol):
    def get_state(self, context: object) -> MarketStateView: ...


def apply_intraday_downgrade(
    previous_status: MarketStatus,
    intraday_breadth: float,
    strong_sector_count: int,
    data_fresh: bool,
) -> MarketStatus:
    if not data_fresh:
        return "FREEZE"
    if previous_status == "FREEZE":
        return "FREEZE"
    if previous_status == "LIMITED":
        return "LIMITED"
    if intraday_breadth < 40 and strong_sector_count < 2:
        return "LIMITED"
    return "ALLOW"


def freeze_market_state(
    *,
    trading_date: date | None,
    as_of: datetime,
    reason: str,
) -> MarketStateView:
    return MarketStateView(
        status="FREEZE",
        trading_date=trading_date,
        as_of=as_of,
        expires_at=as_of,
        indexes_above_ma20=None,
        breadth_pct=None,
        amount_ratio=None,
        strong_sector_count=None,
        reasons=(reason,),
    )
