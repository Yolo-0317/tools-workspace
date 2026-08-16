"""Frozen calibration and validation for five-day return shadow research."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import Decimal
import hashlib
import json
import math
from typing import Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
    FiveDayTrade,
)
from .five_day_return_profiles import SIZING_VERSION
from .five_day_return_runtime import FiveDaySignalPlan
from .models import SetupType


FIVE_DAY_FREEZE_SCHEMA = "five-day-return-freeze-v1"
RESEARCH_IDENTITY = "CASE_ANALYSIS_ONLY|NO-TRADE"
SELECTED_PORTFOLIO_METRIC_VERSION = "selected-portfolio-v2"
WILSON_Z = Decimal("1.959963984540054")
_RESOLVED_STATUSES = frozenset(
    ("STOPPED", "TIME_EXIT_GAIN", "TIME_EXIT_FLAT", "TIME_EXIT_LOSS")
)


@dataclass(frozen=True)
class FiveDayObservation:
    plan: FiveDaySignalPlan
    trade: FiveDayTrade
    resolution_date: date


@dataclass(frozen=True)
class FiveDayCalibration:
    key: str
    profile_id: str
    setup_type: SetupType
    market_status: str | None
    sector_resonating: bool | None
    data_end: date
    total_plans: int
    triggered_resolved: int
    positive_net: int
    profitable_rate: Decimal
    profitable_interval: tuple[Decimal, Decimal]
    net_expectancy: Decimal
    profit_factor: Decimal | None
    stop_rate: Decimal
    mae_p75: Decimal
    positive_window_ratio: Decimal


@dataclass(frozen=True)
class FiveDaySegmentMetrics:
    profile_id: str
    segment: str
    triggered_resolved: int
    net_expectancy: Decimal
    profit_factor: Decimal | None
    profitable_wilson_lower: Decimal
    stop_rate: Decimal
    positive_window_ratio: Decimal
    maximum_drawdown: Decimal
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FiveDayPortfolioMetrics:
    accepted_trades: int
    maximum_drawdown: Decimal
    maximum_stock_trade_share: Decimal
    maximum_stock_profit_share: Decimal
    maximum_sector_trade_share: Decimal
    maximum_sector_profit_share: Decimal
    top5_profit_share: Decimal
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FrozenFiveDayProfile:
    profile_id: str
    rank: int
    train_validation_samples: int
    validation_metrics: FiveDaySegmentMetrics


@dataclass(frozen=True)
class FiveDayFreeze:
    schema: str
    research_identity: str
    profile_matrix_hash: str
    sizing_version: str
    evaluator_version: str
    cost_version: str
    profiles: tuple[FrozenFiveDayProfile, ...]
    calibrations: Mapping[str, FiveDayCalibration]
    empty: bool
    freeze_hash: str


@dataclass(frozen=True)
class FiveDayTestAssessment:
    profile_metrics: tuple[FiveDaySegmentMetrics, ...]
    portfolio_metrics: FiveDayPortfolioMetrics
    eligible_profile_ids: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FiveDayRankedPlan:
    plan: FiveDaySignalPlan
    rank: int
    selected: bool


@dataclass(frozen=True)
class FiveDayRanking:
    plans: tuple[FiveDaySignalPlan, ...]
    rejection_counts: Mapping[str, int]
    ranked: tuple[FiveDayRankedPlan, ...] = ()


@dataclass(frozen=True)
class FiveDaySelection:
    ranking: FiveDayRanking
    selected_observations: tuple[FiveDayObservation, ...]
    admitted: tuple[FiveDayObservation, ...]
    funnel_counts: Mapping[str, int]
    incomplete: bool


@dataclass(frozen=True)
class FiveDaySelectedSegment:
    metric_version: str
    metrics: FiveDaySegmentMetrics
    portfolio: FiveDayPortfolioMetrics
    selection: FiveDaySelection


def _is_resolved(value: FiveDayObservation) -> bool:
    return (
        value.trade.status in _RESOLVED_STATUSES
        and value.trade.net_return is not None
        and value.trade.exit is not None
    )


def _average(values: Sequence[Decimal]) -> Decimal:
    return (
        sum(values, Decimal("0")) / Decimal(len(values))
        if values
        else Decimal("0")
    )


def _wilson_interval(successes: int, total: int) -> tuple[Decimal, Decimal]:
    if total <= 0:
        return Decimal("0"), Decimal("0")
    n = Decimal(total)
    rate = Decimal(successes) / n
    z2 = WILSON_Z * WILSON_Z
    denominator = Decimal("1") + z2 / n
    centre = rate + z2 / (Decimal("2") * n)
    variance = (
        rate * (Decimal("1") - rate) / n
        + z2 / (Decimal("4") * n * n)
    )
    margin = WILSON_Z * Decimal(str(math.sqrt(float(variance))))
    return (
        max(Decimal("0"), (centre - margin) / denominator),
        min(Decimal("1"), (centre + margin) / denominator),
    )


def _percentile_75(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    ordered = tuple(sorted(values))
    index = math.ceil(len(ordered) * 0.75) - 1
    return ordered[max(0, index)]


def _positive_window_ratio(
    observations: Sequence[FiveDayObservation],
    trading_dates: Sequence[date],
    *,
    data_end: date | None = None,
) -> Decimal:
    sessions = tuple(trading_dates)
    if len(sessions) < 63:
        return Decimal("0")
    resolved = tuple(
        value
        for value in observations
        if _is_resolved(value)
        and (data_end is None or value.resolution_date <= data_end)
    )
    positive = 0
    windows = len(sessions) - 62
    for start in range(windows):
        dated = frozenset(sessions[start : start + 63])
        returns = tuple(
            value.trade.net_return
            for value in resolved
            if value.plan.candidate.signal_date in dated
            and value.trade.net_return is not None
        )
        if returns and _average(returns) > 0:
            positive += 1
    return Decimal(positive) / Decimal(windows)


def _calibration_key(
    profile_id: str,
    setup_type: SetupType,
    market_status: str | None,
    sector_resonating: bool | None,
) -> str:
    return "|".join(
        (
            profile_id,
            setup_type.value,
            market_status if market_status is not None else "*",
            str(sector_resonating) if sector_resonating is not None else "*",
        )
    )


def _build_calibration(
    key: str,
    values: Sequence[FiveDayObservation],
    *,
    setup_type: SetupType,
    market_status: str | None,
    sector_resonating: bool | None,
    trading_dates: Sequence[date],
) -> FiveDayCalibration:
    data_end = trading_dates[-1]
    resolved = tuple(
        value
        for value in values
        if _is_resolved(value) and value.resolution_date <= data_end
    )
    positives = tuple(
        value
        for value in resolved
        if value.trade.net_return is not None and value.trade.net_return > 0
    )
    profit_values = tuple(
        value for value in resolved if value.trade.net_pnl > 0
    )
    losses = tuple(value for value in resolved if value.trade.net_pnl < 0)
    gross_profit = sum(
        (value.trade.net_pnl for value in profit_values), Decimal("0")
    )
    gross_loss = abs(
        sum((value.trade.net_pnl for value in losses), Decimal("0"))
    )
    interval = _wilson_interval(len(positives), len(resolved))
    return FiveDayCalibration(
        key=key,
        profile_id=values[0].plan.profile.profile_id,
        setup_type=setup_type,
        market_status=market_status,
        sector_resonating=sector_resonating,
        data_end=data_end,
        total_plans=len(values),
        triggered_resolved=len(resolved),
        positive_net=len(positives),
        profitable_rate=(
            Decimal(len(positives)) / Decimal(len(resolved))
            if resolved
            else Decimal("0")
        ),
        profitable_interval=interval,
        net_expectancy=_average(
            tuple(
                value.trade.net_return
                for value in resolved
                if value.trade.net_return is not None
            )
        ),
        profit_factor=(gross_profit / gross_loss if gross_loss > 0 else None),
        stop_rate=(
            Decimal(sum(value.trade.status == "STOPPED" for value in resolved))
            / Decimal(len(resolved))
            if resolved
            else Decimal("0")
        ),
        mae_p75=_percentile_75(
            tuple(
                value.trade.mae
                for value in resolved
                if value.trade.mae is not None
            )
        ),
        positive_window_ratio=_positive_window_ratio(
            values, trading_dates, data_end=data_end
        ),
    )


def build_five_day_calibrations(
    observations: Sequence[FiveDayObservation],
    *,
    trading_dates: Sequence[date],
) -> Mapping[str, FiveDayCalibration]:
    """Build independent fine, market, and broad calibration buckets."""
    sessions = tuple(trading_dates)
    if not sessions:
        raise ValueError("trading_dates must not be empty")
    grouped: dict[
        tuple[str, SetupType, str | None, bool | None],
        list[FiveDayObservation],
    ] = {}
    for value in observations:
        profile_id = value.plan.profile.profile_id
        setup_type = value.plan.candidate.setup.setup_type
        market_status = value.plan.candidate.market_status
        sector_resonating = value.plan.candidate.sector_resonating
        for group in (
            (profile_id, setup_type, market_status, sector_resonating),
            (profile_id, setup_type, market_status, None),
            (profile_id, setup_type, None, None),
        ):
            grouped.setdefault(group, []).append(value)
    result: dict[str, FiveDayCalibration] = {}
    for group, values in sorted(
        grouped.items(), key=lambda item: _calibration_key(*item[0])
    ):
        profile_id, setup_type, market_status, sector_resonating = group
        key = _calibration_key(*group)
        result[key] = _build_calibration(
            key,
            values,
            setup_type=setup_type,
            market_status=market_status,
            sector_resonating=sector_resonating,
            trading_dates=sessions,
        )
    return result


def resolve_five_day_calibration(
    calibrations: Mapping[str, FiveDayCalibration],
    *,
    profile_id: str,
    setup_type: SetupType,
    market_status: str,
    sector_resonating: bool,
    minimum_samples: int = 30,
) -> FiveDayCalibration | None:
    """Resolve the finest sufficiently sampled bucket without sample merging."""
    for market, sector in (
        (market_status, sector_resonating),
        (market_status, None),
        (None, None),
    ):
        value = calibrations.get(
            _calibration_key(profile_id, setup_type, market, sector)
        )
        if value is not None and value.triggered_resolved >= minimum_samples:
            return value
    return None


def _resistance_rank(plan: FiveDaySignalPlan) -> int:
    if (
        plan.resistance_basis == "LEVEL_AT_OR_ABOVE_2R"
        or plan.resistance_effective_r is not None
        and plan.resistance_effective_r >= Decimal("2")
    ):
        return 2
    if plan.resistance_basis == "NO_RELIABLE_LEVEL":
        return 1
    return 0


def _ranking_key(
    plan: FiveDaySignalPlan,
    calibration: FiveDayCalibration,
) -> tuple[Decimal | int | str, ...]:
    market_allow_rank = int(plan.candidate.market_status == "ALLOW")
    sector_resonance_rank = int(plan.candidate.sector_resonating)
    resistance_rank = _resistance_rank(plan)
    return (
        -calibration.net_expectancy,
        -calibration.profitable_interval[0],
        calibration.mae_p75,
        calibration.stop_rate,
        -market_allow_rank,
        -sector_resonance_rank,
        -resistance_rank,
        -plan.candidate.setup.quality,
        -plan.candidate.average_amount5_qian,
        normalize_code6(plan.candidate.code),
        plan.profile.profile_id,
    )


def _active_structure_key(plan: FiveDaySignalPlan) -> tuple[object, ...]:
    setup = plan.candidate.setup
    return (
        normalize_code6(plan.candidate.code),
        setup.setup_type.value,
        setup.structure_start,
        setup.structure_high,
        setup.structure_low,
    )


def rank_five_day_plans(
    plans: Sequence[FiveDaySignalPlan],
    calibrations: Mapping[str, FiveDayCalibration],
    *,
    active_structure_ids: frozenset[str] = frozenset(),
    daily_limit: int = 3,
) -> FiveDayRanking:
    """Rank plans only from frozen numeric evidence and deterministic ties."""
    if daily_limit < 0:
        raise ValueError("daily_limit must not be negative")
    rejection_counts: Counter[str] = Counter()
    eligible_by_date: dict[
        date, list[tuple[FiveDaySignalPlan, FiveDayCalibration]]
    ] = {}
    for plan in plans:
        if plan.structure_id in active_structure_ids:
            rejection_counts["EXISTING_ACTIVE_STRUCTURE"] += 1
            continue
        calibration = resolve_five_day_calibration(
            calibrations,
            profile_id=plan.profile.profile_id,
            setup_type=plan.candidate.setup.setup_type,
            market_status=plan.candidate.market_status,
            sector_resonating=plan.candidate.sector_resonating,
        )
        if calibration is None:
            rejection_counts["INSUFFICIENT_CALIBRATION"] += 1
            continue
        if calibration.data_end >= plan.candidate.signal_date:
            rejection_counts["CALIBRATION_NOT_POINT_IN_TIME"] += 1
            continue
        eligible_by_date.setdefault(plan.candidate.signal_date, []).append(
            (plan, calibration)
        )

    selected: list[FiveDaySignalPlan] = []
    ranking_trace: list[FiveDayRankedPlan] = []
    for signal_date in sorted(eligible_by_date):
        ranked = sorted(
            eligible_by_date[signal_date],
            key=lambda value: _ranking_key(*value),
        )
        seen_structures: set[tuple[object, ...]] = set()
        unique: list[FiveDaySignalPlan] = []
        for plan, _calibration in ranked:
            identity = _active_structure_key(plan)
            if identity in seen_structures:
                rejection_counts["DUPLICATE_ACTIVE_STRUCTURE"] += 1
                continue
            seen_structures.add(identity)
            unique.append(plan)
        for position, plan in enumerate(unique, start=1):
            is_selected = position <= daily_limit
            ranking_trace.append(
                FiveDayRankedPlan(
                    plan=plan,
                    rank=position,
                    selected=is_selected,
                )
            )
            if is_selected:
                selected.append(plan)
        overflow = max(0, len(unique) - daily_limit)
        if overflow:
            rejection_counts["DAILY_CANDIDATE_LIMIT"] += overflow
    return FiveDayRanking(
        plans=tuple(selected),
        rejection_counts=dict(sorted(rejection_counts.items())),
        ranked=tuple(ranking_trace),
    )


def assess_five_day_segment(
    *,
    profile_id: str,
    segment: str,
    triggered_resolved: int,
    net_expectancy: Decimal,
    profit_factor: Decimal | None,
    profitable_wilson_lower: Decimal,
    stop_rate: Decimal,
    positive_window_ratio: Decimal,
    maximum_drawdown: Decimal,
    required_samples: int,
    cumulative_samples: int | None = None,
    required_cumulative_samples: int | None = None,
) -> FiveDaySegmentMetrics:
    """Apply the frozen profile thresholds with literal boundary semantics."""
    reasons: list[str] = []
    if triggered_resolved < required_samples:
        reasons.append("SEGMENT_SAMPLES_TOO_LOW")
    if (
        required_cumulative_samples is not None
        and (cumulative_samples or 0) < required_cumulative_samples
    ):
        reasons.append(
            "TRAIN_VALIDATION_SAMPLES_TOO_LOW"
            if segment == "validation"
            else "TOTAL_SAMPLES_TOO_LOW"
        )
    if net_expectancy <= 0:
        reasons.append("NON_POSITIVE_EXPECTANCY")
    if profit_factor is None or profit_factor <= Decimal("1.10"):
        reasons.append("PROFIT_FACTOR_TOO_LOW")
    if profitable_wilson_lower < Decimal("0.45"):
        reasons.append("WILSON_LOWER_TOO_LOW")
    if stop_rate > Decimal("0.40"):
        reasons.append("STOP_RATE_TOO_HIGH")
    if positive_window_ratio < Decimal("0.60"):
        reasons.append("POSITIVE_WINDOW_RATIO_TOO_LOW")
    if maximum_drawdown > Decimal("0.10"):
        reasons.append("MAXIMUM_DRAWDOWN_TOO_HIGH")
    return FiveDaySegmentMetrics(
        profile_id=profile_id,
        segment=segment,
        triggered_resolved=triggered_resolved,
        net_expectancy=net_expectancy,
        profit_factor=profit_factor,
        profitable_wilson_lower=profitable_wilson_lower,
        stop_rate=stop_rate,
        positive_window_ratio=positive_window_ratio,
        maximum_drawdown=maximum_drawdown,
        qualifies=not reasons,
        reasons=tuple(reasons),
    )


def assess_five_day_portfolio(
    *,
    accepted_trades: int,
    maximum_drawdown: Decimal,
    maximum_stock_trade_share: Decimal,
    maximum_stock_profit_share: Decimal,
    maximum_sector_trade_share: Decimal,
    maximum_sector_profit_share: Decimal,
    top5_profit_share: Decimal,
    gross_profit_available: bool = True,
) -> FiveDayPortfolioMetrics:
    """Apply combined Top-3 portfolio and concentration thresholds."""
    reasons: list[str] = []
    if accepted_trades <= 0:
        reasons.append("NO_ACCEPTED_TRADES")
    if not gross_profit_available:
        reasons.append("GROSS_PROFIT_UNAVAILABLE")
    if maximum_drawdown > Decimal("0.10"):
        reasons.append("MAXIMUM_DRAWDOWN_TOO_HIGH")
    if maximum_stock_trade_share > Decimal("0.10"):
        reasons.append("STOCK_TRADE_CONCENTRATION_TOO_HIGH")
    if maximum_stock_profit_share > Decimal("0.15"):
        reasons.append("STOCK_PROFIT_CONCENTRATION_TOO_HIGH")
    if maximum_sector_trade_share > Decimal("0.35"):
        reasons.append("SECTOR_TRADE_CONCENTRATION_TOO_HIGH")
    if maximum_sector_profit_share > Decimal("0.40"):
        reasons.append("SECTOR_PROFIT_CONCENTRATION_TOO_HIGH")
    if top5_profit_share > Decimal("0.35"):
        reasons.append("TOP5_PROFIT_CONCENTRATION_TOO_HIGH")
    return FiveDayPortfolioMetrics(
        accepted_trades=accepted_trades,
        maximum_drawdown=maximum_drawdown,
        maximum_stock_trade_share=maximum_stock_trade_share,
        maximum_stock_profit_share=maximum_stock_profit_share,
        maximum_sector_trade_share=maximum_sector_trade_share,
        maximum_sector_profit_share=maximum_sector_profit_share,
        top5_profit_share=top5_profit_share,
        qualifies=not reasons,
        reasons=tuple(reasons),
    )


def _observation_key(value: FiveDayObservation) -> tuple[date, str, str, str]:
    return (
        value.plan.candidate.signal_date,
        normalize_code6(value.plan.candidate.code),
        value.plan.structure_id,
        value.plan.profile.profile_id,
    )


def _plan_key(value: FiveDaySignalPlan) -> tuple[date, str, str, str]:
    return (
        value.candidate.signal_date,
        normalize_code6(value.candidate.code),
        value.structure_id,
        value.profile.profile_id,
    )


def select_five_day_portfolio(
    plans: Sequence[FiveDaySignalPlan],
    observations: Sequence[FiveDayObservation],
    calibrations: Mapping[str, FiveDayCalibration],
    *,
    active_structure_ids: frozenset[str] = frozenset(),
    daily_limit: int = 3,
    capacity: int = 3,
) -> FiveDaySelection:
    """Select and admit plans once while preserving every funnel outcome."""
    if capacity < 0:
        raise ValueError("capacity must not be negative")
    ranking = rank_five_day_plans(
        plans,
        calibrations,
        active_structure_ids=active_structure_ids,
        daily_limit=daily_limit,
    )
    by_plan = {_observation_key(value): value for value in observations}
    counts: Counter[str] = Counter(ranking.rejection_counts)
    selected: list[FiveDayObservation] = []
    admitted: list[FiveDayObservation] = []
    incomplete = False
    for plan in ranking.plans:
        value = by_plan.get(_plan_key(plan))
        if value is None:
            counts["MISSING_OBSERVATION"] += 1
            incomplete = True
            continue
        selected.append(value)
        if not _is_resolved(value):
            counts[value.trade.status] += 1
            incomplete = incomplete or value.trade.status == "PENDING"
            continue
        if value.trade.entry_date is None or value.trade.exit is None:
            counts["INCOMPLETE_RESOLVED_TRADE"] += 1
            incomplete = True
            continue
        entry_date = value.trade.entry_date
        active = sum(
            existing.trade.entry_date is not None
            and existing.trade.entry_date <= entry_date
            and existing.trade.exit is not None
            and existing.trade.exit.actual_exit_date >= entry_date
            for existing in admitted
        )
        if active >= capacity:
            counts["PORTFOLIO_CAPACITY"] += 1
            continue
        admitted.append(value)
    counts["SELECTED_PLANS"] = len(ranking.plans)
    counts["ADMITTED_TRADES"] = len(admitted)
    return FiveDaySelection(
        ranking=ranking,
        selected_observations=tuple(selected),
        admitted=tuple(admitted),
        funnel_counts=dict(sorted(counts.items())),
        incomplete=incomplete,
    )


def _maximum_drawdown(
    observations: Sequence[FiveDayObservation],
    *,
    initial_equity: Decimal = Decimal("30000"),
) -> Decimal:
    equity = initial_equity
    peak = initial_equity
    maximum = Decimal("0")
    for value in sorted(
        observations,
        key=lambda item: (
            item.trade.exit.actual_exit_date if item.trade.exit else date.max,
            normalize_code6(item.trade.code),
            item.trade.profile_id,
        ),
    ):
        equity += value.trade.net_pnl
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, (peak - equity) / peak)
    return maximum


def _largest_share(
    values: Mapping[str, Decimal], denominator: Decimal
) -> Decimal:
    if denominator <= 0 or not values:
        return Decimal("0")
    return max(values.values()) / denominator


def _portfolio_metrics_from_accepted(
    accepted: Sequence[FiveDayObservation],
) -> FiveDayPortfolioMetrics:
    trade_count = len(accepted)
    stock_trades: Counter[str] = Counter(
        normalize_code6(value.trade.code) for value in accepted
    )
    sector_trades: Counter[str] = Counter(
        value.plan.candidate.sector_code for value in accepted
    )
    stock_profit: dict[str, Decimal] = {}
    sector_profit: dict[str, Decimal] = {}
    profits: list[Decimal] = []
    for value in accepted:
        if value.trade.net_pnl <= 0:
            continue
        code = normalize_code6(value.trade.code)
        sector = value.plan.candidate.sector_code
        stock_profit[code] = stock_profit.get(code, Decimal("0")) + value.trade.net_pnl
        sector_profit[sector] = (
            sector_profit.get(sector, Decimal("0")) + value.trade.net_pnl
        )
        profits.append(value.trade.net_pnl)
    gross_profit = sum(profits, Decimal("0"))
    denominator = Decimal(trade_count) if trade_count else Decimal("0")
    return assess_five_day_portfolio(
        accepted_trades=trade_count,
        maximum_drawdown=_maximum_drawdown(accepted),
        maximum_stock_trade_share=(
            Decimal(max(stock_trades.values())) / denominator
            if stock_trades and denominator > 0
            else Decimal("0")
        ),
        maximum_stock_profit_share=_largest_share(stock_profit, gross_profit),
        maximum_sector_trade_share=(
            Decimal(max(sector_trades.values())) / denominator
            if sector_trades and denominator > 0
            else Decimal("0")
        ),
        maximum_sector_profit_share=_largest_share(sector_profit, gross_profit),
        top5_profit_share=(
            sum(sorted(profits, reverse=True)[:5], Decimal("0")) / gross_profit
            if gross_profit > 0
            else Decimal("0")
        ),
        gross_profit_available=gross_profit > 0,
    )


def build_five_day_portfolio_metrics(
    plans: Sequence[FiveDaySignalPlan],
    observations: Sequence[FiveDayObservation],
    calibrations: Mapping[str, FiveDayCalibration],
) -> FiveDayPortfolioMetrics:
    """Rank plans, enforce three active research positions, and score results."""
    selection = select_five_day_portfolio(plans, observations, calibrations)
    return _portfolio_metrics_from_accepted(selection.admitted)


def evaluate_selected_five_day_segment(
    *,
    profile_id: str,
    segment: str,
    observations: Sequence[FiveDayObservation],
    trading_dates: Sequence[date],
    ranking_calibrations: Mapping[str, FiveDayCalibration],
    daily_limit: int,
    capacity: int,
    cumulative_samples: int,
    required_samples: int,
    required_cumulative_samples: int,
) -> FiveDaySelectedSegment:
    """Evaluate one profile from only its capacity-admitted completed trades."""
    profile_values = tuple(
        value
        for value in observations
        if value.plan.profile.profile_id == profile_id
    )
    sessions = tuple(trading_dates)
    data_end = sessions[-1]
    cutoff = tuple(
        value
        for value in profile_values
        if not _is_resolved(value) or value.resolution_date <= data_end
    )
    selection = select_five_day_portfolio(
        tuple(value.plan for value in cutoff),
        cutoff,
        ranking_calibrations,
        daily_limit=daily_limit,
        capacity=capacity,
    )
    admitted = selection.admitted
    positive_returns = tuple(
        value
        for value in admitted
        if value.trade.net_return is not None and value.trade.net_return > 0
    )
    gross_profit = sum(
        (value.trade.net_pnl for value in admitted if value.trade.net_pnl > 0),
        Decimal("0"),
    )
    gross_loss = abs(
        sum(
            (
                value.trade.net_pnl
                for value in admitted
                if value.trade.net_pnl < 0
            ),
            Decimal("0"),
        )
    )
    portfolio = _portfolio_metrics_from_accepted(admitted)
    wilson = _wilson_interval(len(positive_returns), len(admitted))
    metrics = assess_five_day_segment(
        profile_id=profile_id,
        segment=segment,
        triggered_resolved=len(admitted),
        net_expectancy=_average(
            tuple(
                value.trade.net_return
                for value in admitted
                if value.trade.net_return is not None
            )
        ),
        profit_factor=(gross_profit / gross_loss if gross_loss > 0 else None),
        profitable_wilson_lower=wilson[0],
        stop_rate=(
            Decimal(sum(value.trade.status == "STOPPED" for value in admitted))
            / Decimal(len(admitted))
            if admitted
            else Decimal("0")
        ),
        positive_window_ratio=_positive_window_ratio(
            admitted,
            sessions,
            data_end=data_end,
        ),
        maximum_drawdown=portfolio.maximum_drawdown,
        required_samples=required_samples,
        cumulative_samples=cumulative_samples,
        required_cumulative_samples=required_cumulative_samples,
    )
    if selection.incomplete:
        metrics = replace(
            metrics,
            qualifies=False,
            reasons=(*metrics.reasons, "SELECTION_INCOMPLETE"),
        )
    return FiveDaySelectedSegment(
        metric_version=SELECTED_PORTFOLIO_METRIC_VERSION,
        metrics=metrics,
        portfolio=portfolio,
        selection=selection,
    )


def _segment_metrics_from_observations(
    *,
    profile_id: str,
    segment: str,
    observations: Sequence[FiveDayObservation],
    trading_dates: Sequence[date],
    ranking_calibrations: Mapping[str, FiveDayCalibration],
    cumulative_samples: int,
    required_cumulative_samples: int,
) -> FiveDaySegmentMetrics:
    profile_values = tuple(
        value
        for value in observations
        if value.plan.profile.profile_id == profile_id
    )
    data_end = trading_dates[-1]
    cutoff_values = tuple(
        value
        for value in profile_values
        if not _is_resolved(value) or value.resolution_date <= data_end
    )
    resolved = tuple(
        value
        for value in profile_values
        if _is_resolved(value) and value.resolution_date <= data_end
    )
    positives = tuple(
        value
        for value in resolved
        if value.trade.net_return is not None and value.trade.net_return > 0
    )
    profit_values = tuple(
        value for value in resolved if value.trade.net_pnl > 0
    )
    gross_profit = sum(
        (value.trade.net_pnl for value in profit_values), Decimal("0")
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
    profile_portfolio = build_five_day_portfolio_metrics(
        tuple(value.plan for value in profile_values),
        cutoff_values,
        ranking_calibrations,
    )
    wilson = _wilson_interval(len(positives), len(resolved))
    return assess_five_day_segment(
        profile_id=profile_id,
        segment=segment,
        triggered_resolved=len(resolved),
        net_expectancy=_average(
            tuple(
                value.trade.net_return
                for value in resolved
                if value.trade.net_return is not None
            )
        ),
        profit_factor=(gross_profit / gross_loss if gross_loss > 0 else None),
        profitable_wilson_lower=wilson[0],
        stop_rate=(
            Decimal(sum(value.trade.status == "STOPPED" for value in resolved))
            / Decimal(len(resolved))
            if resolved
            else Decimal("0")
        ),
        positive_window_ratio=_positive_window_ratio(
            profile_values, trading_dates, data_end=data_end
        ),
        maximum_drawdown=profile_portfolio.maximum_drawdown,
        required_samples=30,
        cumulative_samples=cumulative_samples,
        required_cumulative_samples=required_cumulative_samples,
    )


def _resolved_count(
    observations: Sequence[FiveDayObservation],
    profile_id: str,
    *,
    data_end: date | None = None,
) -> int:
    return sum(
        value.plan.profile.profile_id == profile_id
        and _is_resolved(value)
        and (data_end is None or value.resolution_date <= data_end)
        for value in observations
    )


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, SetupType):
        return value.value
    raise TypeError(f"unsupported freeze value: {type(value).__name__}")


def _freeze_hash(
    *,
    research_identity: str,
    profile_matrix_hash: str,
    profiles: Sequence[FrozenFiveDayProfile],
    calibrations: Mapping[str, FiveDayCalibration],
) -> str:
    payload = {
        "calibrations": {
            key: asdict(value)
            for key, value in sorted(calibrations.items())
        },
        "cost_version": COST_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "profile_matrix_hash": profile_matrix_hash,
        "profiles": [asdict(value) for value in profiles],
        "research_identity": research_identity,
        "schema": FIVE_DAY_FREEZE_SCHEMA,
        "sizing_version": SIZING_VERSION,
    }
    encoded = json.dumps(
        payload,
        default=_json_default,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _make_freeze(
    *,
    research_identity: str,
    profile_matrix_hash: str,
    profiles: Sequence[FrozenFiveDayProfile],
    calibrations: Mapping[str, FiveDayCalibration],
) -> FiveDayFreeze:
    frozen_profiles = tuple(profiles)
    frozen_calibrations = dict(sorted(calibrations.items()))
    return FiveDayFreeze(
        schema=FIVE_DAY_FREEZE_SCHEMA,
        research_identity=research_identity,
        profile_matrix_hash=profile_matrix_hash,
        sizing_version=SIZING_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        cost_version=COST_VERSION,
        profiles=frozen_profiles,
        calibrations=frozen_calibrations,
        empty=not frozen_profiles,
        freeze_hash=_freeze_hash(
            research_identity=research_identity,
            profile_matrix_hash=profile_matrix_hash,
            profiles=frozen_profiles,
            calibrations=frozen_calibrations,
        ),
    )


def evaluate_validation_freeze(
    observations: Sequence[FiveDayObservation],
    *,
    train_dates: Sequence[date],
    validation_dates: Sequence[date],
    profile_matrix_hash: str,
    research_identity: str = RESEARCH_IDENTITY,
) -> FiveDayFreeze:
    """Evaluate validation once using train calibration, then freeze evidence."""
    train_sessions = tuple(train_dates)
    validation_sessions = tuple(validation_dates)
    train_set = frozenset(train_sessions)
    validation_set = frozenset(validation_sessions)
    train_values = tuple(
        value
        for value in observations
        if value.plan.candidate.signal_date in train_set
    )
    validation_values = tuple(
        value
        for value in observations
        if value.plan.candidate.signal_date in validation_set
    )
    train_calibrations = build_five_day_calibrations(
        train_values,
        trading_dates=train_sessions,
    )
    profile_ids = tuple(
        sorted({value.plan.profile.profile_id for value in observations})
    )
    qualifying: list[tuple[str, FiveDaySegmentMetrics, int]] = []
    for profile_id in profile_ids:
        train_validation_samples = _resolved_count(
            (*train_values, *validation_values),
            profile_id,
            data_end=validation_sessions[-1],
        )
        metrics = _segment_metrics_from_observations(
            profile_id=profile_id,
            segment="validation",
            observations=validation_values,
            trading_dates=validation_sessions,
            ranking_calibrations=train_calibrations,
            cumulative_samples=train_validation_samples,
            required_cumulative_samples=70,
        )
        if metrics.qualifies:
            qualifying.append(
                (profile_id, metrics, train_validation_samples)
            )

    qualified_ids = frozenset(value[0] for value in qualifying)
    qualified_validation = tuple(
        value
        for value in validation_values
        if value.plan.profile.profile_id in qualified_ids
        and (
            not _is_resolved(value)
            or value.resolution_date <= validation_sessions[-1]
        )
    )
    combined = build_five_day_portfolio_metrics(
        tuple(value.plan for value in qualified_validation),
        qualified_validation,
        train_calibrations,
    )
    if not combined.qualifies:
        return _make_freeze(
            research_identity=research_identity,
            profile_matrix_hash=profile_matrix_hash,
            profiles=(),
            calibrations={},
        )

    ranked_profiles = sorted(
        qualifying,
        key=lambda value: (
            -value[1].net_expectancy,
            -value[1].profitable_wilson_lower,
            value[1].maximum_drawdown,
            value[1].stop_rate,
            value[0],
        ),
    )
    profiles = tuple(
        FrozenFiveDayProfile(
            profile_id=profile_id,
            rank=index,
            train_validation_samples=sample_count,
            validation_metrics=metrics,
        )
        for index, (profile_id, metrics, sample_count) in enumerate(
            ranked_profiles, start=1
        )
    )
    frozen_values = tuple(
        value
        for value in (*train_values, *validation_values)
        if value.plan.profile.profile_id in qualified_ids
    )
    calibrations = build_five_day_calibrations(
        frozen_values,
        trading_dates=(*train_sessions, *validation_sessions),
    )
    return _make_freeze(
        research_identity=research_identity,
        profile_matrix_hash=profile_matrix_hash,
        profiles=profiles,
        calibrations=calibrations,
    )


def evaluate_frozen_test(
    freeze: FiveDayFreeze,
    observations: Sequence[FiveDayObservation],
    *,
    test_dates: Sequence[date],
) -> FiveDayTestAssessment:
    """Assess only profiles and calibrations already present in the freeze."""
    if freeze.empty:
        portfolio = assess_five_day_portfolio(
            accepted_trades=0,
            maximum_drawdown=Decimal("0"),
            maximum_stock_trade_share=Decimal("0"),
            maximum_stock_profit_share=Decimal("0"),
            maximum_sector_trade_share=Decimal("0"),
            maximum_sector_profit_share=Decimal("0"),
            top5_profit_share=Decimal("0"),
            gross_profit_available=False,
        )
        return FiveDayTestAssessment(
            profile_metrics=(),
            portfolio_metrics=portfolio,
            eligible_profile_ids=(),
            reasons=("EMPTY_FREEZE",),
        )

    sessions = tuple(test_dates)
    session_set = frozenset(sessions)
    frozen_by_id = {value.profile_id: value for value in freeze.profiles}
    test_values = tuple(
        value
        for value in observations
        if value.plan.candidate.signal_date in session_set
        and value.plan.profile.profile_id in frozen_by_id
    )
    metrics: list[FiveDaySegmentMetrics] = []
    reasons: list[str] = []
    eligible_ids: list[str] = []
    for frozen in sorted(freeze.profiles, key=lambda value: value.rank):
        test_samples = _resolved_count(
            test_values,
            frozen.profile_id,
            data_end=sessions[-1],
        )
        value = _segment_metrics_from_observations(
            profile_id=frozen.profile_id,
            segment="test",
            observations=test_values,
            trading_dates=sessions,
            ranking_calibrations=freeze.calibrations,
            cumulative_samples=frozen.train_validation_samples + test_samples,
            required_cumulative_samples=100,
        )
        metrics.append(value)
        if value.qualifies:
            eligible_ids.append(frozen.profile_id)
        else:
            reasons.extend(
                f"PROFILE:{frozen.profile_id}:{reason}"
                for reason in value.reasons
            )

    eligible_set = frozenset(eligible_ids)
    combined_values = tuple(
        value
        for value in test_values
        if value.plan.profile.profile_id in eligible_set
        and (
            not _is_resolved(value) or value.resolution_date <= sessions[-1]
        )
    )
    portfolio = build_five_day_portfolio_metrics(
        tuple(value.plan for value in combined_values),
        combined_values,
        freeze.calibrations,
    )
    if not portfolio.qualifies:
        eligible_ids = []
        reasons.extend(f"PORTFOLIO:{reason}" for reason in portfolio.reasons)
    return FiveDayTestAssessment(
        profile_metrics=tuple(metrics),
        portfolio_metrics=portfolio,
        eligible_profile_ids=tuple(eligible_ids),
        reasons=tuple(reasons),
    )
