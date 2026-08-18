"""Train-only score-component attribution for five-day ranking V3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
import hashlib
from itertools import groupby
import json
from typing import TYPE_CHECKING, Mapping, Sequence, TypeAlias

from .five_day_ranking_v3 import (
    V3_POLICY_IDS,
    V3_SELECTION_MODES,
    FiveDayV3Policy,
    build_five_day_v3_policies,
)
from .five_day_ranking_v3_attribution import (
    AttributedReturn,
    MarketClosePanel,
    attribute_interval,
    canonical_decimal_mean,
    exact_decimal_sum,
    fifth_subsequent_train_date,
    spearman_correlation,
    wilson_interval,
)
from stock_ai.market_codes import normalize_code6

if TYPE_CHECKING:
    from .five_day_ranking_v3_attribution_report import (
        FiveDayRankingV3AttributionArtifact,
    )
    from .five_day_ranking_v3_report import FiveDayRankingV3TrainArtifact
    from .five_day_return_runtime import FiveDayResearchReview


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


@dataclass(frozen=True)
class CoverageComparison:
    candidate_rows: int
    eligible_outcomes: int
    excluded_without_train_horizon: int
    excluded_missing_coverage: int
    population_fingerprint: str
    benchmark_fingerprint: str


@dataclass(frozen=True)
class FoldExperimentReview:
    fold_id: str
    policy_id: str
    experiment_id: str
    coverage: CoverageComparison
    metrics: RobustRankMetrics
    status: str


@dataclass(frozen=True)
class ComponentCorrelationReview:
    fold_id: str
    policy_id: str
    population_fingerprint: str
    metrics: tuple[ComponentCorrelationMetrics, ...]


@dataclass(frozen=True)
class PolicyComponentEffect:
    policy_id: str
    component_id: str
    fold1: AblationDelta
    fold2: AblationDelta
    label: str


@dataclass(frozen=True)
class FiveDayRankingV3ComponentAttributionReview:
    schema: str
    component_attribution_version: str
    parent_train_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    parent_attribution_identity: str
    market_data_fingerprint: str
    train_split_identity: str
    fold_experiments: tuple[FoldExperimentReview, ...]
    combined_experiments: tuple[FoldExperimentReview, ...]
    fold_component_correlations: tuple[ComponentCorrelationReview, ...]
    combined_component_correlations: tuple[ComponentCorrelationReview, ...]
    component_effects: tuple[PolicyComponentEffect, ...]
    status: str
    train_only: bool
    validation_outcomes_read: bool
    test_outcomes_read: bool
    promotion_eligible: bool
    trade_permission: str


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


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _plan_identity(value: object) -> PlanIdentity:
    if not isinstance(value, Mapping):
        raise ValueError("invalid V3 plan key")
    try:
        signal_date = date.fromisoformat(str(value["signal_date"]))
        code = normalize_code6(str(value["code"]))
        structure_id = str(value["structure_id"])
        profile_id = str(value["profile_id"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid V3 plan key") from None
    if not code or not structure_id or not profile_id:
        raise ValueError("invalid V3 plan key")
    return signal_date, code, structure_id, profile_id


def _observation_identity(value: object) -> PlanIdentity:
    plan = value.plan
    return (
        plan.candidate.signal_date,
        normalize_code6(plan.candidate.code),
        plan.structure_id,
        plan.profile.profile_id,
    )


def _empty_review(
    train_artifact: FiveDayRankingV3TrainArtifact,
    parent_attribution: FiveDayRankingV3AttributionArtifact,
    *,
    parent_research_identity: str,
    status: str,
) -> FiveDayRankingV3ComponentAttributionReview:
    return FiveDayRankingV3ComponentAttributionReview(
        schema=COMPONENT_ATTRIBUTION_SCHEMA,
        component_attribution_version=COMPONENT_ATTRIBUTION_VERSION,
        parent_train_identity=train_artifact.artifact_identity,
        parent_research_identity=parent_research_identity,
        parent_input_fingerprint=train_artifact.parent_input_fingerprint,
        parent_attribution_identity=parent_attribution.artifact_identity,
        market_data_fingerprint=parent_attribution.market_data_fingerprint,
        train_split_identity=_canonical_hash(train_artifact.payload["split"]),
        fold_experiments=(),
        combined_experiments=(),
        fold_component_correlations=(),
        combined_component_correlations=(),
        component_effects=(),
        status=status,
        train_only=True,
        validation_outcomes_read=False,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )


def _scored_without_presentation(value: object) -> str:
    if not isinstance(value, list):
        raise ValueError("invalid scored registry")
    normalized: list[dict[str, object]] = []
    for row in value:
        if not isinstance(row, Mapping):
            raise ValueError("invalid scored registry")
        normalized.append(
            {str(key): item for key, item in row.items() if key != "selected"}
        )
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _deduplicated_variants(
    train_artifact: FiveDayRankingV3TrainArtifact,
) -> dict[tuple[str, str], Mapping[str, object]]:
    raw = train_artifact.payload.get("variants")
    if not isinstance(raw, list):
        raise ValueError("invalid V3 variant registry")
    grouped: dict[tuple[str, str], dict[str, Mapping[str, object]]] = {}
    for value in raw:
        if not isinstance(value, Mapping):
            raise ValueError("invalid V3 variant registry")
        try:
            key = (str(value["fold_id"]), str(value["policy_id"]))
            mode = str(value["selection_mode"])
        except KeyError:
            raise ValueError("invalid V3 variant registry") from None
        if mode in grouped.setdefault(key, {}):
            raise ValueError("duplicate V3 selection mode")
        grouped[key][mode] = value
    expected_keys = {
        (fold_id, policy_id)
        for fold_id in ("train-fold-1", "train-fold-2", "train-combined")
        for policy_id in V3_POLICY_IDS
    }
    if set(grouped) != expected_keys:
        raise ValueError("invalid V3 variant registry")
    result: dict[tuple[str, str], Mapping[str, object]] = {}
    for key, modes in grouped.items():
        if set(modes) != set(V3_SELECTION_MODES):
            raise ValueError("invalid V3 selection mode registry")
        fingerprints = {
            _scored_without_presentation(value.get("scored"))
            for value in modes.values()
        }
        if len(fingerprints) != 1:
            raise ValueError("V3 selection-mode scored drift")
        result[key] = modes["FORMAL"]
    return result


def _fold_date_registry(
    train_artifact: FiveDayRankingV3TrainArtifact,
) -> dict[str, frozenset[date]]:
    folds = train_artifact.payload.get("folds")
    if not isinstance(folds, list):
        raise ValueError("invalid V3 fold registry")
    result: dict[str, frozenset[date]] = {}
    for fold in folds:
        if not isinstance(fold, Mapping):
            raise ValueError("invalid V3 fold registry")
        try:
            fold_id = str(fold["fold_id"])
            dates = frozenset(
                date.fromisoformat(str(value))
                for value in fold["evaluation_dates"]
            )
        except (KeyError, TypeError, ValueError):
            raise ValueError("invalid V3 fold registry") from None
        result[fold_id] = dates
    if set(result) != {"train-fold-1", "train-fold-2"}:
        raise ValueError("invalid V3 fold registry")
    return result


def _population_fingerprint(
    rows: Sequence[ComponentOutcome],
    endpoints: Mapping[PlanIdentity, date],
) -> str:
    return _canonical_hash(
        [
            {
                "identity": (
                    row.signal_date.isoformat(),
                    row.plan_identity[1],
                    row.plan_identity[2],
                    row.plan_identity[3],
                ),
                "endpoint": endpoints[row.plan_identity].isoformat(),
                "raw": str(row.value.raw_return),
                "index_excess": str(row.value.index_excess),
                "market_excess": str(row.value.market_median_excess),
            }
            for row in sorted(rows, key=lambda item: item.plan_identity)
        ]
    )


def _combined_coverage(
    left: CoverageComparison,
    right: CoverageComparison,
    population_fingerprint: str,
) -> CoverageComparison:
    return CoverageComparison(
        candidate_rows=left.candidate_rows + right.candidate_rows,
        eligible_outcomes=left.eligible_outcomes + right.eligible_outcomes,
        excluded_without_train_horizon=(
            left.excluded_without_train_horizon
            + right.excluded_without_train_horizon
        ),
        excluded_missing_coverage=(
            left.excluded_missing_coverage + right.excluded_missing_coverage
        ),
        population_fingerprint=population_fingerprint,
        benchmark_fingerprint=left.benchmark_fingerprint,
    )


def build_five_day_ranking_v3_component_attribution_review(
    train_artifact: FiveDayRankingV3TrainArtifact,
    research: FiveDayResearchReview,
    parent_attribution: FiveDayRankingV3AttributionArtifact,
    *,
    parent_research_identity: str,
    market_panel: MarketClosePanel,
) -> FiveDayRankingV3ComponentAttributionReview:
    """Build a deduplicated, aggregate-only train component diagnosis."""

    try:
        from .five_day_ranking_v3_attribution import (
            build_five_day_ranking_v3_attribution_review,
        )
        from .five_day_ranking_v3_attribution_report import (
            five_day_ranking_v3_attribution_payload,
        )

        parent_payload = parent_attribution.payload
        if (
            parent_research_identity != train_artifact.parent_research_identity
            or parent_research_identity != parent_attribution.parent_research_identity
            or research.input_fingerprint != train_artifact.parent_input_fingerprint
            or research.input_fingerprint != parent_attribution.parent_input_fingerprint
            or parent_attribution.parent_train_identity
            != train_artifact.artifact_identity
            or parent_attribution.status != "COMPLETE"
            or not isinstance(parent_payload, Mapping)
            or parent_payload.get("train_only") is not True
            or parent_payload.get("validation_outcomes_read") is not False
            or parent_payload.get("test_outcomes_read") is not False
            or parent_payload.get("promotion_eligible") is not False
            or parent_payload.get("trade_permission") != "NO-TRADE"
        ):
            raise ValueError("component attribution lineage mismatch")
        replay = build_five_day_ranking_v3_attribution_review(
            train_artifact,
            research,
            parent_research_identity=parent_research_identity,
            market_panel=market_panel,
        )
        replay_payload = five_day_ranking_v3_attribution_payload(replay)
        if (
            replay_payload != parent_payload
            or replay.market_data_fingerprint
            != parent_attribution.market_data_fingerprint
            or replay_payload.get("artifact_identity")
            != parent_attribution.artifact_identity
        ):
            raise ValueError("parent attribution replay mismatch")
        variants = _deduplicated_variants(train_artifact)
        fold_dates = _fold_date_registry(train_artifact)
    except (AttributeError, KeyError, TypeError, ValueError):
        return _empty_review(
            train_artifact,
            parent_attribution,
            parent_research_identity=parent_research_identity,
            status="LINEAGE_INVALID",
        )

    observations: dict[PlanIdentity, object] = {}
    try:
        for observation in research.observations:
            identity = _observation_identity(observation)
            if identity in observations:
                raise ValueError("duplicate parent observation")
            observations[identity] = observation
    except (AttributeError, TypeError, ValueError):
        return _empty_review(
            train_artifact,
            parent_attribution,
            parent_research_identity=parent_research_identity,
            status="LINEAGE_INVALID",
        )

    policies = {value.policy_id: value for value in build_five_day_v3_policies()}
    outcomes: dict[tuple[str, str], tuple[ComponentOutcome, ...]] = {}
    coverages: dict[tuple[str, str], CoverageComparison] = {}
    endpoints_by_unit: dict[tuple[str, str], dict[PlanIdentity, date]] = {}
    train_dates = tuple(train_artifact.split.train)

    for fold_id in ("train-fold-1", "train-fold-2"):
        for policy_id in V3_POLICY_IDS:
            variant = variants[(fold_id, policy_id)]
            scored = variant.get("scored")
            if not isinstance(scored, list):
                return _empty_review(
                    train_artifact,
                    parent_attribution,
                    parent_research_identity=parent_research_identity,
                    status="LINEAGE_INVALID",
                )
            rows: list[ComponentOutcome] = []
            endpoints: dict[PlanIdentity, date] = {}
            without_horizon = 0
            missing_coverage = 0
            for content in scored:
                try:
                    if not isinstance(content, Mapping):
                        raise ValueError
                    identity = _plan_identity(content["plan_key"])
                    if identity[0] not in fold_dates[fold_id]:
                        raise ValueError("scored plan outside fold")
                    observation = observations.get(identity)
                    if observation is None:
                        raise ValueError("scored plan has no observation")
                    endpoint = fifth_subsequent_train_date(
                        identity[0], train_dates
                    )
                    if endpoint is None:
                        without_horizon += 1
                        continue
                    endpoints[identity] = endpoint
                    try:
                        attributed = attribute_interval(
                            identity[1], identity[0], endpoint, market_panel
                        )
                    except ValueError:
                        missing_coverage += 1
                        continue
                    evidence = content["evidence"]
                    feature = content["feature_adjustment"]
                    if not isinstance(evidence, Mapping) or not isinstance(
                        feature, Mapping
                    ):
                        raise ValueError
                    components = reconstruct_score_components(
                        edge=Decimal(str(evidence["edge"])),
                        consistency=Decimal(str(content["consistency"])),
                        feature_adjustment=Decimal(str(feature["total"])),
                        downside=Decimal(str(content["downside"])),
                        policy=policies[policy_id],
                        persisted_score=Decimal(str(content["score"])),
                    )
                    rank = content["rank"]
                    if type(rank) is not int:
                        raise ValueError("invalid official rank")
                    rows.append(
                        ComponentOutcome(
                            signal_date=identity[0],
                            plan_identity=identity,
                            profile_id=identity[3],
                            setup_quality=observation.plan.candidate.setup.quality,
                            full_edge=Decimal(str(evidence["full_edge"])),
                            recent_edge=Decimal(str(evidence["recent_edge"])),
                            raw_downside=Decimal(str(content["downside"])),
                            official_rank=rank,
                            components=components,
                            value=attributed,
                        )
                    )
                except (ArithmeticError, KeyError, TypeError, ValueError):
                    return _empty_review(
                        train_artifact,
                        parent_attribution,
                        parent_research_identity=parent_research_identity,
                        status="SCORE_RECONSTRUCTION_FAILED",
                    )
            if missing_coverage:
                return _empty_review(
                    train_artifact,
                    parent_attribution,
                    parent_research_identity=parent_research_identity,
                    status="MARKET_DATA_INCOMPLETE",
                )
            frozen_rows = tuple(rows)
            fingerprint = _population_fingerprint(frozen_rows, endpoints)
            unit = (fold_id, policy_id)
            outcomes[unit] = frozen_rows
            endpoints_by_unit[unit] = endpoints
            coverages[unit] = CoverageComparison(
                candidate_rows=len(scored),
                eligible_outcomes=len(frozen_rows),
                excluded_without_train_horizon=without_horizon,
                excluded_missing_coverage=missing_coverage,
                population_fingerprint=fingerprint,
                benchmark_fingerprint=parent_attribution.market_data_fingerprint,
            )

    fold_experiments: list[FoldExperimentReview] = []
    fold_correlations: list[ComponentCorrelationReview] = []
    experiment_registry: dict[tuple[str, str, str], FoldExperimentReview] = {}
    for fold_id in ("train-fold-1", "train-fold-2"):
        for policy_id in V3_POLICY_IDS:
            unit = (fold_id, policy_id)
            fold_correlations.append(
                ComponentCorrelationReview(
                    fold_id=fold_id,
                    policy_id=policy_id,
                    population_fingerprint=coverages[unit].population_fingerprint,
                    metrics=summarize_component_correlations(outcomes[unit]),
                )
            )
            for experiment_id in EXPERIMENT_IDS:
                try:
                    ranking = rank_component_experiment(
                        outcomes[unit], experiment_id
                    )
                except ValueError:
                    return _empty_review(
                        train_artifact,
                        parent_attribution,
                        parent_research_identity=parent_research_identity,
                        status=(
                            "BASELINE_REPRODUCTION_FAILED"
                            if experiment_id == "BASELINE"
                            else "COMPARABILITY_FAILED"
                        ),
                    )
                review = FoldExperimentReview(
                    fold_id=fold_id,
                    policy_id=policy_id,
                    experiment_id=experiment_id,
                    coverage=coverages[unit],
                    metrics=summarize_experiment_ranking(ranking),
                    status=(
                        "BOUNDARY_TIE_INCONCLUSIVE"
                        if ranking.boundary_ties
                        else "COMPLETE"
                    ),
                )
                fold_experiments.append(review)
                experiment_registry[(fold_id, policy_id, experiment_id)] = review

    combined_experiments: list[FoldExperimentReview] = []
    combined_correlations: list[ComponentCorrelationReview] = []
    effects: list[PolicyComponentEffect] = []
    component_experiment = {
        "CONSISTENCY": "WITHOUT_CONSISTENCY",
        "STRUCTURE": "WITHOUT_STRUCTURE",
        "DOWNSIDE": "WITHOUT_DOWNSIDE",
    }
    for policy_id in V3_POLICY_IDS:
        left_unit = ("train-fold-1", policy_id)
        right_unit = ("train-fold-2", policy_id)
        combined_rows = outcomes[left_unit] + outcomes[right_unit]
        combined_endpoints = {
            **endpoints_by_unit[left_unit],
            **endpoints_by_unit[right_unit],
        }
        combined_fingerprint = _population_fingerprint(
            combined_rows, combined_endpoints
        )
        coverage = _combined_coverage(
            coverages[left_unit],
            coverages[right_unit],
            combined_fingerprint,
        )
        combined_correlations.append(
            ComponentCorrelationReview(
                fold_id="train-combined",
                policy_id=policy_id,
                population_fingerprint=combined_fingerprint,
                metrics=summarize_component_correlations(combined_rows),
            )
        )
        for experiment_id in EXPERIMENT_IDS:
            ranking = rank_component_experiment(combined_rows, experiment_id)
            combined_experiments.append(
                FoldExperimentReview(
                    fold_id="train-combined",
                    policy_id=policy_id,
                    experiment_id=experiment_id,
                    coverage=coverage,
                    metrics=summarize_experiment_ranking(ranking),
                    status=(
                        "BOUNDARY_TIE_INCONCLUSIVE"
                        if ranking.boundary_ties
                        else "COMPLETE"
                    ),
                )
            )
        for component_id, experiment_id in component_experiment.items():
            try:
                fold1 = compare_ablation(
                    experiment_registry[("train-fold-1", policy_id, "BASELINE")].metrics,
                    experiment_registry[("train-fold-1", policy_id, experiment_id)].metrics,
                )
                fold2 = compare_ablation(
                    experiment_registry[("train-fold-2", policy_id, "BASELINE")].metrics,
                    experiment_registry[("train-fold-2", policy_id, experiment_id)].metrics,
                )
            except ValueError:
                return _empty_review(
                    train_artifact,
                    parent_attribution,
                    parent_research_identity=parent_research_identity,
                    status="COMPARABILITY_FAILED",
                )
            effect = classify_component_effect(
                fold1, fold2, component_id=component_id
            )
            effects.append(
                PolicyComponentEffect(
                    policy_id=policy_id,
                    component_id=component_id,
                    fold1=fold1,
                    fold2=fold2,
                    label=effect.label,
                )
            )

    return FiveDayRankingV3ComponentAttributionReview(
        schema=COMPONENT_ATTRIBUTION_SCHEMA,
        component_attribution_version=COMPONENT_ATTRIBUTION_VERSION,
        parent_train_identity=train_artifact.artifact_identity,
        parent_research_identity=parent_research_identity,
        parent_input_fingerprint=research.input_fingerprint,
        parent_attribution_identity=parent_attribution.artifact_identity,
        market_data_fingerprint=parent_attribution.market_data_fingerprint,
        train_split_identity=_canonical_hash(train_artifact.payload["split"]),
        fold_experiments=tuple(fold_experiments),
        combined_experiments=tuple(combined_experiments),
        fold_component_correlations=tuple(fold_correlations),
        combined_component_correlations=tuple(combined_correlations),
        component_effects=tuple(effects),
        status="COMPLETE",
        train_only=True,
        validation_outcomes_read=False,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )
