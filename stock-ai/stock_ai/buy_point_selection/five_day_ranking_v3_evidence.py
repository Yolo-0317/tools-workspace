"""Point-in-time hierarchy evidence for five-day ranking V3 research."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from .five_day_return_validation import (
    FiveDayObservation,
    _average,
    _is_resolved,
    _percentile_75,
    _positive_window_ratio,
    _wilson_interval,
)
from .models import SetupType


@dataclass(frozen=True, order=True)
class V3BucketKey:
    level: str
    profile_id: str
    setup_type: SetupType | None = None
    market_status: str | None = None
    sector_resonating: bool | None = None


@dataclass(frozen=True)
class V3BucketStats:
    key: V3BucketKey
    data_end: date
    total_plans: int
    resolved_samples: int
    net_expectancy: Decimal
    profit_factor: Decimal | None
    profitable_interval: tuple[Decimal, Decimal]
    positive_window_ratio: Decimal
    mae_p75: Decimal
    stop_rate: Decimal


@dataclass(frozen=True)
class V3EvidenceWindows:
    full_dates: tuple[date, ...]
    recent_dates: tuple[date, ...]
    full: Mapping[V3BucketKey, V3BucketStats]
    recent: Mapping[V3BucketKey, V3BucketStats]


def _hierarchy_keys(value: FiveDayObservation) -> tuple[V3BucketKey, ...]:
    plan = value.plan
    profile_id = plan.profile.profile_id
    setup_type = plan.candidate.setup.setup_type
    market_status = plan.candidate.market_status
    sector_resonating = plan.candidate.sector_resonating
    return (
        V3BucketKey(level="PROFILE", profile_id=profile_id),
        V3BucketKey(
            level="SETUP",
            profile_id=profile_id,
            setup_type=setup_type,
        ),
        V3BucketKey(
            level="MARKET",
            profile_id=profile_id,
            setup_type=setup_type,
            market_status=market_status,
        ),
        V3BucketKey(
            level="SECTOR",
            profile_id=profile_id,
            setup_type=setup_type,
            market_status=market_status,
            sector_resonating=sector_resonating,
        ),
    )


def _summarize_bucket(
    key: V3BucketKey,
    values: Sequence[FiveDayObservation],
    *,
    trading_dates: tuple[date, ...],
) -> V3BucketStats:
    data_end = trading_dates[-1]
    resolved = tuple(
        value
        for value in values
        if _is_resolved(value) and value.resolution_date <= data_end
    )
    positive_count = sum(
        value.trade.net_return is not None and value.trade.net_return > 0
        for value in resolved
    )
    gross_profit = sum(
        (
            value.trade.net_pnl
            for value in resolved
            if value.trade.net_pnl > 0
        ),
        Decimal("0"),
    )
    gross_loss = abs(
        sum(
            (
                value.trade.net_pnl
                for value in resolved
                if value.trade.net_pnl < 0
            ),
            Decimal("0"),
        )
    )
    return V3BucketStats(
        key=key,
        data_end=data_end,
        total_plans=len(values),
        resolved_samples=len(resolved),
        net_expectancy=_average(
            tuple(
                value.trade.net_return
                for value in resolved
                if value.trade.net_return is not None
            )
        ),
        profit_factor=(
            gross_profit / gross_loss if gross_loss > 0 else None
        ),
        profitable_interval=_wilson_interval(
            positive_count,
            len(resolved),
        ),
        positive_window_ratio=_positive_window_ratio(
            values,
            trading_dates,
            data_end=data_end,
        ),
        mae_p75=_percentile_75(
            tuple(
                value.trade.mae
                for value in resolved
                if value.trade.mae is not None
            )
        ),
        stop_rate=(
            Decimal(
                sum(value.trade.status == "STOPPED" for value in resolved)
            )
            / Decimal(len(resolved))
            if resolved
            else Decimal("0")
        ),
    )


def _build_window(
    observations: Sequence[FiveDayObservation],
    *,
    trading_dates: tuple[date, ...],
) -> Mapping[V3BucketKey, V3BucketStats]:
    session_set = frozenset(trading_dates)
    grouped: dict[V3BucketKey, list[FiveDayObservation]] = defaultdict(list)
    for value in observations:
        if value.plan.candidate.signal_date not in session_set:
            continue
        for key in _hierarchy_keys(value):
            grouped[key].append(value)
    return {
        key: _summarize_bucket(
            key,
            grouped[key],
            trading_dates=trading_dates,
        )
        for key in sorted(grouped)
    }


def build_v3_evidence_windows(
    observations: Sequence[FiveDayObservation],
    *,
    trading_dates: Sequence[date],
) -> V3EvidenceWindows:
    """Build profile-isolated full and trailing-126-session summaries."""
    sessions = tuple(trading_dates)
    if not sessions:
        raise ValueError("trading_dates must not be empty")
    if any(left >= right for left, right in zip(sessions, sessions[1:])):
        raise ValueError("trading_dates must be unique and increasing")
    recent_dates = sessions[-126:]
    return V3EvidenceWindows(
        full_dates=sessions,
        recent_dates=recent_dates,
        full=_build_window(observations, trading_dates=sessions),
        recent=_build_window(observations, trading_dates=recent_dates),
    )
