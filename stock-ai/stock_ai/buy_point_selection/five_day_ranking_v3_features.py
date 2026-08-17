"""Frozen point-in-time feature effects for five-day ranking V3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Mapping, Sequence

from .five_day_return_profiles import resolve_profile_stop
from .five_day_return_runtime import FiveDaySignalPlan
from .five_day_return_validation import FiveDayObservation, _is_resolved
from .models import SelectionPolicy, SetupType


V3_FEATURE_VERSION = "common-point-in-time-features-v1"
V3_FEATURE_NAMES = (
    "setup_quality",
    "structure_duration",
    "structure_width",
    "trigger_gap",
    "risk_distance",
    "resistance_effective_r",
    "log_average_amount5",
)


@dataclass(frozen=True)
class V3PlanFeatures:
    setup_quality: Decimal
    structure_duration: int
    structure_width: Decimal
    trigger_gap: Decimal
    risk_distance: Decimal
    resistance_effective_r: Decimal | None
    log_average_amount5: Decimal


@dataclass(frozen=True)
class V3FeatureEffect:
    full_samples: int
    recent_samples: int
    full_delta: Decimal
    recent_delta: Decimal


@dataclass(frozen=True)
class V3FeatureModel:
    data_end: date
    boundaries: Mapping[str, tuple[Decimal, ...]]
    effects: Mapping[tuple[str, str, str, str], V3FeatureEffect]


@dataclass(frozen=True)
class V3FeatureAdjustment:
    effects: Mapping[str, Decimal]
    total: Decimal


@dataclass(frozen=True)
class _FeatureRow:
    observation: FiveDayObservation
    features: V3PlanFeatures


def _validate_dates(
    values: Sequence[date],
    *,
    name: str,
) -> tuple[date, ...]:
    dates = tuple(values)
    if not dates:
        raise ValueError(f"{name} must not be empty")
    if any(left >= right for left, right in zip(dates, dates[1:])):
        raise ValueError(f"{name} must be unique and increasing")
    return dates


def _weekday_duration(start: date, end: date) -> int:
    if start > end:
        raise ValueError("structure start must not follow signal date")
    current = start
    sessions = 0
    while current <= end:
        if current.weekday() < 5:
            sessions += 1
        current += timedelta(days=1)
    return sessions


def _metric_duration(plan: FiveDaySignalPlan) -> int:
    setup = plan.candidate.setup
    metrics = setup.metrics
    if (
        setup.setup_type == SetupType.TREND_PULLBACK
        and "pullback_sessions" in metrics
    ):
        return int(metrics["pullback_sessions"])
    if (
        setup.setup_type == SetupType.FIRST_LAUNCH_PULLBACK
        and "quiet_sessions" in metrics
    ):
        return int(metrics["quiet_sessions"]) + 1
    if setup.setup_type == SetupType.PRE_BREAKOUT:
        return SelectionPolicy().platform_window
    return _weekday_duration(setup.structure_start, plan.candidate.signal_date)


def _calendar_duration(
    plan: FiveDaySignalPlan,
    trading_dates: Sequence[date],
) -> int:
    dates = _validate_dates(trading_dates, name="trading_dates")
    setup = plan.candidate.setup
    signal_date = plan.candidate.signal_date
    positions = {value: index for index, value in enumerate(dates)}
    if signal_date not in positions:
        raise ValueError("signal date is missing from trading_dates")
    if setup.structure_start in positions:
        duration = positions[signal_date] - positions[setup.structure_start] + 1
        if duration <= 0:
            raise ValueError("structure start must not follow signal date")
        return duration
    return _metric_duration(plan)


def _derive_features(
    plan: FiveDaySignalPlan,
    *,
    structure_duration: int,
) -> V3PlanFeatures:
    setup = plan.candidate.setup
    if (
        not setup.quality.is_finite()
        or not setup.structure_high.is_finite()
        or not setup.structure_low.is_finite()
        or setup.structure_low <= 0
        or setup.structure_high < setup.structure_low
        or not plan.signal_close.is_finite()
        or plan.signal_close <= 0
        or not plan.breakout_trigger.is_finite()
        or plan.candidate.average_amount5_qian <= 0
        or not plan.candidate.average_amount5_qian.is_finite()
        or structure_duration <= 0
    ):
        raise ValueError("invalid signal-time feature inputs")
    stop = resolve_profile_stop(
        plan.profile,
        plan.reference_entry,
        plan.structure_stop,
    )
    if stop.stop_price is None or stop.risk_fraction is None:
        raise ValueError("profile stop is unresolved")
    resistance = plan.resistance_effective_r
    if resistance is not None and not resistance.is_finite():
        raise ValueError("resistance effective R must be finite")
    with localcontext() as context:
        context.prec = 28
        log_amount = plan.candidate.average_amount5_qian.ln()
    return V3PlanFeatures(
        setup_quality=setup.quality,
        structure_duration=structure_duration,
        structure_width=(
            setup.structure_high - setup.structure_low
        )
        / setup.structure_low,
        trigger_gap=(plan.breakout_trigger - plan.signal_close)
        / plan.signal_close,
        risk_distance=stop.risk_fraction,
        resistance_effective_r=resistance,
        log_average_amount5=log_amount,
    )


def derive_v3_plan_features(
    plan: FiveDaySignalPlan,
    *,
    trading_dates: Sequence[date],
) -> V3PlanFeatures:
    """Derive common features from signal-time values and a frozen calendar."""
    return _derive_features(
        plan,
        structure_duration=_calendar_duration(plan, trading_dates),
    )


def _signal_plan_features(plan: FiveDaySignalPlan) -> V3PlanFeatures:
    return _derive_features(
        plan,
        structure_duration=_metric_duration(plan),
    )


def _feature_value(
    features: V3PlanFeatures,
    feature_name: str,
) -> Decimal | None:
    value = getattr(features, feature_name)
    return Decimal(value) if isinstance(value, int) else value


def _quintile_boundaries(values: Sequence[Decimal]) -> tuple[Decimal, ...]:
    ordered = tuple(sorted(values))
    if not ordered:
        return ()
    return tuple(
        ordered[(len(ordered) * numerator + 4) // 5 - 1]
        for numerator in range(1, 5)
    )


def _bin_name(
    value: Decimal | None,
    boundaries: Sequence[Decimal],
) -> str:
    if value is None:
        return "MISSING"
    for index, boundary in enumerate(boundaries, start=1):
        if value <= boundary:
            return f"Q{index}"
    return f"Q{len(tuple(boundaries)) + 1}"


def _average(values: Sequence[Decimal]) -> Decimal:
    return (
        sum(values, Decimal("0")) / Decimal(len(values))
        if values
        else Decimal("0")
    )


def _parent_key(row: _FeatureRow) -> tuple[str, str]:
    plan = row.observation.plan
    return (
        plan.profile.profile_id,
        plan.candidate.setup.setup_type.value,
    )


def _rows_by_parent(
    rows: Sequence[_FeatureRow],
) -> Mapping[tuple[str, str], tuple[_FeatureRow, ...]]:
    parents = sorted({_parent_key(row) for row in rows})
    return {
        parent: tuple(row for row in rows if _parent_key(row) == parent)
        for parent in parents
    }


def _bin_rows(
    rows: Sequence[_FeatureRow],
    *,
    feature_name: str,
    bin_name: str,
    boundaries: Sequence[Decimal],
) -> tuple[_FeatureRow, ...]:
    return tuple(
        row
        for row in rows
        if _bin_name(
            _feature_value(row.features, feature_name),
            boundaries,
        )
        == bin_name
    )


def _net_returns(rows: Sequence[_FeatureRow]) -> tuple[Decimal, ...]:
    return tuple(
        row.observation.trade.net_return
        for row in rows
        if row.observation.trade.net_return is not None
    )


def build_v3_feature_model(
    observations: Sequence[FiveDayObservation],
    *,
    full_dates: Sequence[date],
    recent_dates: Sequence[date],
) -> V3FeatureModel:
    """Freeze full-window quintiles and full/recent signed raw effects."""
    full = _validate_dates(full_dates, name="full_dates")
    recent = _validate_dates(recent_dates, name="recent_dates")
    expected_recent = full[-min(126, len(full)) :]
    if recent != expected_recent:
        raise ValueError("recent_dates must be the trailing full window")
    full_set = frozenset(full)
    recent_set = frozenset(recent)
    full_rows = tuple(
        _FeatureRow(
            observation=value,
            features=derive_v3_plan_features(
                value.plan,
                trading_dates=full,
            ),
        )
        for value in observations
        if value.plan.candidate.signal_date in full_set
        and _is_resolved(value)
        and value.resolution_date <= full[-1]
    )
    recent_rows = tuple(
        row
        for row in full_rows
        if row.observation.plan.candidate.signal_date in recent_set
        and row.observation.resolution_date <= recent[-1]
    )
    boundaries = {
        feature_name: _quintile_boundaries(
            tuple(
                value
                for row in full_rows
                if (
                    value := _feature_value(row.features, feature_name)
                )
                is not None
            )
        )
        for feature_name in V3_FEATURE_NAMES
    }
    full_parents = _rows_by_parent(full_rows)
    recent_parents = _rows_by_parent(recent_rows)
    effects: dict[tuple[str, str, str, str], V3FeatureEffect] = {}
    for parent in sorted(set(full_parents) | set(recent_parents)):
        parent_full = full_parents.get(parent, ())
        parent_recent = recent_parents.get(parent, ())
        full_parent_edge = _average(_net_returns(parent_full))
        recent_parent_edge = _average(_net_returns(parent_recent))
        for feature_name in V3_FEATURE_NAMES:
            feature_boundaries = boundaries[feature_name]
            bins = {
                _bin_name(
                    _feature_value(row.features, feature_name),
                    feature_boundaries,
                )
                for row in (*parent_full, *parent_recent)
            }
            for bin_name in sorted(bins):
                full_bin = _bin_rows(
                    parent_full,
                    feature_name=feature_name,
                    bin_name=bin_name,
                    boundaries=feature_boundaries,
                )
                recent_bin = _bin_rows(
                    parent_recent,
                    feature_name=feature_name,
                    bin_name=bin_name,
                    boundaries=feature_boundaries,
                )
                effects[(*parent, feature_name, bin_name)] = V3FeatureEffect(
                    full_samples=len(full_bin),
                    recent_samples=len(recent_bin),
                    full_delta=(
                        _average(_net_returns(full_bin)) - full_parent_edge
                        if full_bin
                        else Decimal("0")
                    ),
                    recent_delta=(
                        _average(_net_returns(recent_bin))
                        - recent_parent_edge
                        if recent_bin
                        else Decimal("0")
                    ),
                )
    return V3FeatureModel(
        data_end=full[-1],
        boundaries=boundaries,
        effects=dict(sorted(effects.items())),
    )


def _clip(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return min(upper, max(lower, value))


def _same_nonzero_sign(left: Decimal, right: Decimal) -> bool:
    return left * right > 0


def _feature_contribution(
    effect: V3FeatureEffect | None,
    *,
    shrinkage_k: int,
) -> Decimal:
    if (
        effect is None
        or effect.full_samples < 30
        or effect.recent_samples < 15
        or not _same_nonzero_sign(effect.full_delta, effect.recent_delta)
    ):
        return Decimal("0")
    full_reliability = Decimal(effect.full_samples) / Decimal(
        effect.full_samples + shrinkage_k
    )
    recent_reliability = Decimal(effect.recent_samples) / Decimal(
        effect.recent_samples + shrinkage_k
    )
    full_delta = full_reliability * effect.full_delta
    recent_delta = recent_reliability * effect.recent_delta
    combined = (
        full_reliability * full_delta
        + recent_reliability * recent_delta
    ) / (full_reliability + recent_reliability)
    return _clip(
        combined,
        Decimal("-0.001"),
        Decimal("0.001"),
    )


def score_v3_feature_adjustment(
    plan: FiveDaySignalPlan,
    model: V3FeatureModel,
    *,
    shrinkage_k: int,
) -> V3FeatureAdjustment:
    """Score frozen feature effects without recalibration or outcome access."""
    if shrinkage_k not in (30, 60):
        raise ValueError("shrinkage_k must be 30 or 60")
    if model.data_end >= plan.candidate.signal_date:
        raise ValueError("feature model is not point in time")
    features = _signal_plan_features(plan)
    profile_id = plan.profile.profile_id
    setup_type = plan.candidate.setup.setup_type.value
    effects: dict[str, Decimal] = {}
    for feature_name in V3_FEATURE_NAMES:
        boundaries = model.boundaries.get(feature_name)
        if boundaries is None:
            raise ValueError("feature model boundaries are incomplete")
        bin_name = _bin_name(
            _feature_value(features, feature_name),
            boundaries,
        )
        effects[feature_name] = _feature_contribution(
            model.effects.get(
                (profile_id, setup_type, feature_name, bin_name)
            ),
            shrinkage_k=shrinkage_k,
        )
    total = _clip(
        sum(effects.values(), Decimal("0")),
        Decimal("-0.003"),
        Decimal("0.003"),
    )
    return V3FeatureAdjustment(effects=effects, total=total)
