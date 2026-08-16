"""Train-only point-in-time diagnostics for five-day plan rankings."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from .five_day_return_profiles import build_five_day_return_profiles
from .five_day_return_runtime import FiveDayResearchReview, FiveDaySignalPlan
from .five_day_return_validation import (
    SELECTED_PORTFOLIO_METRIC_VERSION,
    FiveDayCalibration,
    FiveDayObservation,
    FiveDayRanking,
    FiveDaySelection,
    FiveDaySelectedSegment,
    _is_resolved,
    build_five_day_calibrations,
    evaluate_five_day_selection_segment,
    evaluate_selected_five_day_segment,
    resolve_five_day_calibration,
    select_five_day_portfolio,
)
from .validation import ChronologicalSplit


RANKING_RESEARCH_SCHEMA = "five-day-ranking-train-v1"
RANKING_KEY_VERSION = "five-day-ranking-key-v1"
TRAIN_DAILY_LIMITS = (1, 3, 5)


@dataclass(frozen=True)
class RankingPolicy:
    ranking_key_version: str
    daily_limit: int
    capacity: int
    metric_version: str


REGISTERED_VALIDATION_POLICY = RankingPolicy(
    ranking_key_version=RANKING_KEY_VERSION,
    daily_limit=3,
    capacity=3,
    metric_version=SELECTED_PORTFOLIO_METRIC_VERSION,
)


@dataclass(frozen=True)
class TrainFold:
    fold_id: str
    calibration_dates: tuple[date, ...]
    evaluation_dates: tuple[date, ...]
    calibration_data_end: date
    excluded_unresolved_calibration_rows: int


@dataclass(frozen=True)
class RankingVariantMetrics:
    fold_id: str
    scope: str
    daily_limit: int
    segment: FiveDaySelectedSegment


@dataclass(frozen=True)
class AttributionRow:
    fold_id: str
    scope: str
    dimension: str
    bucket: str
    selected_plans: int
    admitted_trades: int
    resolved_observations: int
    win_count: int
    loss_count: int
    stop_count: int
    gross_pnl: Decimal
    net_pnl: Decimal
    cost_drag: Decimal
    net_expectancy: Decimal


@dataclass(frozen=True)
class FiveDayRankingTrainReview:
    schema: str
    parent_research_identity: str
    parent_input_fingerprint: str
    split: ChronologicalSplit
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    sizing_version: str
    evaluator_version: str
    cost_version: str
    folds: tuple[TrainFold, ...]
    daily_limits: tuple[int, ...]
    variants: tuple[RankingVariantMetrics, ...]
    attribution: tuple[AttributionRow, ...]
    quintile_boundaries: Mapping[str, Mapping[str, tuple[Decimal, ...]]]
    fold_stability: Mapping[str, str]
    registered_validation_policy: RankingPolicy
    validation_outcomes_read: bool
    test_outcomes_read: bool


def _fold_specs(
    train_dates: Sequence[date],
) -> tuple[tuple[str, tuple[date, ...], tuple[date, ...]], ...]:
    values = tuple(train_dates)
    if len(values) != 378:
        raise ValueError("ranking diagnostics require exactly 378 train sessions")
    return (
        ("train-fold-1", values[:252], values[252:315]),
        ("train-fold-2", values[:315], values[315:378]),
    )


def _combine_selections(
    values: Sequence[FiveDaySelection],
) -> FiveDaySelection:
    ranking_counts: Counter[str] = Counter()
    funnel_counts: Counter[str] = Counter()
    for value in values:
        ranking_counts.update(value.ranking.rejection_counts)
        funnel_counts.update(value.funnel_counts)
    return FiveDaySelection(
        ranking=FiveDayRanking(
            plans=tuple(
                plan for value in values for plan in value.ranking.plans
            ),
            rejection_counts=dict(sorted(ranking_counts.items())),
            ranked=tuple(
                row for value in values for row in value.ranking.ranked
            ),
        ),
        selected_observations=tuple(
            row for value in values for row in value.selected_observations
        ),
        admitted=tuple(row for value in values for row in value.admitted),
        funnel_counts=dict(sorted(funnel_counts.items())),
        incomplete=any(value.incomplete for value in values),
    )


def _descriptive_only(
    value: FiveDaySelectedSegment,
) -> FiveDaySelectedSegment:
    reason = "TRAIN_DIAGNOSTIC_ONLY"
    metric_reasons = value.metrics.reasons
    portfolio_reasons = value.portfolio.reasons
    return replace(
        value,
        metrics=replace(
            value.metrics,
            qualifies=False,
            reasons=(
                metric_reasons
                if reason in metric_reasons
                else (*metric_reasons, reason)
            ),
        ),
        portfolio=replace(
            value.portfolio,
            qualifies=False,
            reasons=(
                portfolio_reasons
                if reason in portfolio_reasons
                else (*portfolio_reasons, reason)
            ),
        ),
    )


def _plan_key(plan: FiveDaySignalPlan) -> tuple[object, ...]:
    return (
        plan.candidate.signal_date,
        plan.candidate.code,
        plan.structure_id,
        plan.profile.profile_id,
    )


def _rank_band(rank: int) -> str:
    if rank == 1:
        return "RANK_1"
    if rank <= 3:
        return "RANK_2_3"
    if rank <= 5:
        return "RANK_4_5"
    return "RANK_6_PLUS"


def _quintile_boundaries(values: Sequence[Decimal]) -> tuple[Decimal, ...]:
    ordered = tuple(sorted(values))
    if not ordered:
        return ()
    return tuple(
        ordered[max(0, (len(ordered) * fifth + 4) // 5 - 1)]
        for fifth in range(1, 5)
    )


def _quintile_bucket(
    value: Decimal,
    boundaries: Sequence[Decimal],
) -> str:
    return f"Q{1 + sum(value > boundary for boundary in boundaries)}"


def _cost_drag(value: FiveDayObservation | None) -> Decimal:
    if value is None:
        return Decimal("0")
    exit_fees = (
        value.trade.exit.fees
        if value.trade.exit is not None
        else Decimal("0")
    )
    return value.trade.entry_fees + exit_fees


def _cost_drag_bucket(value: FiveDayObservation | None) -> str:
    if value is None or value.trade.entry_date is None:
        return "NO_TRADE"
    if value.trade.evaluation_notional <= 0:
        return "UNAVAILABLE"
    ratio = _cost_drag(value) / value.trade.evaluation_notional
    if ratio <= 0:
        return "ZERO"
    if ratio <= Decimal("0.001"):
        return "LE_10_BPS"
    if ratio <= Decimal("0.003"):
        return "LE_30_BPS"
    return "GT_30_BPS"


_ATTRIBUTION_DIMENSIONS = (
    "rank_band",
    "setup_type",
    "market_status",
    "sector_resonance",
    "resistance_basis",
    "setup_quality_quintile",
    "calibration_expectancy_quintile",
    "profile",
    "trade_status",
    "gross_to_net_cost_drag",
)


def _fold_attribution(
    *,
    fold_id: str,
    segment: FiveDaySelectedSegment,
    observations: Sequence[FiveDayObservation],
    calibrations: Mapping[str, FiveDayCalibration],
) -> tuple[tuple[AttributionRow, ...], Mapping[str, tuple[Decimal, ...]]]:
    ranking = segment.selection.ranking.ranked
    by_plan = {_plan_key(value.plan): value for value in observations}
    calibration_by_plan = {
        _plan_key(row.plan): resolve_five_day_calibration(
            calibrations,
            profile_id=row.plan.profile.profile_id,
            setup_type=row.plan.candidate.setup.setup_type,
            market_status=row.plan.candidate.market_status,
            sector_resonating=row.plan.candidate.sector_resonating,
        )
        for row in ranking
    }
    boundaries = {
        "setup_quality": _quintile_boundaries(
            tuple(row.plan.candidate.setup.quality for row in ranking)
        ),
        "calibration_expectancy": _quintile_boundaries(
            tuple(
                value.net_expectancy
                for value in calibration_by_plan.values()
                if value is not None
            )
        ),
    }
    groups: dict[tuple[str, str], list[tuple[object, ...]]] = {
        ("rank_band", bucket): []
        for bucket in ("RANK_1", "RANK_2_3", "RANK_4_5", "RANK_6_PLUS")
    }
    ranked_by_key = {_plan_key(row.plan): row for row in ranking}
    for row in ranking:
        key = _plan_key(row.plan)
        observation = by_plan.get(key)
        calibration = calibration_by_plan[key]
        dimensions = {
            "rank_band": _rank_band(row.rank),
            "setup_type": row.plan.candidate.setup.setup_type.value,
            "market_status": row.plan.candidate.market_status or "UNKNOWN",
            "sector_resonance": (
                "RESONATING"
                if row.plan.candidate.sector_resonating is True
                else "NOT_RESONATING"
                if row.plan.candidate.sector_resonating is False
                else "UNKNOWN"
            ),
            "resistance_basis": row.plan.resistance_basis,
            "setup_quality_quintile": _quintile_bucket(
                row.plan.candidate.setup.quality,
                boundaries["setup_quality"],
            ),
            "calibration_expectancy_quintile": (
                _quintile_bucket(
                    calibration.net_expectancy,
                    boundaries["calibration_expectancy"],
                )
                if calibration is not None
                else "UNAVAILABLE"
            ),
            "profile": row.plan.profile.profile_id,
            "trade_status": (
                observation.trade.status
                if observation is not None
                else "MISSING_OBSERVATION"
            ),
            "gross_to_net_cost_drag": _cost_drag_bucket(observation),
        }
        for dimension, bucket in dimensions.items():
            groups.setdefault((dimension, bucket), []).append(key)

    admitted_keys = frozenset(
        _plan_key(value.plan) for value in segment.selection.admitted
    )
    rows: list[AttributionRow] = []
    for dimension in _ATTRIBUTION_DIMENSIONS:
        dimension_groups = sorted(
            (key, values)
            for key, values in groups.items()
            if key[0] == dimension
        )
        for (_dimension, bucket), keys in dimension_groups:
            values = tuple(by_plan.get(key) for key in keys)
            resolved = tuple(
                value
                for value in values
                if value is not None and _is_resolved(value)
            )
            net_returns = tuple(
                value.trade.net_return
                for value in resolved
                if value.trade.net_return is not None
            )
            drag = sum((_cost_drag(value) for value in resolved), Decimal("0"))
            net_pnl = sum(
                (value.trade.net_pnl for value in resolved),
                Decimal("0"),
            )
            rows.append(
                AttributionRow(
                    fold_id=fold_id,
                    scope="global",
                    dimension=dimension,
                    bucket=bucket,
                    selected_plans=sum(
                        ranked_by_key[key].selected for key in keys
                    ),
                    admitted_trades=sum(key in admitted_keys for key in keys),
                    resolved_observations=len(resolved),
                    win_count=sum(value > 0 for value in net_returns),
                    loss_count=sum(value < 0 for value in net_returns),
                    stop_count=sum(
                        value.trade.status == "STOPPED" for value in resolved
                    ),
                    gross_pnl=net_pnl + drag,
                    net_pnl=net_pnl,
                    cost_drag=drag,
                    net_expectancy=(
                        sum(net_returns, Decimal("0")) / Decimal(len(net_returns))
                        if net_returns
                        else Decimal("0")
                    ),
                )
            )
    return tuple(rows), boundaries


def build_five_day_ranking_train_review(
    review: FiveDayResearchReview,
    *,
    parent_research_identity: str,
) -> FiveDayRankingTrainReview:
    """Project a complete legacy review onto train-only expanding folds."""
    if len(parent_research_identity) != 64 or any(
        value not in "0123456789abcdef" for value in parent_research_identity
    ):
        raise ValueError("parent research identity must be a sha256 digest")
    if not review.point_in_time_complete or review.test_outcomes_read:
        raise ValueError("base research review is incomplete or test-tainted")
    if tuple(
        len(values)
        for values in (
            review.split.train,
            review.split.validation,
            review.split.test,
        )
    ) != (378, 126, 126):
        raise ValueError("ranking diagnostics require the 378/126/126 split")
    train_dates = tuple(review.split.train)
    train_set = frozenset(train_dates)
    train_observations = tuple(
        value
        for value in review.observations
        if value.plan.candidate.signal_date in train_set
    )
    folds: list[TrainFold] = []
    variants: list[RankingVariantMetrics] = []
    attribution: list[AttributionRow] = []
    quintile_boundaries: dict[str, Mapping[str, tuple[Decimal, ...]]] = {}
    fold_segments: dict[tuple[str, str, int], FiveDaySelectedSegment] = {}
    profiles = build_five_day_return_profiles()
    for fold_id, calibration_dates, evaluation_dates in _fold_specs(train_dates):
        calibration_set = frozenset(calibration_dates)
        boundary = evaluation_dates[0]
        calibration_candidates = tuple(
            value
            for value in train_observations
            if value.plan.candidate.signal_date in calibration_set
        )
        excluded = sum(
            not _is_resolved(value) or value.resolution_date >= boundary
            for value in calibration_candidates
        )
        calibration_observations = tuple(
            value
            for value in calibration_candidates
            if _is_resolved(value) and value.resolution_date < boundary
        )
        calibrations = build_five_day_calibrations(
            calibration_observations,
            trading_dates=calibration_dates,
        )
        evaluation_set = frozenset(evaluation_dates)
        evaluation_observations = tuple(
            value
            for value in train_observations
            if value.plan.candidate.signal_date in evaluation_set
        )
        folds.append(
            TrainFold(
                fold_id=fold_id,
                calibration_dates=calibration_dates,
                evaluation_dates=evaluation_dates,
                calibration_data_end=calibration_dates[-1],
                excluded_unresolved_calibration_rows=excluded,
            )
        )
        for daily_limit in TRAIN_DAILY_LIMITS:
            for profile in profiles:
                scope = f"profile:{profile.profile_id}"
                segment = _descriptive_only(
                    evaluate_selected_five_day_segment(
                        profile_id=profile.profile_id,
                        segment=fold_id,
                        observations=evaluation_observations,
                        trading_dates=evaluation_dates,
                        ranking_calibrations=calibrations,
                        daily_limit=daily_limit,
                        capacity=3,
                        cumulative_samples=0,
                        required_samples=0,
                        required_cumulative_samples=0,
                    )
                )
                fold_segments[(fold_id, scope, daily_limit)] = segment
                variants.append(
                    RankingVariantMetrics(
                        fold_id=fold_id,
                        scope=scope,
                        daily_limit=daily_limit,
                        segment=segment,
                    )
                )
            global_selection = select_five_day_portfolio(
                tuple(value.plan for value in evaluation_observations),
                evaluation_observations,
                calibrations,
                daily_limit=daily_limit,
                capacity=3,
            )
            global_segment = _descriptive_only(
                evaluate_five_day_selection_segment(
                    profile_id="GLOBAL",
                    segment=fold_id,
                    selection=global_selection,
                    trading_dates=evaluation_dates,
                    cumulative_samples=len(global_selection.admitted),
                    required_samples=0,
                    required_cumulative_samples=0,
                )
            )
            fold_segments[(fold_id, "global", daily_limit)] = global_segment
            variants.append(
                RankingVariantMetrics(
                    fold_id=fold_id,
                    scope="global",
                    daily_limit=daily_limit,
                    segment=global_segment,
                )
            )
        fold_attribution, fold_boundaries = _fold_attribution(
            fold_id=fold_id,
            segment=fold_segments[(fold_id, "global", 5)],
            observations=evaluation_observations,
            calibrations=calibrations,
        )
        attribution.extend(fold_attribution)
        quintile_boundaries[fold_id] = fold_boundaries

    combined_dates = tuple(
        value for fold in folds for value in fold.evaluation_dates
    )
    scopes = tuple(
        f"profile:{profile.profile_id}" for profile in profiles
    ) + ("global",)
    for daily_limit in TRAIN_DAILY_LIMITS:
        for scope in scopes:
            selection = _combine_selections(
                tuple(
                    fold_segments[(fold.fold_id, scope, daily_limit)].selection
                    for fold in folds
                )
            )
            profile_id = scope.removeprefix("profile:")
            if scope == "global":
                profile_id = "GLOBAL"
            segment = _descriptive_only(
                evaluate_five_day_selection_segment(
                    profile_id=profile_id,
                    segment="train-combined",
                    selection=selection,
                    trading_dates=combined_dates,
                    cumulative_samples=len(selection.admitted),
                    required_samples=0,
                    required_cumulative_samples=0,
                )
            )
            variants.append(
                RankingVariantMetrics(
                    fold_id="train-combined",
                    scope=scope,
                    daily_limit=daily_limit,
                    segment=segment,
                )
            )
    by_variant = {
        (value.fold_id, value.scope, value.daily_limit): value
        for value in variants
    }
    fold_stability = {
        f"{scope}|top:{daily_limit}": (
            "STABLE"
            if all(
                by_variant[(fold_id, scope, daily_limit)]
                .segment.metrics.net_expectancy
                > 0
                and by_variant[(fold_id, scope, daily_limit)]
                .segment.metrics.maximum_drawdown
                <= Decimal("0.10")
                for fold_id in ("train-fold-1", "train-fold-2")
            )
            else "UNSTABLE"
        )
        for daily_limit in TRAIN_DAILY_LIMITS
        for scope in scopes
    }
    return FiveDayRankingTrainReview(
        schema=RANKING_RESEARCH_SCHEMA,
        parent_research_identity=parent_research_identity,
        parent_input_fingerprint=review.input_fingerprint,
        split=review.split,
        formal_rule_version=review.formal_rule_version,
        formal_policy_hash=review.formal_policy_hash,
        profile_matrix_hash=review.profile_matrix_hash,
        sizing_version=review.sizing_version,
        evaluator_version=review.evaluator_version,
        cost_version=review.cost_version,
        folds=tuple(folds),
        daily_limits=TRAIN_DAILY_LIMITS,
        variants=tuple(variants),
        attribution=tuple(attribution),
        quintile_boundaries=quintile_boundaries,
        fold_stability=fold_stability,
        registered_validation_policy=REGISTERED_VALIDATION_POLICY,
        validation_outcomes_read=False,
        test_outcomes_read=False,
    )
