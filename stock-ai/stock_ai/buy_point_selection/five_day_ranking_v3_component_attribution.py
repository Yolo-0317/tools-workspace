"""Train-only score-component attribution for five-day ranking V3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from itertools import groupby
from typing import Sequence, TypeAlias

from .five_day_ranking_v3 import (
    FiveDayV3Policy,
    build_five_day_v3_policies,
)
from .five_day_ranking_v3_attribution import (
    AttributedReturn,
    canonical_decimal_mean,
    exact_decimal_sum,
    spearman_correlation,
    wilson_interval,
)
from stock_ai.market_codes import normalize_code6


COMPONENT_ATTRIBUTION_SCHEMA = (
    "five-day-ranking-v3-component-attribution-v1"
)
COMPONENT_ATTRIBUTION_VERSION = "score-component-ablation-v1"
COMPONENT_IDS = ("EDGE", "CONSISTENCY", "STRUCTURE", "DOWNSIDE")
EXPERIMENT_IDS = (
    "BASELINE",
    "WITHOUT_CONSISTENCY",
    "WITHOUT_STRUCTURE",
    "WITHOUT_DOWNSIDE",
)
PlanIdentity: TypeAlias = tuple[date, str, str, str]


@dataclass(frozen=True)
class ScoreComponents:
    """Signed contributions whose sum reproduces one persisted V3 score."""

    edge: Decimal
    consistency: Decimal
    structure: Decimal
    downside: Decimal

    @property
    def baseline_score(self) -> Decimal:
        with localcontext() as context:
            context.prec = 28
            return (
                self.edge
                + self.consistency
                + self.structure
                + self.downside
            )


@dataclass(frozen=True)
class ComponentOutcome:
    """One ephemeral fixed-five outcome with its persisted score inputs."""

    signal_date: date
    plan_identity: PlanIdentity
    profile_id: str
    setup_quality: Decimal
    full_edge: Decimal
    recent_edge: Decimal
    raw_downside: Decimal
    official_rank: int
    components: ScoreComponents
    value: AttributedReturn


@dataclass(frozen=True)
class ExperimentalRankedOutcome:
    """One outcome after deterministic ranking under an experiment."""

    signal_date: date
    plan_identity: PlanIdentity
    rank: int
    value: AttributedReturn
    components: ScoreComponents


@dataclass(frozen=True)
class ExperimentRanking:
    """Aggregate-safe metadata plus ephemeral ranked outcomes."""

    experiment_id: str
    rows: tuple[ExperimentalRankedOutcome, ...]
    candidate_rows: int
    boundary_ties: int


@dataclass(frozen=True)
class RankMetricAuditTotals:
    raw_difference_sum: Decimal
    index_excess_difference_sum: Decimal
    market_excess_difference_sum: Decimal
    rank_one_win_dates: int
    raw_correlation_sum: Decimal
    index_excess_correlation_sum: Decimal
    market_excess_correlation_sum: Decimal


@dataclass(frozen=True)
class RobustRankMetrics:
    candidate_rows: int
    boundary_ties: int
    paired_dates: int
    correlation_eligible_dates: int
    correlation_dates: int
    audit: RankMetricAuditTotals
    mean_raw_difference: Decimal | None
    median_raw_difference: Decimal | None
    mean_index_excess_difference: Decimal | None
    median_index_excess_difference: Decimal | None
    mean_market_excess_difference: Decimal | None
    median_market_excess_difference: Decimal | None
    rank_one_win_ratio: Decimal | None
    rank_one_win_interval: tuple[Decimal, Decimal] | None
    mean_raw_correlation: Decimal | None
    median_raw_correlation: Decimal | None
    mean_index_excess_correlation: Decimal | None
    median_index_excess_correlation: Decimal | None
    mean_market_excess_correlation: Decimal | None
    median_market_excess_correlation: Decimal | None


@dataclass(frozen=True)
class ComponentCorrelationAuditTotals:
    raw_correlation_sum: Decimal
    index_excess_correlation_sum: Decimal
    market_excess_correlation_sum: Decimal


@dataclass(frozen=True)
class ComponentCorrelationMetrics:
    component_id: str
    eligible_dates: int
    completed_dates: int
    audit: ComponentCorrelationAuditTotals
    mean_raw_correlation: Decimal | None
    median_raw_correlation: Decimal | None
    mean_index_excess_correlation: Decimal | None
    median_index_excess_correlation: Decimal | None
    mean_market_excess_correlation: Decimal | None
    median_market_excess_correlation: Decimal | None


@dataclass(frozen=True)
class AblationDelta:
    paired_dates: int
    correlation_dates: int
    boundary_ties: int
    median_raw_difference_delta: Decimal
    rank_one_win_ratio_delta: Decimal
    mean_raw_correlation_delta: Decimal
    mean_index_excess_difference_delta: Decimal
    mean_market_excess_difference_delta: Decimal


@dataclass(frozen=True)
class ComponentEffectReview:
    component_id: str
    fold1: AblationDelta
    fold2: AblationDelta
    label: str


def _finite_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("score component must be a finite Decimal")
    return value


def reconstruct_score_components(
    *,
    edge: Decimal,
    consistency: Decimal,
    feature_adjustment: Decimal,
    downside: Decimal,
    policy: FiveDayV3Policy,
    persisted_score: Decimal,
) -> ScoreComponents:
    """Reconstruct signed policy contributions and verify the stored score."""

    if policy not in build_five_day_v3_policies():
        raise ValueError("policy is not in the registered V3 policy set")
    values = tuple(
        _finite_decimal(value)
        for value in (
            edge,
            consistency,
            feature_adjustment,
            downside,
            persisted_score,
        )
    )
    (
        finite_edge,
        finite_consistency,
        finite_feature,
        finite_downside,
        finite_persisted,
    ) = values
    with localcontext() as context:
        context.prec = 28
        result = ScoreComponents(
            edge=finite_edge,
            consistency=policy.consistency_weight * finite_consistency,
            structure=policy.structure_weight * finite_feature,
            downside=-policy.downside_weight * finite_downside,
        )
        if result.baseline_score != finite_persisted:
            raise ValueError("persisted V3 score reconstruction mismatch")
    return result


def experiment_score(
    components: ScoreComponents,
    experiment_id: str,
) -> Decimal:
    """Return the preregistered score for exactly one experiment."""

    values = tuple(
        _finite_decimal(value)
        for value in (
            components.edge,
            components.consistency,
            components.structure,
            components.downside,
        )
    )
    edge, consistency, structure, downside = values
    with localcontext() as context:
        context.prec = 28
        if experiment_id == "BASELINE":
            return edge + consistency + structure + downside
        if experiment_id == "WITHOUT_CONSISTENCY":
            return edge + structure + downside
        if experiment_id == "WITHOUT_STRUCTURE":
            return edge + consistency + downside
        if experiment_id == "WITHOUT_DOWNSIDE":
            return edge + consistency + structure
    raise ValueError("unknown component attribution experiment")


def _baseline_key(value: ComponentOutcome) -> tuple[object, ...]:
    return (
        -value.components.baseline_score,
        -value.components.edge,
        -min(value.full_edge, value.recent_edge),
        value.raw_downside,
        -value.setup_quality,
        normalize_code6(value.plan_identity[1]),
        value.profile_id,
    )


def _validate_outcome(value: ComponentOutcome) -> None:
    if (
        len(value.plan_identity) != 4
        or value.plan_identity[0] != value.signal_date
        or not value.plan_identity[2]
        or value.plan_identity[3] != value.profile_id
        or not value.profile_id
        or value.official_rank < 1
    ):
        raise ValueError("invalid component outcome identity or rank")
    for item in (
        value.setup_quality,
        value.full_edge,
        value.recent_edge,
        value.raw_downside,
    ):
        _finite_decimal(item)
    experiment_score(value.components, "BASELINE")


def _boundary_ties(scores: tuple[Decimal, ...]) -> int:
    result = 0
    if len(scores) >= 2 and scores[0] == scores[1]:
        result += 1
    if len(scores) >= 4 and scores[2] == scores[3]:
        result += 1
    return result


def rank_component_experiment(
    rows: tuple[ComponentOutcome, ...],
    experiment_id: str,
) -> ExperimentRanking:
    """Rank identical per-date populations under one frozen experiment."""

    if experiment_id not in EXPERIMENT_IDS:
        raise ValueError("unknown component attribution experiment")
    identities = tuple(value.plan_identity for value in rows)
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate plan identity")
    for value in rows:
        _validate_outcome(value)

    ranked: list[ExperimentalRankedOutcome] = []
    boundary_ties = 0
    ordered = sorted(rows, key=lambda value: value.signal_date)
    for _, grouped in groupby(ordered, key=lambda value: value.signal_date):
        daily = tuple(grouped)
        official_ranks = tuple(sorted(value.official_rank for value in daily))
        if official_ranks != tuple(range(1, len(daily) + 1)):
            raise ValueError("official ranks must be contiguous within date")
        if experiment_id == "BASELINE":
            daily_ranked = tuple(sorted(daily, key=_baseline_key))
            if tuple(value.official_rank for value in daily_ranked) != tuple(
                range(1, len(daily_ranked) + 1)
            ):
                raise ValueError("baseline rank reproduction mismatch")
            scores = tuple(
                value.components.baseline_score for value in daily_ranked
            )
        else:
            daily_ranked = tuple(
                sorted(
                    daily,
                    key=lambda value: (
                        -experiment_score(value.components, experiment_id),
                        value.plan_identity,
                    ),
                )
            )
            scores = tuple(
                experiment_score(value.components, experiment_id)
                for value in daily_ranked
            )
            boundary_ties += _boundary_ties(scores)
        ranked.extend(
            ExperimentalRankedOutcome(
                signal_date=value.signal_date,
                plan_identity=value.plan_identity,
                rank=rank,
                value=value.value,
                components=value.components,
            )
            for rank, value in enumerate(daily_ranked, start=1)
        )
    return ExperimentRanking(
        experiment_id=experiment_id,
        rows=tuple(ranked),
        candidate_rows=len(rows),
        boundary_ties=boundary_ties,
    )


def _median_decimal(values: Sequence[Decimal]) -> Decimal:
    ordered = tuple(sorted(values))
    if not ordered:
        raise ValueError("median requires at least one value")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    with localcontext() as context:
        context.prec = 28
        return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _optional_median(values: Sequence[Decimal]) -> Decimal | None:
    return _median_decimal(values) if values else None


def _optional_exact_mean(
    values: Sequence[Decimal],
) -> tuple[Decimal, Decimal | None]:
    total = exact_decimal_sum(values)
    return total, (
        canonical_decimal_mean(total, len(values)) if values else None
    )


def _group_experimental_rows(
    rows: Sequence[ExperimentalRankedOutcome],
) -> dict[date, dict[int, ExperimentalRankedOutcome]]:
    grouped: dict[date, dict[int, ExperimentalRankedOutcome]] = {}
    identities: set[PlanIdentity] = set()
    for row in rows:
        if row.plan_identity in identities:
            raise ValueError("duplicate experimental plan identity")
        identities.add(row.plan_identity)
        if row.signal_date != row.plan_identity[0] or row.rank < 1:
            raise ValueError("invalid experimental ranked outcome")
        dated = grouped.setdefault(row.signal_date, {})
        if row.rank in dated:
            raise ValueError("duplicate experimental rank within date")
        dated[row.rank] = row
    return grouped


def summarize_experiment_ranking(
    ranking: ExperimentRanking,
) -> RobustRankMetrics:
    """Summarize same-date Rank-1 robustness with exact audit totals."""

    if ranking.candidate_rows != len(ranking.rows) or ranking.boundary_ties < 0:
        raise ValueError("experiment ranking counts are invalid")
    grouped = _group_experimental_rows(ranking.rows)
    raw_differences: list[Decimal] = []
    index_differences: list[Decimal] = []
    market_differences: list[Decimal] = []
    raw_correlations: list[Decimal] = []
    index_correlations: list[Decimal] = []
    market_correlations: list[Decimal] = []
    eligible_correlation_dates = 0

    for signal_date in sorted(grouped):
        dated = grouped[signal_date]
        rank_one = dated.get(1)
        lower = tuple(
            dated[rank].value for rank in (2, 3) if rank in dated
        )
        if rank_one is not None and lower:
            raw_differences.append(
                rank_one.value.raw_return
                - _median_decimal(tuple(value.raw_return for value in lower))
            )
            index_differences.append(
                rank_one.value.index_excess
                - _median_decimal(tuple(value.index_excess for value in lower))
            )
            market_differences.append(
                rank_one.value.market_median_excess
                - _median_decimal(
                    tuple(value.market_median_excess for value in lower)
                )
            )
        if len(dated) < 5:
            continue
        eligible_correlation_dates += 1
        ordered = tuple(dated[rank] for rank in sorted(dated))
        negative_ranks = tuple(Decimal(-value.rank) for value in ordered)
        raw = spearman_correlation(
            negative_ranks,
            tuple(value.value.raw_return for value in ordered),
        )
        index = spearman_correlation(
            negative_ranks,
            tuple(value.value.index_excess for value in ordered),
        )
        market = spearman_correlation(
            negative_ranks,
            tuple(value.value.market_median_excess for value in ordered),
        )
        if raw is None or index is None or market is None:
            continue
        raw_correlations.append(raw)
        index_correlations.append(index)
        market_correlations.append(market)

    raw_sum, raw_mean = _optional_exact_mean(raw_differences)
    index_sum, index_mean = _optional_exact_mean(index_differences)
    market_sum, market_mean = _optional_exact_mean(market_differences)
    raw_corr_sum, raw_corr_mean = _optional_exact_mean(raw_correlations)
    index_corr_sum, index_corr_mean = _optional_exact_mean(index_correlations)
    market_corr_sum, market_corr_mean = _optional_exact_mean(
        market_correlations
    )
    paired_dates = len(raw_differences)
    wins = sum(value > 0 for value in raw_differences)
    win_ratio = (
        canonical_decimal_mean(Decimal(wins), paired_dates)
        if paired_dates
        else None
    )
    return RobustRankMetrics(
        candidate_rows=ranking.candidate_rows,
        boundary_ties=ranking.boundary_ties,
        paired_dates=paired_dates,
        correlation_eligible_dates=eligible_correlation_dates,
        correlation_dates=len(raw_correlations),
        audit=RankMetricAuditTotals(
            raw_difference_sum=raw_sum,
            index_excess_difference_sum=index_sum,
            market_excess_difference_sum=market_sum,
            rank_one_win_dates=wins,
            raw_correlation_sum=raw_corr_sum,
            index_excess_correlation_sum=index_corr_sum,
            market_excess_correlation_sum=market_corr_sum,
        ),
        mean_raw_difference=raw_mean,
        median_raw_difference=_optional_median(raw_differences),
        mean_index_excess_difference=index_mean,
        median_index_excess_difference=_optional_median(index_differences),
        mean_market_excess_difference=market_mean,
        median_market_excess_difference=_optional_median(market_differences),
        rank_one_win_ratio=win_ratio,
        rank_one_win_interval=(
            wilson_interval(wins, paired_dates) if paired_dates else None
        ),
        mean_raw_correlation=raw_corr_mean,
        median_raw_correlation=_optional_median(raw_correlations),
        mean_index_excess_correlation=index_corr_mean,
        median_index_excess_correlation=_optional_median(index_correlations),
        mean_market_excess_correlation=market_corr_mean,
        median_market_excess_correlation=_optional_median(
            market_correlations
        ),
    )


def _component_value(
    components: ScoreComponents,
    component_id: str,
) -> Decimal:
    if component_id == "EDGE":
        return components.edge
    if component_id == "CONSISTENCY":
        return components.consistency
    if component_id == "STRUCTURE":
        return components.structure
    if component_id == "DOWNSIDE":
        return components.downside
    raise ValueError("unknown score component")


def summarize_component_correlations(
    rows: Sequence[ComponentOutcome],
) -> tuple[ComponentCorrelationMetrics, ...]:
    """Correlate signed score contributions with same-date outcomes."""

    grouped: dict[date, list[ComponentOutcome]] = {}
    identities: set[PlanIdentity] = set()
    for row in rows:
        _validate_outcome(row)
        if row.plan_identity in identities:
            raise ValueError("duplicate plan identity")
        identities.add(row.plan_identity)
        grouped.setdefault(row.signal_date, []).append(row)

    result: list[ComponentCorrelationMetrics] = []
    for component_id in COMPONENT_IDS:
        raw_correlations: list[Decimal] = []
        index_correlations: list[Decimal] = []
        market_correlations: list[Decimal] = []
        eligible_dates = 0
        for signal_date in sorted(grouped):
            dated = grouped[signal_date]
            if len(dated) < 5:
                continue
            eligible_dates += 1
            component_values = tuple(
                _component_value(value.components, component_id)
                for value in dated
            )
            raw = spearman_correlation(
                component_values,
                tuple(value.value.raw_return for value in dated),
            )
            index = spearman_correlation(
                component_values,
                tuple(value.value.index_excess for value in dated),
            )
            market = spearman_correlation(
                component_values,
                tuple(value.value.market_median_excess for value in dated),
            )
            if raw is None or index is None or market is None:
                continue
            raw_correlations.append(raw)
            index_correlations.append(index)
            market_correlations.append(market)
        raw_sum, raw_mean = _optional_exact_mean(raw_correlations)
        index_sum, index_mean = _optional_exact_mean(index_correlations)
        market_sum, market_mean = _optional_exact_mean(market_correlations)
        result.append(
            ComponentCorrelationMetrics(
                component_id=component_id,
                eligible_dates=eligible_dates,
                completed_dates=len(raw_correlations),
                audit=ComponentCorrelationAuditTotals(
                    raw_correlation_sum=raw_sum,
                    index_excess_correlation_sum=index_sum,
                    market_excess_correlation_sum=market_sum,
                ),
                mean_raw_correlation=raw_mean,
                median_raw_correlation=_optional_median(raw_correlations),
                mean_index_excess_correlation=index_mean,
                median_index_excess_correlation=_optional_median(
                    index_correlations
                ),
                mean_market_excess_correlation=market_mean,
                median_market_excess_correlation=_optional_median(
                    market_correlations
                ),
            )
        )
    return tuple(result)


def compare_ablation(
    baseline: RobustRankMetrics,
    ablation: RobustRankMetrics,
) -> AblationDelta:
    """Calculate ablation-minus-baseline deltas on comparable metrics."""

    if (
        baseline.candidate_rows != ablation.candidate_rows
        or baseline.paired_dates != ablation.paired_dates
        or baseline.correlation_dates != ablation.correlation_dates
    ):
        raise ValueError("ablation metrics are not comparable")
    fields = (
        baseline.median_raw_difference,
        ablation.median_raw_difference,
        baseline.rank_one_win_ratio,
        ablation.rank_one_win_ratio,
        baseline.mean_raw_correlation,
        ablation.mean_raw_correlation,
        baseline.mean_index_excess_difference,
        ablation.mean_index_excess_difference,
        baseline.mean_market_excess_difference,
        ablation.mean_market_excess_difference,
    )
    if any(value is None for value in fields):
        raise ValueError("ablation metrics are incomplete")
    finite = tuple(_finite_decimal(value) for value in fields)
    with localcontext() as context:
        context.prec = 28
        return AblationDelta(
            paired_dates=baseline.paired_dates,
            correlation_dates=baseline.correlation_dates,
            boundary_ties=ablation.boundary_ties,
            median_raw_difference_delta=finite[1] - finite[0],
            rank_one_win_ratio_delta=finite[3] - finite[2],
            mean_raw_correlation_delta=finite[5] - finite[4],
            mean_index_excess_difference_delta=finite[7] - finite[6],
            mean_market_excess_difference_delta=finite[9] - finite[8],
        )


def _core_positive(value: AblationDelta) -> bool:
    return (
        value.median_raw_difference_delta > 0
        and value.rank_one_win_ratio_delta > 0
        and value.mean_raw_correlation_delta > 0
    )


def _core_negative(value: AblationDelta) -> bool:
    return (
        value.median_raw_difference_delta < 0
        and value.rank_one_win_ratio_delta < 0
        and value.mean_raw_correlation_delta < 0
    )


def _harmful_direction(value: AblationDelta) -> bool:
    return (
        _core_positive(value)
        and value.mean_index_excess_difference_delta >= 0
        and value.mean_market_excess_difference_delta >= 0
    )


def _helpful_direction(value: AblationDelta) -> bool:
    return (
        _core_negative(value)
        and value.mean_index_excess_difference_delta <= 0
        and value.mean_market_excess_difference_delta <= 0
    )


def classify_component_effect(
    fold1: AblationDelta,
    fold2: AblationDelta,
    *,
    component_id: str,
) -> ComponentEffectReview:
    """Assign one descriptive component label from two train folds only."""

    if component_id not in {"CONSISTENCY", "STRUCTURE", "DOWNSIDE"}:
        raise ValueError("component is not an ablation target")
    usable = all(
        value.paired_dates >= 30
        and value.correlation_dates >= 30
        and value.boundary_ties == 0
        for value in (fold1, fold2)
    )
    label = "INCONCLUSIVE"
    if usable:
        if _harmful_direction(fold1) and _harmful_direction(fold2):
            label = "CONSISTENTLY_HARMFUL"
        elif _helpful_direction(fold1) and _helpful_direction(fold2):
            label = "CONSISTENTLY_HELPFUL"
        elif (
            _core_positive(fold1) and _core_negative(fold2)
        ) or (
            _core_negative(fold1) and _core_positive(fold2)
        ):
            label = "REGIME_UNSTABLE"
    return ComponentEffectReview(
        component_id=component_id,
        fold1=fold1,
        fold2=fold2,
        label=label,
    )
