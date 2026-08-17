"""Point-in-time hierarchy evidence for five-day ranking V3 research."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from .five_day_return_runtime import FiveDaySignalPlan
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


class V3EvidenceRejected(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class V3CandidateEvidence:
    full_edge: Decimal
    recent_edge: Decimal
    edge: Decimal
    stop_rate: Decimal
    mae_p75: Decimal
    deepest_full_key: V3BucketKey
    deepest_recent_key: V3BucketKey
    stable_negative: bool
    full_trace: tuple[V3BucketStats, ...]
    recent_trace: tuple[V3BucketStats, ...]


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


def _validate_shrinkage_k(shrinkage_k: int) -> None:
    if shrinkage_k not in (30, 60):
        raise ValueError("shrinkage_k must be 30 or 60")


def _weight(samples: int, shrinkage_k: int) -> Decimal:
    return Decimal(samples) / Decimal(samples + shrinkage_k)


def recursive_edge(
    path: Sequence[V3BucketStats],
    *,
    shrinkage_k: int,
) -> Decimal:
    _validate_shrinkage_k(shrinkage_k)
    edge = Decimal("0")
    for stats in path:
        weight = _weight(stats.resolved_samples, shrinkage_k)
        edge = (
            weight * stats.net_expectancy
            + (Decimal("1") - weight) * edge
        )
    return edge


def _candidate_keys(plan: FiveDaySignalPlan) -> tuple[V3BucketKey, ...]:
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


def _resolve_path(
    values: Mapping[V3BucketKey, V3BucketStats],
    keys: Sequence[V3BucketKey],
) -> tuple[V3BucketStats, ...]:
    path: list[V3BucketStats] = []
    for key in keys:
        stats = values.get(key)
        if stats is None or stats.resolved_samples <= 0:
            break
        path.append(stats)
    return tuple(path)


def _recursive_metric(
    path: Sequence[V3BucketStats],
    field: str,
    *,
    shrinkage_k: int,
) -> Decimal:
    if not path:
        return Decimal("0")
    value = getattr(path[0], field)
    for stats in path[1:]:
        weight = _weight(stats.resolved_samples, shrinkage_k)
        value = (
            weight * getattr(stats, field)
            + (Decimal("1") - weight) * value
        )
    return value


def _blend_windows(
    full_value: Decimal,
    recent_value: Decimal,
    *,
    full_samples: int,
    recent_samples: int,
    shrinkage_k: int,
) -> Decimal:
    if recent_samples == 0 or full_value == recent_value:
        return full_value
    full_reliability = _weight(full_samples, shrinkage_k)
    recent_reliability = _weight(recent_samples, shrinkage_k)
    reliability = full_reliability + recent_reliability
    if reliability == 0:
        return Decimal("0")
    return (
        full_reliability * full_value
        + recent_reliability * recent_value
    ) / reliability


def _pair_has_samples(
    full_path: Sequence[V3BucketStats],
    recent_path: Sequence[V3BucketStats],
    child_index: int,
) -> bool:
    levels = (child_index - 1, child_index)
    return all(
        full_path[index].resolved_samples >= 60
        and recent_path[index].resolved_samples >= 30
        for index in levels
    )


def _pair_is_negative(
    full_path: Sequence[V3BucketStats],
    recent_path: Sequence[V3BucketStats],
    child_index: int,
    *,
    shrinkage_k: int,
) -> bool:
    levels = (child_index - 1, child_index)
    full_edges = tuple(
        recursive_edge(full_path[: index + 1], shrinkage_k=shrinkage_k)
        for index in levels
    )
    recent_edges = tuple(
        recursive_edge(recent_path[: index + 1], shrinkage_k=shrinkage_k)
        for index in levels
    )
    return all(value <= 0 for value in full_edges + recent_edges) and all(
        full_path[index].profit_factor is not None
        and full_path[index].profit_factor <= Decimal("1")
        and recent_path[index].profit_factor is not None
        and recent_path[index].profit_factor <= Decimal("1")
        and full_path[index].profitable_interval[1] < Decimal("0.50")
        for index in levels
    )


def v3_stable_negative(
    full_path: Sequence[V3BucketStats],
    recent_path: Sequence[V3BucketStats],
    *,
    shrinkage_k: int,
) -> bool:
    _validate_shrinkage_k(shrinkage_k)
    maximum_child = min(len(full_path), len(recent_path)) - 1
    for child_index in range(maximum_child, 0, -1):
        if _pair_has_samples(full_path, recent_path, child_index):
            return _pair_is_negative(
                full_path,
                recent_path,
                child_index,
                shrinkage_k=shrinkage_k,
            )
    return False


def resolve_v3_candidate_evidence(
    plan: FiveDaySignalPlan,
    windows: V3EvidenceWindows,
    *,
    shrinkage_k: int,
) -> V3CandidateEvidence:
    _validate_shrinkage_k(shrinkage_k)
    if not windows.full_dates or not windows.recent_dates:
        raise ValueError("evidence windows must include trading dates")
    signal_date = plan.candidate.signal_date
    if (
        windows.full_dates[-1] >= signal_date
        or windows.recent_dates[-1] >= signal_date
    ):
        raise V3EvidenceRejected("CALIBRATION_NOT_POINT_IN_TIME")

    keys = _candidate_keys(plan)
    full_path = _resolve_path(windows.full, keys)
    recent_path = _resolve_path(windows.recent, keys)
    if not full_path or full_path[0].resolved_samples < 60:
        raise V3EvidenceRejected("PROFILE_HISTORY_TOO_LOW")

    full_edge = recursive_edge(full_path, shrinkage_k=shrinkage_k)
    recent_edge = recursive_edge(recent_path, shrinkage_k=shrinkage_k)
    full_samples = full_path[0].resolved_samples
    recent_samples = recent_path[0].resolved_samples if recent_path else 0
    edge = _blend_windows(
        full_edge,
        recent_edge,
        full_samples=full_samples,
        recent_samples=recent_samples,
        shrinkage_k=shrinkage_k,
    )
    stop_rate = _blend_windows(
        _recursive_metric(
            full_path,
            "stop_rate",
            shrinkage_k=shrinkage_k,
        ),
        _recursive_metric(
            recent_path,
            "stop_rate",
            shrinkage_k=shrinkage_k,
        ),
        full_samples=full_samples,
        recent_samples=recent_samples,
        shrinkage_k=shrinkage_k,
    )
    mae_p75 = _blend_windows(
        _recursive_metric(
            full_path,
            "mae_p75",
            shrinkage_k=shrinkage_k,
        ),
        _recursive_metric(
            recent_path,
            "mae_p75",
            shrinkage_k=shrinkage_k,
        ),
        full_samples=full_samples,
        recent_samples=recent_samples,
        shrinkage_k=shrinkage_k,
    )
    return V3CandidateEvidence(
        full_edge=full_edge,
        recent_edge=recent_edge,
        edge=edge,
        stop_rate=stop_rate,
        mae_p75=mae_p75,
        deepest_full_key=full_path[-1].key,
        deepest_recent_key=(
            recent_path[-1].key if recent_path else keys[0]
        ),
        stable_negative=v3_stable_negative(
            full_path,
            recent_path,
            shrinkage_k=shrinkage_k,
        ),
        full_trace=full_path,
        recent_trace=recent_path,
    )
