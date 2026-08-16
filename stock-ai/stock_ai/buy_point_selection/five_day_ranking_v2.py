"""Conservative point-in-time ranking policies for five-day research."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import TYPE_CHECKING, Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .five_day_return_runtime import FiveDayResearchReview, FiveDaySignalPlan
from .five_day_return_validation import (
    FiveDayCalibration,
    FiveDayObservation,
    FiveDayRankedPlan,
    FiveDayRanking,
    FiveDaySelectedSegment,
    FiveDaySelection,
    _active_structure_key,
    _is_resolved,
    admit_five_day_ranking,
    build_five_day_calibrations,
    evaluate_five_day_selection_segment,
    resolve_five_day_calibration,
)
from .models import SetupType
from .validation import ChronologicalSplit

if TYPE_CHECKING:
    from .five_day_ranking_v2_report import FiveDayRankingV2TrainArtifact


V2_RANKING_VERSION = "five-day-ranking-key-v2"
V2_TRAIN_SCHEMA = "five-day-ranking-v2-train-v1"
V2_POLICY_IDS = (
    "EDGE-K30-BASE",
    "EDGE-K30-STABLE_NEGATIVE",
    "EDGE-K60-BASE",
    "EDGE-K60-STABLE_NEGATIVE",
    "BALANCED-K30-BASE",
    "BALANCED-K30-STABLE_NEGATIVE",
    "BALANCED-K60-BASE",
    "BALANCED-K60-STABLE_NEGATIVE",
    "DOWNSIDE-K30-BASE",
    "DOWNSIDE-K30-STABLE_NEGATIVE",
    "DOWNSIDE-K60-BASE",
    "DOWNSIDE-K60-STABLE_NEGATIVE",
)


@dataclass(frozen=True)
class V2Weights:
    edge: int
    wilson: int
    positive_windows: int
    low_mae: int
    low_stop_rate: int
    context: int
    setup_quality: int

    def __post_init__(self) -> None:
        if sum(self.as_tuple()) != 100:
            raise ValueError("weights must sum to 100")

    def as_tuple(self) -> tuple[int, ...]:
        return (
            self.edge,
            self.wilson,
            self.positive_windows,
            self.low_mae,
            self.low_stop_rate,
            self.context,
            self.setup_quality,
        )


@dataclass(frozen=True)
class FiveDayV2Policy:
    policy_id: str
    ranking_version: str
    shrinkage_k: int
    gate_mode: str
    weights: V2Weights

    def __post_init__(self) -> None:
        if self.shrinkage_k not in (30, 60):
            raise ValueError("shrinkage_k must be 30 or 60")
        if self.gate_mode not in ("BASE", "STABLE_NEGATIVE"):
            raise ValueError("unsupported gate mode")


@dataclass(frozen=True)
class V2ScoreComponents:
    edge: Decimal
    wilson: Decimal
    positive_windows: Decimal
    low_mae: Decimal
    low_stop_rate: Decimal
    context: Decimal
    setup_quality: Decimal


@dataclass(frozen=True)
class FiveDayV2ScoredPlan:
    plan: FiveDaySignalPlan
    calibration: FiveDayCalibration
    shrunk_edge: Decimal
    components: V2ScoreComponents
    score: Decimal
    rank: int
    selected: bool


@dataclass(frozen=True)
class FiveDayV2RankingResult:
    policy: FiveDayV2Policy
    ranking: FiveDayRanking
    scored: tuple[FiveDayV2ScoredPlan, ...]


@dataclass(frozen=True)
class V2RankBandMetrics:
    band: str
    triggered_completed: int
    net_expectancy: Decimal


@dataclass(frozen=True)
class V2MonotonicityAssessment:
    bands: tuple[V2RankBandMetrics, ...]
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FiveDayV2PolicyAssessment:
    policy: FiveDayV2Policy
    fold1: FiveDaySelectedSegment
    fold2: FiveDaySelectedSegment
    combined: FiveDaySelectedSegment
    monotonicity: V2MonotonicityAssessment
    worst_fold_expectancy: Decimal
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FiveDayV2Fold:
    fold_id: str
    calibration_dates: tuple[date, ...]
    evaluation_dates: tuple[date, ...]
    calibration_data_end: date
    excluded_unresolved_calibration_rows: int


@dataclass(frozen=True)
class FiveDayV2VariantReview:
    fold_id: str
    policy_id: str
    daily_limit: int
    scored: tuple[FiveDayV2ScoredPlan, ...]
    segment: FiveDaySelectedSegment


@dataclass(frozen=True)
class FiveDayRankingV2TrainReview:
    schema: str
    ranking_version: str
    parent_research_identity: str
    parent_input_fingerprint: str
    split: ChronologicalSplit
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    sizing_version: str
    evaluator_version: str
    cost_version: str
    policy_set_hash: str
    policies: tuple[FiveDayV2Policy, ...]
    folds: tuple[FiveDayV2Fold, ...]
    variants: tuple[FiveDayV2VariantReview, ...]
    assessments: tuple[FiveDayV2PolicyAssessment, ...]
    winner_policy_id: str | None
    winner_policy_hash: str | None
    winner_train_samples: int
    status: str
    validation_eligible: bool
    validation_outcomes_read: bool
    test_outcomes_read: bool
    promotion_eligible: bool
    trade_permission: str


@dataclass(frozen=True)
class FiveDayRankingV2ValidationReview:
    schema: str
    trial_identity: str
    parent_train_identity: str
    parent_research_identity: str
    parent_input_fingerprint: str
    winner_policy_id: str
    winner_policy_hash: str
    validation_dates: tuple[date, ...]
    segment: FiveDaySelectedSegment
    qualifies_for_test_design: bool
    reasons: tuple[str, ...]
    validation_outcomes_read: bool
    test_outcomes_read: bool
    promotion_eligible: bool
    trade_permission: str


def build_five_day_v2_policies() -> tuple[FiveDayV2Policy, ...]:
    """Return the preregistered policies in their frozen identity order."""
    templates = (
        ("EDGE", V2Weights(35, 20, 15, 10, 10, 5, 5)),
        ("BALANCED", V2Weights(25, 20, 15, 15, 15, 5, 5)),
        ("DOWNSIDE", V2Weights(20, 20, 10, 20, 20, 5, 5)),
    )
    return tuple(
        FiveDayV2Policy(
            policy_id=f"{name}-K{shrinkage_k}-{gate_mode}",
            ranking_version=V2_RANKING_VERSION,
            shrinkage_k=shrinkage_k,
            gate_mode=gate_mode,
            weights=weights,
        )
        for name, weights in templates
        for shrinkage_k in (30, 60)
        for gate_mode in ("BASE", "STABLE_NEGATIVE")
    )


def _policy_payload(policy: FiveDayV2Policy) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "ranking_version": policy.ranking_version,
        "shrinkage_k": policy.shrinkage_k,
        "gate_mode": policy.gate_mode,
        "weights": dict(
            zip(
                (
                    "edge",
                    "wilson",
                    "positive_windows",
                    "low_mae",
                    "low_stop_rate",
                    "context",
                    "setup_quality",
                ),
                policy.weights.as_tuple(),
                strict=True,
            )
        ),
    }


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def five_day_v2_policy_hash(policy: FiveDayV2Policy) -> str:
    """Hash one complete frozen policy definition."""
    return _sha256(_policy_payload(policy))


def five_day_v2_policy_set_hash() -> str:
    """Hash the registry together with formula and tie-breaker identities."""
    return _sha256(
        {
            "policies": [
                _policy_payload(value)
                for value in build_five_day_v2_policies()
            ],
            "formula_version": "conservative-percentile-v1",
            "tie_breaker_version": (
                "score-edge-quality-code-profile-v1"
            ),
        }
    )


def shrink_five_day_edge(
    expectancy: Decimal,
    sample_count: int,
    shrinkage_k: int,
) -> Decimal:
    """Shrink a calibration edge toward zero using exact decimal math."""
    if sample_count < 0 or shrinkage_k <= 0:
        raise ValueError("invalid shrinkage inputs")
    return (
        Decimal(sample_count)
        / Decimal(sample_count + shrinkage_k)
        * expectancy
    )


def relative_percentiles(
    values: Sequence[Decimal],
    *,
    higher_is_better: bool,
) -> tuple[Decimal, ...]:
    """Project values onto deterministic within-date relative percentiles."""
    if not values:
        raise ValueError("percentile input must not be empty")
    if len(values) == 1:
        return (Decimal("0.5"),)
    denominator = Decimal(len(values) - 1)
    return tuple(
        (
            Decimal(sum(other < value for other in values))
            + Decimal(sum(other == value for other in values) - 1)
            * Decimal("0.5")
        )
        / denominator
        if higher_is_better
        else (
            Decimal(sum(other > value for other in values))
            + Decimal(sum(other == value for other in values) - 1)
            * Decimal("0.5")
        )
        / denominator
        for value in values
    )


def five_day_v2_context_score(plan: FiveDaySignalPlan) -> Decimal:
    """Score the three fixed context inputs known at signal time."""
    market = (
        Decimal("1")
        if plan.candidate.market_status == "ALLOW"
        else Decimal("0")
    )
    sector = (
        Decimal("1")
        if plan.candidate.sector_resonating is True
        else Decimal("0")
        if plan.candidate.sector_resonating is False
        else Decimal("0.5")
    )
    resistance = (
        Decimal("1")
        if plan.resistance_basis == "LEVEL_AT_OR_ABOVE_2R"
        else Decimal("0.5")
        if plan.resistance_basis == "NO_RELIABLE_LEVEL"
        else Decimal("0")
    )
    return (market + sector + resistance) / Decimal("3")


def _passes_v2_gate(
    plan: FiveDaySignalPlan,
    calibration: FiveDayCalibration,
    policy: FiveDayV2Policy,
) -> tuple[bool, str | None]:
    edge = shrink_five_day_edge(
        calibration.net_expectancy,
        calibration.triggered_resolved,
        policy.shrinkage_k,
    )
    if edge <= 0:
        return False, "NON_POSITIVE_SHRUNK_EDGE"
    if (
        calibration.profit_factor is None
        or calibration.profit_factor <= Decimal("1")
    ):
        return False, "PROFIT_FACTOR_NOT_ABOVE_ONE"
    if policy.gate_mode == "STABLE_NEGATIVE":
        if plan.candidate.sector_resonating is False:
            return False, "STABLE_NEGATIVE_SECTOR"
        if plan.candidate.setup.setup_type is SetupType.FIRST_LAUNCH_PULLBACK:
            return False, "STABLE_NEGATIVE_SETUP"
    return True, None


def _v2_sort_key(value: FiveDayV2ScoredPlan) -> tuple[object, ...]:
    return (
        -value.score,
        -value.shrunk_edge,
        -value.components.setup_quality,
        normalize_code6(value.plan.candidate.code),
        value.plan.profile.profile_id,
    )


def _score_signal_date(
    rows: Sequence[
        tuple[FiveDaySignalPlan, FiveDayCalibration, Decimal]
    ],
    policy: FiveDayV2Policy,
) -> tuple[FiveDayV2ScoredPlan, ...]:
    raw = tuple(
        (
            edge,
            calibration.profitable_interval[0],
            calibration.positive_window_ratio,
            calibration.mae_p75,
            calibration.stop_rate,
            five_day_v2_context_score(plan),
            Decimal(plan.candidate.setup.quality),
        )
        for plan, calibration, edge in rows
    )
    percentiles = tuple(
        relative_percentiles(
            tuple(value[index] for value in raw),
            higher_is_better=index not in (3, 4),
        )
        for index in range(7)
    )
    weights = policy.weights.as_tuple()
    scored = tuple(
        FiveDayV2ScoredPlan(
            plan=plan,
            calibration=calibration,
            shrunk_edge=edge,
            components=V2ScoreComponents(
                edge=percentiles[0][index],
                wilson=percentiles[1][index],
                positive_windows=percentiles[2][index],
                low_mae=percentiles[3][index],
                low_stop_rate=percentiles[4][index],
                context=percentiles[5][index],
                setup_quality=percentiles[6][index],
            ),
            score=sum(
                (
                    Decimal(weight) * percentiles[component][index]
                    for component, weight in enumerate(weights)
                ),
                Decimal("0"),
            ),
            rank=0,
            selected=False,
        )
        for index, (plan, calibration, edge) in enumerate(rows)
    )
    return tuple(sorted(scored, key=_v2_sort_key))


def rank_five_day_plans_v2(
    plans: Sequence[FiveDaySignalPlan],
    calibrations: Mapping[str, FiveDayCalibration],
    *,
    policy: FiveDayV2Policy,
    active_structure_ids: frozenset[str] = frozenset(),
    daily_limit: int = 3,
) -> FiveDayV2RankingResult:
    """Gate plans and expose a deterministic V2 ranking trace."""
    if daily_limit < 0:
        raise ValueError("daily_limit must not be negative")
    rejections: Counter[str] = Counter()
    eligible_by_date: dict[
        date,
        list[tuple[FiveDaySignalPlan, FiveDayCalibration, Decimal]],
    ] = {}
    for plan in plans:
        if plan.structure_id in active_structure_ids:
            rejections["EXISTING_ACTIVE_STRUCTURE"] += 1
            continue
        calibration = resolve_five_day_calibration(
            calibrations,
            profile_id=plan.profile.profile_id,
            setup_type=plan.candidate.setup.setup_type,
            market_status=plan.candidate.market_status,
            sector_resonating=plan.candidate.sector_resonating,
        )
        if calibration is None:
            rejections["INSUFFICIENT_CALIBRATION"] += 1
            continue
        if calibration.data_end >= plan.candidate.signal_date:
            rejections["CALIBRATION_NOT_POINT_IN_TIME"] += 1
            continue
        edge = shrink_five_day_edge(
            calibration.net_expectancy,
            calibration.triggered_resolved,
            policy.shrinkage_k,
        )
        passed, reason = _passes_v2_gate(plan, calibration, policy)
        if not passed:
            assert reason is not None
            rejections[reason] += 1
            continue
        eligible_by_date.setdefault(
            plan.candidate.signal_date,
            [],
        ).append((plan, calibration, edge))

    selected: list[FiveDaySignalPlan] = []
    traces: list[FiveDayRankedPlan] = []
    scored: list[FiveDayV2ScoredPlan] = []
    for signal_date in sorted(eligible_by_date):
        variants = _score_signal_date(eligible_by_date[signal_date], policy)
        seen_structures: set[tuple[object, ...]] = set()
        structures: list[FiveDayV2ScoredPlan] = []
        for row in variants:
            identity = _active_structure_key(row.plan)
            if identity in seen_structures:
                rejections["DUPLICATE_ACTIVE_STRUCTURE"] += 1
                continue
            seen_structures.add(identity)
            structures.append(row)
        for position, row in enumerate(structures, start=1):
            chosen = position <= daily_limit
            scored.append(replace(row, rank=position, selected=chosen))
            traces.append(
                FiveDayRankedPlan(
                    plan=row.plan,
                    rank=position,
                    selected=chosen,
                )
            )
            if chosen:
                selected.append(row.plan)
        overflow = max(0, len(structures) - daily_limit)
        if overflow:
            rejections["DAILY_CANDIDATE_LIMIT"] += overflow
    return FiveDayV2RankingResult(
        policy=policy,
        ranking=FiveDayRanking(
            plans=tuple(selected),
            rejection_counts=dict(sorted(rejections.items())),
            ranked=tuple(traces),
        ),
        scored=tuple(scored),
    )


def _v2_plan_key(plan: FiveDaySignalPlan) -> tuple[date, str, str, str]:
    return (
        plan.candidate.signal_date,
        normalize_code6(plan.candidate.code),
        plan.structure_id,
        plan.profile.profile_id,
    )


def build_v2_rank_bands(
    scored: Sequence[FiveDayV2ScoredPlan],
    observations: Sequence[FiveDayObservation],
) -> tuple[V2RankBandMetrics, ...]:
    """Summarize resolved triggered observations by diagnostic rank band."""
    by_plan = {
        _v2_plan_key(value.plan): value
        for value in observations
    }
    returns: dict[str, list[Decimal]] = {
        "RANK_1": [],
        "RANK_2_3": [],
        "RANK_4_5": [],
        "RANK_6_PLUS": [],
    }
    for row in scored:
        observation = by_plan.get(_v2_plan_key(row.plan))
        if observation is None or not _is_resolved(observation):
            continue
        assert observation.trade.net_return is not None
        band = (
            "RANK_1"
            if row.rank == 1
            else "RANK_2_3"
            if row.rank <= 3
            else "RANK_4_5"
            if row.rank <= 5
            else "RANK_6_PLUS"
        )
        returns[band].append(observation.trade.net_return)
    return tuple(
        V2RankBandMetrics(
            band=band,
            triggered_completed=len(values),
            net_expectancy=(
                sum(values, Decimal("0")) / Decimal(len(values))
                if values
                else Decimal("0")
            ),
        )
        for band, values in returns.items()
    )


def assess_v2_rank_monotonicity(
    bands: Sequence[V2RankBandMetrics],
    *,
    admitted_top3_expectancy: Decimal,
) -> V2MonotonicityAssessment:
    """Require supported rank bands with no material order inversion."""
    by_band = {value.band: value for value in bands}
    reasons: list[str] = []
    if any(value.triggered_completed < 15 for value in bands):
        reasons.append("RANK_BAND_SAMPLES_TOO_LOW")
    tolerance = Decimal("0.002")
    if (
        by_band["RANK_1"].net_expectancy + tolerance
        < by_band["RANK_2_3"].net_expectancy
    ):
        reasons.append("RANK_1_BELOW_RANK_2_3")
    if (
        by_band["RANK_2_3"].net_expectancy + tolerance
        < by_band["RANK_4_5"].net_expectancy
    ):
        reasons.append("RANK_2_3_BELOW_RANK_4_5")
    if admitted_top3_expectancy <= by_band["RANK_6_PLUS"].net_expectancy:
        reasons.append("TOP3_NOT_ABOVE_RANK6_PLUS")
    return V2MonotonicityAssessment(
        bands=tuple(bands),
        qualifies=not reasons,
        reasons=tuple(reasons),
    )


def assess_five_day_v2_policy(
    *,
    policy: FiveDayV2Policy,
    fold1: FiveDaySelectedSegment,
    fold2: FiveDaySelectedSegment,
    combined: FiveDaySelectedSegment,
    monotonicity: V2MonotonicityAssessment,
) -> FiveDayV2PolicyAssessment:
    """Apply the frozen fold, combined, and rank-evidence thresholds."""
    reasons: list[str] = []
    for label, value in (("FOLD_1", fold1), ("FOLD_2", fold2)):
        if value.selection.incomplete:
            reasons.append(f"{label}_INCOMPLETE")
        if value.metrics.triggered_resolved < 15:
            reasons.append(f"{label}_SAMPLES_TOO_LOW")
        if value.metrics.net_expectancy <= 0:
            reasons.append(f"{label}_NON_POSITIVE_EXPECTANCY")
    if combined.selection.incomplete:
        reasons.append("COMBINED_INCOMPLETE")
    if combined.metrics.triggered_resolved < 40:
        reasons.append("COMBINED_SAMPLES_TOO_LOW")
    if combined.metrics.net_expectancy < Decimal("0.003"):
        reasons.append("COMBINED_EDGE_TOO_LOW")
    if (
        combined.metrics.profit_factor is None
        or combined.metrics.profit_factor <= Decimal("1.10")
    ):
        reasons.append("PROFIT_FACTOR_NOT_ABOVE_1_10")
    reasons.extend(monotonicity.reasons)
    return FiveDayV2PolicyAssessment(
        policy=policy,
        fold1=fold1,
        fold2=fold2,
        combined=combined,
        monotonicity=monotonicity,
        worst_fold_expectancy=min(
            fold1.metrics.net_expectancy,
            fold2.metrics.net_expectancy,
        ),
        qualifies=not reasons,
        reasons=tuple(reasons),
    )


def select_five_day_v2_winner(
    assessments: Sequence[FiveDayV2PolicyAssessment],
) -> FiveDayV2PolicyAssessment | None:
    """Select one qualified policy without an unqualified fallback."""
    qualified = tuple(value for value in assessments if value.qualifies)
    if not qualified:
        return None
    return min(
        qualified,
        key=lambda value: (
            -value.worst_fold_expectancy,
            -value.combined.metrics.net_expectancy,
            -value.combined.metrics.triggered_resolved,
            value.combined.metrics.maximum_drawdown,
            V2_POLICY_IDS.index(value.policy.policy_id),
        ),
    )


def v2_fold_specs(
    train_dates: Sequence[date],
) -> tuple[FiveDayV2Fold, ...]:
    """Build the two frozen expanding train folds."""
    dates = tuple(train_dates)
    if len(dates) != 378:
        raise ValueError("ranking v2 requires exactly 378 train sessions")
    return (
        FiveDayV2Fold(
            fold_id="train-fold-1",
            calibration_dates=dates[:252],
            evaluation_dates=dates[252:315],
            calibration_data_end=dates[251],
            excluded_unresolved_calibration_rows=0,
        ),
        FiveDayV2Fold(
            fold_id="train-fold-2",
            calibration_dates=dates[:315],
            evaluation_dates=dates[315:378],
            calibration_data_end=dates[314],
            excluded_unresolved_calibration_rows=0,
        ),
    )


def combine_v2_selections(
    selections: Sequence[FiveDaySelection],
) -> FiveDaySelection:
    """Combine non-overlapping fold selections without reranking them."""
    ranking_counts: Counter[str] = Counter()
    funnel_counts: Counter[str] = Counter()
    for selection in selections:
        ranking_counts.update(selection.ranking.rejection_counts)
        funnel_counts.update(selection.funnel_counts)
    return FiveDaySelection(
        ranking=FiveDayRanking(
            plans=tuple(
                plan
                for selection in selections
                for plan in selection.ranking.plans
            ),
            rejection_counts=dict(sorted(ranking_counts.items())),
            ranked=tuple(
                row
                for selection in selections
                for row in selection.ranking.ranked
            ),
        ),
        selected_observations=tuple(
            row
            for selection in selections
            for row in selection.selected_observations
        ),
        admitted=tuple(
            row for selection in selections for row in selection.admitted
        ),
        funnel_counts=dict(sorted(funnel_counts.items())),
        incomplete=any(selection.incomplete for selection in selections),
    )


def build_five_day_ranking_v2_train_review(
    research: FiveDayResearchReview,
    *,
    parent_research_identity: str,
) -> FiveDayRankingV2TrainReview:
    """Evaluate every frozen V2 policy using train outcomes only."""
    if len(parent_research_identity) != 64 or any(
        value not in "0123456789abcdef"
        for value in parent_research_identity
    ):
        raise ValueError("parent research identity must be a sha256 digest")
    if not research.point_in_time_complete or research.test_outcomes_read:
        raise ValueError("base research review is incomplete or test-tainted")
    if tuple(
        len(values)
        for values in (
            research.split.train,
            research.split.validation,
            research.split.test,
        )
    ) != (378, 126, 126):
        raise ValueError("ranking v2 requires the 378/126/126 split")

    train_dates = tuple(research.split.train)
    train_set = frozenset(train_dates)
    train_observations = tuple(
        value
        for value in research.observations
        if value.plan.candidate.signal_date in train_set
    )
    folds: list[FiveDayV2Fold] = []
    for base_fold in v2_fold_specs(train_dates):
        calibration_set = frozenset(base_fold.calibration_dates)
        calibration_candidates = tuple(
            value
            for value in train_observations
            if value.plan.candidate.signal_date in calibration_set
        )
        boundary = base_fold.evaluation_dates[0]
        folds.append(
            replace(
                base_fold,
                excluded_unresolved_calibration_rows=sum(
                    not _is_resolved(value)
                    or value.resolution_date >= boundary
                    for value in calibration_candidates
                ),
            )
        )

    policies = build_five_day_v2_policies()
    variants: list[FiveDayV2VariantReview] = []
    for fold in folds:
        calibration_set = frozenset(fold.calibration_dates)
        evaluation_set = frozenset(fold.evaluation_dates)
        boundary = fold.evaluation_dates[0]
        calibration_observations = tuple(
            value
            for value in train_observations
            if value.plan.candidate.signal_date in calibration_set
            and _is_resolved(value)
            and value.resolution_date < boundary
        )
        calibrations = build_five_day_calibrations(
            calibration_observations,
            trading_dates=fold.calibration_dates,
        )
        evaluation_observations = tuple(
            value
            for value in train_observations
            if value.plan.candidate.signal_date in evaluation_set
        )
        plans = tuple(value.plan for value in evaluation_observations)
        for policy in policies:
            for daily_limit in (1, 3, 5):
                ranked = rank_five_day_plans_v2(
                    plans,
                    calibrations,
                    policy=policy,
                    daily_limit=daily_limit,
                )
                selection = admit_five_day_ranking(
                    ranked.ranking,
                    evaluation_observations,
                    capacity=3,
                )
                variants.append(
                    FiveDayV2VariantReview(
                        fold_id=fold.fold_id,
                        policy_id=policy.policy_id,
                        daily_limit=daily_limit,
                        scored=ranked.scored,
                        segment=evaluate_five_day_selection_segment(
                            profile_id="GLOBAL",
                            segment=fold.fold_id,
                            selection=selection,
                            trading_dates=fold.evaluation_dates,
                            cumulative_samples=len(selection.admitted),
                            required_samples=0,
                            required_cumulative_samples=0,
                        ),
                    )
                )

    combined_dates = tuple(
        day for fold in folds for day in fold.evaluation_dates
    )
    for policy in policies:
        for daily_limit in (1, 3, 5):
            fold_values = tuple(
                value
                for value in variants
                if value.policy_id == policy.policy_id
                and value.daily_limit == daily_limit
                and value.fold_id in ("train-fold-1", "train-fold-2")
            )
            combined_selection = combine_v2_selections(
                tuple(value.segment.selection for value in fold_values)
            )
            variants.append(
                FiveDayV2VariantReview(
                    fold_id="train-combined",
                    policy_id=policy.policy_id,
                    daily_limit=daily_limit,
                    scored=tuple(
                        row for value in fold_values for row in value.scored
                    ),
                    segment=evaluate_five_day_selection_segment(
                        profile_id="GLOBAL",
                        segment="train-combined",
                        selection=combined_selection,
                        trading_dates=combined_dates,
                        cumulative_samples=len(combined_selection.admitted),
                        required_samples=0,
                        required_cumulative_samples=0,
                    ),
                )
            )

    assessments: list[FiveDayV2PolicyAssessment] = []
    for policy in policies:
        top3 = {
            value.fold_id: value
            for value in variants
            if value.policy_id == policy.policy_id
            and value.daily_limit == 3
        }
        band_rows = tuple(
            row
            for fold_id in ("train-fold-1", "train-fold-2")
            for row in top3[fold_id].scored
        )
        bands = build_v2_rank_bands(band_rows, train_observations)
        monotonicity = assess_v2_rank_monotonicity(
            bands,
            admitted_top3_expectancy=(
                top3["train-combined"].segment.metrics.net_expectancy
            ),
        )
        assessments.append(
            assess_five_day_v2_policy(
                policy=policy,
                fold1=top3["train-fold-1"].segment,
                fold2=top3["train-fold-2"].segment,
                combined=top3["train-combined"].segment,
                monotonicity=monotonicity,
            )
        )
    winner = select_five_day_v2_winner(assessments)
    return FiveDayRankingV2TrainReview(
        schema=V2_TRAIN_SCHEMA,
        ranking_version=V2_RANKING_VERSION,
        parent_research_identity=parent_research_identity,
        parent_input_fingerprint=research.input_fingerprint,
        split=research.split,
        formal_rule_version=research.formal_rule_version,
        formal_policy_hash=research.formal_policy_hash,
        profile_matrix_hash=research.profile_matrix_hash,
        sizing_version=research.sizing_version,
        evaluator_version=research.evaluator_version,
        cost_version=research.cost_version,
        policy_set_hash=five_day_v2_policy_set_hash(),
        policies=policies,
        folds=tuple(folds),
        variants=tuple(variants),
        assessments=tuple(assessments),
        winner_policy_id=(winner.policy.policy_id if winner else None),
        winner_policy_hash=(
            five_day_v2_policy_hash(winner.policy) if winner else None
        ),
        winner_train_samples=(
            winner.combined.metrics.triggered_resolved if winner else 0
        ),
        status=(
            "TRAIN_CANDIDATE_SELECTED"
            if winner
            else "NO_TRAIN_CANDIDATE"
        ),
        validation_eligible=winner is not None,
        validation_outcomes_read=False,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )


def build_five_day_ranking_v2_validation_review(
    research: FiveDayResearchReview,
    train: "FiveDayRankingV2TrainArtifact",
    *,
    parent_research_identity: str,
) -> FiveDayRankingV2ValidationReview:
    """Reject an unlocked or lineage-mismatched validation attempt."""
    if (
        not train.validation_eligible
        or train.winner_policy_id is None
        or train.winner_policy_hash is None
    ):
        raise ValueError(
            "ranking v2 validation requires a unique train winner"
        )
    policy = next(
        (
            value
            for value in build_five_day_v2_policies()
            if value.policy_id == train.winner_policy_id
        ),
        None,
    )
    split_payload = {
        "train": [value.isoformat() for value in research.split.train],
        "validation": [
            value.isoformat() for value in research.split.validation
        ],
        "test": [value.isoformat() for value in research.split.test],
    }
    if (
        policy is None
        or five_day_v2_policy_hash(policy) != train.winner_policy_hash
        or train.payload["winner_policy_id"] != train.winner_policy_id
        or train.payload["winner_policy_hash"] != train.winner_policy_hash
        or train.payload["validation_eligible"] is not True
        or train.parent_research_identity != parent_research_identity
        or train.payload["parent_research_identity"]
        != parent_research_identity
        or train.parent_input_fingerprint != research.input_fingerprint
        or train.payload["parent_input_fingerprint"]
        != research.input_fingerprint
        or train.payload["split"] != split_payload
        or not research.point_in_time_complete
        or research.test_outcomes_read
    ):
        raise ValueError("ranking v2 winner policy or lineage mismatch")

    validation_start = research.split.validation[0]
    validation_end = research.split.validation[-1]
    train_dates = frozenset(research.split.train)
    validation_dates = frozenset(research.split.validation)
    calibration_rows = tuple(
        value
        for value in research.observations
        if value.plan.candidate.signal_date in train_dates
        and _is_resolved(value)
        and value.resolution_date < validation_start
    )
    calibrations = build_five_day_calibrations(
        calibration_rows,
        trading_dates=research.split.train,
    )
    observations = tuple(
        value
        for value in research.observations
        if value.plan.candidate.signal_date in validation_dates
        and (
            not _is_resolved(value)
            or value.resolution_date <= validation_end
        )
    )
    assert policy is not None
    ranked = rank_five_day_plans_v2(
        tuple(value.plan for value in observations),
        calibrations,
        policy=policy,
        daily_limit=3,
    )
    selection = admit_five_day_ranking(
        ranked.ranking,
        observations,
        capacity=3,
    )
    segment = evaluate_five_day_selection_segment(
        profile_id="GLOBAL",
        segment="validation",
        selection=selection,
        trading_dates=research.split.validation,
        cumulative_samples=(
            train.winner_train_samples + len(selection.admitted)
        ),
        required_samples=30,
        required_cumulative_samples=70,
    )
    reasons = tuple(
        dict.fromkeys((*segment.metrics.reasons, *segment.portfolio.reasons))
    )
    return FiveDayRankingV2ValidationReview(
        schema="five-day-ranking-v2-validation-v1",
        trial_identity=v2_validation_trial_identity(
            train.artifact_identity,
            train.winner_policy_hash,
        ),
        parent_train_identity=train.artifact_identity,
        parent_research_identity=parent_research_identity,
        parent_input_fingerprint=research.input_fingerprint,
        winner_policy_id=policy.policy_id,
        winner_policy_hash=train.winner_policy_hash,
        validation_dates=tuple(research.split.validation),
        segment=segment,
        qualifies_for_test_design=not reasons,
        reasons=reasons,
        validation_outcomes_read=True,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )


def v2_validation_trial_identity(
    train_identity: str,
    winner_policy_hash: str,
) -> str:
    """Derive the one validation-trial identity before reading outcomes."""
    return _sha256(
        {
            "schema": "five-day-ranking-v2-validation-v1",
            "parent_train_identity": train_identity,
            "winner_policy_hash": winner_policy_hash,
        }
    )
