"""Hierarchical confidence scores for five-day ranking V3 research."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import TYPE_CHECKING, Sequence

from stock_ai.market_codes import normalize_code6

from .five_day_ranking_v3_evidence import (
    V3CandidateEvidence,
    V3EvidenceRejected,
    V3EvidenceWindows,
    build_v3_evidence_windows,
    resolve_v3_candidate_evidence,
)
from .five_day_ranking_v3_features import (
    V3_FEATURE_NAMES,
    V3_FEATURE_VERSION,
    V3FeatureAdjustment,
    V3FeatureModel,
    build_v3_feature_model,
    score_v3_feature_adjustment,
)
from .five_day_ranking_v2 import (
    assess_v2_rank_monotonicity,
    build_v2_rank_bands,
    combine_v2_selections,
    v2_fold_specs,
)
from .five_day_return_profiles import resolve_profile_stop
from .five_day_return_runtime import (
    FiveDayResearchReview,
    FiveDaySignalPlan,
)
from .five_day_return_validation import (
    FiveDayObservation,
    FiveDayRankedPlan,
    FiveDayRanking,
    FiveDaySelectedSegment,
    FiveDaySelection,
    _active_structure_key,
    _is_resolved,
    admit_five_day_ranking,
    evaluate_five_day_selection_segment,
)
from .validation import ChronologicalSplit

if TYPE_CHECKING:
    from .five_day_ranking_v3_report import FiveDayRankingV3TrainArtifact


V3_RANKING_VERSION = "five-day-ranking-key-v3"
V3_TRAIN_SCHEMA = "five-day-ranking-v3-train-v1"
V3_VALIDATION_SCHEMA = "five-day-ranking-v3-validation-v1"
V3_SCORE_FORMULA_VERSION = "hierarchical-confidence-edge-v1"
V3_SELECTION_VERSION = "absolute-edge-boundary-margin-v1"
V3_POLICY_IDS = (
    "EDGE-K30",
    "EDGE-K60",
    "CONSISTENCY-K30",
    "CONSISTENCY-K60",
    "STRUCTURE-K30",
    "STRUCTURE-K60",
    "DOWNSIDE-K30",
    "DOWNSIDE-K60",
)
V3_SELECTION_MODES = ("TOP_1", "FORMAL", "TOP_5")


@dataclass(frozen=True)
class FiveDayV3Policy:
    policy_id: str
    shrinkage_k: int
    consistency_weight: Decimal
    structure_weight: Decimal
    downside_weight: Decimal

    def __post_init__(self) -> None:
        if self.shrinkage_k not in (30, 60):
            raise ValueError("shrinkage_k must be 30 or 60")
        weights = (
            self.consistency_weight,
            self.structure_weight,
            self.downside_weight,
        )
        if any(not value.is_finite() or value < 0 for value in weights):
            raise ValueError("policy weights must be finite and non-negative")


@dataclass(frozen=True)
class FiveDayV3ScoredPlan:
    plan: FiveDaySignalPlan
    evidence: V3CandidateEvidence
    feature_adjustment: V3FeatureAdjustment
    consistency: Decimal
    downside: Decimal
    score: Decimal
    rank: int = 0
    selected: bool = False


@dataclass(frozen=True)
class FiveDayV3RankingResult:
    policy: FiveDayV3Policy
    ranking: FiveDayRanking
    scored: tuple[FiveDayV3ScoredPlan, ...]


@dataclass(frozen=True)
class FiveDayV3Fold:
    fold_id: str
    calibration_dates: tuple[date, ...]
    evaluation_dates: tuple[date, ...]
    calibration_data_end: date
    excluded_unresolved_calibration_rows: int


@dataclass(frozen=True)
class FiveDayV3VariantReview:
    fold_id: str
    policy_id: str
    selection_mode: str
    scored: tuple[FiveDayV3ScoredPlan, ...]
    segment: FiveDaySelectedSegment


@dataclass(frozen=True)
class V3RankBandMetrics:
    band: str
    triggered_completed: int
    net_expectancy: Decimal


@dataclass(frozen=True)
class V3MonotonicityAssessment:
    bands: tuple[V3RankBandMetrics, ...]
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FiveDayV3PolicyAssessment:
    policy: FiveDayV3Policy
    fold1: FiveDaySelectedSegment
    fold2: FiveDaySelectedSegment
    combined: FiveDaySelectedSegment
    monotonicity: V3MonotonicityAssessment
    worst_fold_expectancy: Decimal
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FiveDayV3PolicyFingerprint:
    policy_id: str
    selected_structure_keys: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True)
class FiveDayV3FingerprintGroup:
    fingerprint: str
    policy_ids: tuple[str, ...]


@dataclass(frozen=True)
class FiveDayRankingV3TrainReview:
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
    policies: tuple[FiveDayV3Policy, ...]
    folds: tuple[FiveDayV3Fold, ...]
    variants: tuple[FiveDayV3VariantReview, ...]
    assessments: tuple[FiveDayV3PolicyAssessment, ...]
    policy_fingerprints: tuple[FiveDayV3PolicyFingerprint, ...]
    fingerprint_groups: tuple[FiveDayV3FingerprintGroup, ...]
    validation_evidence_windows: V3EvidenceWindows
    validation_feature_model: V3FeatureModel
    validation_excluded_unresolved_train_rows: int
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
class FiveDayRankingV3ValidationReview:
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


def build_five_day_v3_policies() -> tuple[FiveDayV3Policy, ...]:
    """Return the eight preregistered policies in frozen identity order."""
    templates = (
        (
            "EDGE",
            Decimal("0.50"),
            Decimal("0.50"),
            Decimal("0.50"),
        ),
        (
            "CONSISTENCY",
            Decimal("1.00"),
            Decimal("0.50"),
            Decimal("0.50"),
        ),
        (
            "STRUCTURE",
            Decimal("0.50"),
            Decimal("1.00"),
            Decimal("0.50"),
        ),
        (
            "DOWNSIDE",
            Decimal("0.50"),
            Decimal("0.50"),
            Decimal("1.00"),
        ),
    )
    return tuple(
        FiveDayV3Policy(
            policy_id=f"{name}-K{shrinkage_k}",
            shrinkage_k=shrinkage_k,
            consistency_weight=consistency_weight,
            structure_weight=structure_weight,
            downside_weight=downside_weight,
        )
        for (
            name,
            consistency_weight,
            structure_weight,
            downside_weight,
        ) in templates
        for shrinkage_k in (30, 60)
    )


def _policy_payload(policy: FiveDayV3Policy) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "ranking_version": V3_RANKING_VERSION,
        "shrinkage_k": policy.shrinkage_k,
        "weights": {
            "consistency": str(policy.consistency_weight),
            "structure": str(policy.structure_weight),
            "downside": str(policy.downside_weight),
        },
    }


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def five_day_v3_policy_hash(policy: FiveDayV3Policy) -> str:
    """Hash one complete frozen policy definition."""
    return _sha256(_policy_payload(policy))


def _policy_set_payload() -> dict[str, object]:
    return {
        "versions": {
            "ranking": V3_RANKING_VERSION,
            "train_schema": V3_TRAIN_SCHEMA,
            "validation_schema": V3_VALIDATION_SCHEMA,
            "score_formula": V3_SCORE_FORMULA_VERSION,
            "features": V3_FEATURE_VERSION,
            "selection": V3_SELECTION_VERSION,
        },
        "policies": [
            _policy_payload(value) for value in build_five_day_v3_policies()
        ],
        "hierarchy": {
            "levels": ["PROFILE", "SETUP", "MARKET", "SECTOR"],
            "root_prior": "zero",
            "recursive_edge": "n/(n+k)*raw+(1-n/(n+k))*parent",
            "window_blend": (
                "(r_full*E_full+r_recent*E_recent)/(r_full+r_recent)"
            ),
            "recent_sessions": 126,
            "profile_full_samples_minimum": 60,
        },
        "stable_negative": {
            "full_samples_minimum": 60,
            "recent_samples_minimum": 30,
            "requires_parent_and_child": True,
            "edge_maximum": "0",
            "profit_factor_maximum": "1.0",
            "full_wilson_upper_exclusive": "0.50",
        },
        "features": {
            "names": list(V3_FEATURE_NAMES),
            "boundaries": "full_window_quintiles",
            "raw_delta": "bin_edge-profile_setup_parent_edge",
            "shrinkage": "n/(n+k)*raw_delta",
            "window_blend": "reliability_weighted_full_recent",
            "full_bin_samples_minimum": 30,
            "recent_bin_samples_minimum": 15,
            "requires_same_nonzero_sign": True,
            "per_feature_clip": ["-0.001", "0.001"],
            "total_clip": ["-0.003", "0.003"],
        },
        "score": {
            "consistency": "clip(min(E_full,E_recent),-0.001,0.001)",
            "downside": {
                "stop_rate": ["0.01", "0.30"],
                "mae_p75": ["0.10", "0.05"],
                "risk_distance": ["0.05", "0.05"],
                "clip": ["0", "0.003"],
            },
            "formula": "E+wc*C+ws*S-wd*D",
        },
        "selection": {
            "score_floor": "0.001",
            "boundary_margin": "0.001",
            "capacity": 3,
            "no_backfill": True,
            "tie_breakers": [
                "score_desc",
                "base_edge_desc",
                "weakest_window_edge_desc",
                "downside_asc",
                "setup_quality_desc",
                "normalized_code_asc",
                "profile_id_asc",
            ],
        },
        "research_boundaries": {
            "parent_split_sessions": [378, 126, 126],
            "train_folds": [[252, 63], [315, 63]],
            "calibration_resolution_before_evaluation": True,
        },
        "qualification": {
            "distinct_policy_fingerprints_minimum": 4,
            "completed_per_fold_minimum": 15,
            "positive_fold_expectancy": True,
            "combined_completed_minimum": 40,
            "combined_expectancy_minimum": "0.003",
            "combined_profit_factor_exclusive_minimum": "1.10",
            "rank_band_completed_minimum": 15,
            "rank_monotonicity_tolerance": "0.002",
            "formal_beats_rank_6_plus": True,
            "unqualified_fallback": False,
        },
    }


def five_day_v3_policy_set_hash() -> str:
    """Hash the ordered registry and every frozen ranking boundary."""
    return _sha256(_policy_set_payload())


def _clip(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return min(upper, max(lower, value))


def score_five_day_plan_v3(
    plan: FiveDaySignalPlan,
    *,
    evidence: V3CandidateEvidence,
    features: V3FeatureAdjustment,
    policy: FiveDayV3Policy,
) -> FiveDayV3ScoredPlan:
    """Compute one preregistered after-cost risk-adjusted V3 score."""
    if policy not in build_five_day_v3_policies():
        raise ValueError("policy is not in the registered V3 policy set")
    stop = resolve_profile_stop(
        plan.profile,
        plan.reference_entry,
        plan.structure_stop,
    )
    if stop.stop_price is None or stop.risk_fraction is None:
        raise ValueError("profile stop is unresolved")

    consistency = _clip(
        min(evidence.full_edge, evidence.recent_edge),
        Decimal("-0.001"),
        Decimal("0.001"),
    )
    downside = _clip(
        Decimal("0.01")
        * max(evidence.stop_rate - Decimal("0.30"), Decimal("0"))
        + Decimal("0.10")
        * max(evidence.mae_p75 - Decimal("0.05"), Decimal("0"))
        + Decimal("0.05")
        * max(stop.risk_fraction - Decimal("0.05"), Decimal("0")),
        Decimal("0"),
        Decimal("0.003"),
    )
    score = (
        evidence.edge
        + policy.consistency_weight * consistency
        + policy.structure_weight * features.total
        - policy.downside_weight * downside
    )
    return FiveDayV3ScoredPlan(
        plan=plan,
        evidence=evidence,
        feature_adjustment=features,
        consistency=consistency,
        downside=downside,
        score=score,
    )


def _ranking_key(value: FiveDayV3ScoredPlan) -> tuple[object, ...]:
    plan = value.plan
    return (
        -value.score,
        -value.evidence.edge,
        -min(value.evidence.full_edge, value.evidence.recent_edge),
        value.downside,
        -plan.candidate.setup.quality,
        normalize_code6(plan.candidate.code),
        plan.profile.profile_id,
    )


def _profile_stop_rejection_reasons(
    plan: FiveDaySignalPlan,
) -> tuple[str, ...]:
    stop = resolve_profile_stop(
        plan.profile,
        plan.reference_entry,
        plan.structure_stop,
    )
    if stop.stop_price is not None and stop.risk_fraction is not None:
        return ()
    return stop.reasons or ("PROFILE_STOP_UNRESOLVED",)


def rank_five_day_plans_v3(
    plans: Sequence[FiveDaySignalPlan],
    windows: V3EvidenceWindows,
    feature_model: V3FeatureModel,
    *,
    policy: FiveDayV3Policy,
    active_structure_ids: frozenset[str] = frozenset(),
) -> FiveDayV3RankingResult:
    """Rank each signal date with the frozen zero-to-three V3 rule."""
    if policy not in build_five_day_v3_policies():
        raise ValueError("policy is not in the registered V3 policy set")

    rejection_counts: Counter[str] = Counter()
    eligible_by_date: dict[date, list[FiveDayV3ScoredPlan]] = {}
    for plan in plans:
        if plan.structure_id in active_structure_ids:
            rejection_counts["EXISTING_ACTIVE_STRUCTURE"] += 1
            continue
        stop_reasons = _profile_stop_rejection_reasons(plan)
        if stop_reasons:
            rejection_counts.update(stop_reasons)
            continue
        try:
            evidence = resolve_v3_candidate_evidence(
                plan,
                windows,
                shrinkage_k=policy.shrinkage_k,
            )
        except V3EvidenceRejected as error:
            rejection_counts[error.reason] += 1
            continue
        if evidence.stable_negative:
            rejection_counts["STABLE_NEGATIVE"] += 1
            continue
        features = score_v3_feature_adjustment(
            plan,
            feature_model,
            shrinkage_k=policy.shrinkage_k,
        )
        scored = score_five_day_plan_v3(
            plan,
            evidence=evidence,
            features=features,
            policy=policy,
        )
        eligible_by_date.setdefault(
            plan.candidate.signal_date,
            [],
        ).append(scored)

    selected_plans: list[FiveDaySignalPlan] = []
    ranking_trace: list[FiveDayRankedPlan] = []
    scored_trace: list[FiveDayV3ScoredPlan] = []
    for signal_date in sorted(eligible_by_date):
        ranked = sorted(eligible_by_date[signal_date], key=_ranking_key)
        unique: list[FiveDayV3ScoredPlan] = []
        seen_structures: set[tuple[object, ...]] = set()
        for row in ranked:
            identity = _active_structure_key(row.plan)
            if identity in seen_structures:
                rejection_counts["DUPLICATE_ACTIVE_STRUCTURE"] += 1
                continue
            seen_structures.add(identity)
            unique.append(row)

        eligible = [
            row for row in unique if row.score >= Decimal("0.001")
        ]
        rejection_counts["ABSOLUTE_EDGE_TOO_LOW"] += (
            len(unique) - len(eligible)
        )
        count = min(3, len(eligible))
        provisional_count = count
        while count > 1 and count < len(eligible):
            boundary = eligible[count - 1].score - eligible[count].score
            if boundary >= Decimal("0.001"):
                break
            count -= 1
        rejection_counts["BOUNDARY_MARGIN_TOO_LOW"] += (
            provisional_count - count
        )

        for rank, row in enumerate(unique, start=1):
            is_selected = rank <= count
            ranked_row = replace(row, rank=rank, selected=is_selected)
            scored_trace.append(ranked_row)
            ranking_trace.append(
                FiveDayRankedPlan(
                    plan=row.plan,
                    rank=rank,
                    selected=is_selected,
                )
            )
            if is_selected:
                selected_plans.append(row.plan)

    return FiveDayV3RankingResult(
        policy=policy,
        ranking=FiveDayRanking(
            plans=tuple(selected_plans),
            rejection_counts={
                key: value
                for key, value in sorted(rejection_counts.items())
                if value > 0
            },
            ranked=tuple(ranking_trace),
        ),
        scored=tuple(scored_trace),
    )


def _diagnostic_ranking(
    result: FiveDayV3RankingResult,
    *,
    daily_limit: int,
) -> tuple[FiveDayRanking, tuple[FiveDayV3ScoredPlan, ...]]:
    counts = Counter(
        {
            key: value
            for key, value in result.ranking.rejection_counts.items()
            if key
            not in ("ABSOLUTE_EDGE_TOO_LOW", "BOUNDARY_MARGIN_TOO_LOW")
        }
    )
    by_date: dict[date, list[FiveDayV3ScoredPlan]] = {}
    for row in result.scored:
        by_date.setdefault(row.plan.candidate.signal_date, []).append(row)
    selected_plans: list[FiveDaySignalPlan] = []
    ranked: list[FiveDayRankedPlan] = []
    scored: list[FiveDayV3ScoredPlan] = []
    for signal_date in sorted(by_date):
        rows = sorted(by_date[signal_date], key=lambda value: value.rank)
        for row in rows:
            selected = row.rank <= daily_limit
            scored.append(replace(row, selected=selected))
            ranked.append(
                FiveDayRankedPlan(
                    plan=row.plan,
                    rank=row.rank,
                    selected=selected,
                )
            )
            if selected:
                selected_plans.append(row.plan)
        counts["DAILY_CANDIDATE_LIMIT"] += max(
            0,
            len(rows) - daily_limit,
        )
    return (
        FiveDayRanking(
            plans=tuple(selected_plans),
            rejection_counts={
                key: value
                for key, value in sorted(counts.items())
                if value > 0
            },
            ranked=tuple(ranked),
        ),
        tuple(scored),
    )


def _rank_bands(
    scored: Sequence[FiveDayV3ScoredPlan],
    observations: Sequence[FiveDayObservation],
) -> tuple[V3RankBandMetrics, ...]:
    bands = build_v2_rank_bands(scored, observations)
    return tuple(
        V3RankBandMetrics(
            band=value.band,
            triggered_completed=value.triggered_completed,
            net_expectancy=value.net_expectancy,
        )
        for value in bands
    )


def _assess_rank_monotonicity(
    bands: Sequence[V3RankBandMetrics],
    *,
    admitted_expectancy: Decimal,
) -> V3MonotonicityAssessment:
    assessment = assess_v2_rank_monotonicity(
        bands,
        admitted_top3_expectancy=admitted_expectancy,
    )
    return V3MonotonicityAssessment(
        bands=tuple(bands),
        qualifies=assessment.qualifies,
        reasons=assessment.reasons,
    )


def assess_five_day_v3_policy(
    *,
    policy: FiveDayV3Policy,
    fold1: FiveDaySelectedSegment,
    fold2: FiveDaySelectedSegment,
    combined: FiveDaySelectedSegment,
    monotonicity: V3MonotonicityAssessment,
) -> FiveDayV3PolicyAssessment:
    """Apply the unchanged fold, combined, and rank thresholds."""
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
    return FiveDayV3PolicyAssessment(
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


def select_five_day_v3_winner(
    assessments: Sequence[FiveDayV3PolicyAssessment],
) -> FiveDayV3PolicyAssessment | None:
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
            V3_POLICY_IDS.index(value.policy.policy_id),
        ),
    )


def five_day_v3_selection_fingerprint(
    selected_structure_keys: Sequence[str],
) -> str:
    """Hash one ordered two-fold formal selection trace."""
    return _sha256(
        {
            "selection_version": V3_SELECTION_VERSION,
            "selected_structure_keys": list(selected_structure_keys),
        }
    )


def _structure_key_text(plan: FiveDaySignalPlan) -> str:
    setup = plan.candidate.setup
    return "|".join(
        (
            plan.candidate.signal_date.isoformat(),
            normalize_code6(plan.candidate.code),
            setup.setup_type.value,
            setup.structure_start.isoformat(),
            str(setup.structure_high),
            str(setup.structure_low),
        )
    )


def _fingerprint_groups(
    values: Sequence[FiveDayV3PolicyFingerprint],
) -> tuple[FiveDayV3FingerprintGroup, ...]:
    grouped: dict[str, list[str]] = {}
    for value in values:
        grouped.setdefault(value.fingerprint, []).append(value.policy_id)
    return tuple(
        FiveDayV3FingerprintGroup(
            fingerprint=fingerprint,
            policy_ids=tuple(policy_ids),
        )
        for fingerprint, policy_ids in sorted(grouped.items())
        if len(policy_ids) > 1
    )


def finalize_five_day_ranking_v3_train(
    review: FiveDayRankingV3TrainReview,
) -> FiveDayRankingV3TrainReview:
    """Apply policy-family diversity before choosing one train winner."""
    if tuple(value.policy_id for value in review.policies) != V3_POLICY_IDS:
        raise ValueError("ranking v3 review has an invalid policy registry")
    if tuple(
        value.policy.policy_id for value in review.assessments
    ) != V3_POLICY_IDS:
        raise ValueError("ranking v3 review has invalid assessments")
    if tuple(
        value.policy_id for value in review.policy_fingerprints
    ) != V3_POLICY_IDS:
        raise ValueError("ranking v3 review has invalid fingerprints")

    distinct = len(
        {value.fingerprint for value in review.policy_fingerprints}
    )
    groups = _fingerprint_groups(review.policy_fingerprints)
    assessments = review.assessments
    if distinct < 4:
        assessments = tuple(
            replace(
                value,
                qualifies=False,
                reasons=(
                    value.reasons
                    if "POLICY_SET_DEGENERATE" in value.reasons
                    else (*value.reasons, "POLICY_SET_DEGENERATE")
                ),
            )
            for value in assessments
        )
        winner = None
        status = "POLICY_SET_DEGENERATE"
    else:
        winner = select_five_day_v3_winner(assessments)
        status = (
            "TRAIN_CANDIDATE_SELECTED"
            if winner is not None
            else "NO_TRAIN_CANDIDATE"
        )
    return replace(
        review,
        assessments=assessments,
        fingerprint_groups=groups,
        winner_policy_id=(winner.policy.policy_id if winner else None),
        winner_policy_hash=(
            five_day_v3_policy_hash(winner.policy) if winner else None
        ),
        winner_train_samples=(
            winner.combined.metrics.triggered_resolved if winner else 0
        ),
        status=status,
        validation_eligible=winner is not None,
        validation_outcomes_read=False,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )


def _mode_ranking(
    result: FiveDayV3RankingResult,
    selection_mode: str,
) -> tuple[FiveDayRanking, tuple[FiveDayV3ScoredPlan, ...]]:
    if selection_mode == "FORMAL":
        return result.ranking, result.scored
    if selection_mode == "TOP_1":
        return _diagnostic_ranking(result, daily_limit=1)
    if selection_mode == "TOP_5":
        return _diagnostic_ranking(result, daily_limit=5)
    raise ValueError("unsupported V3 selection mode")


def _fold_variants(
    *,
    fold: FiveDayV3Fold,
    calibration_observations: Sequence[FiveDayObservation],
    evaluation_plans: Sequence[FiveDaySignalPlan],
    evaluation_observations: Sequence[FiveDayObservation],
    policies: Sequence[FiveDayV3Policy],
) -> tuple[FiveDayV3VariantReview, ...]:
    windows = build_v3_evidence_windows(
        calibration_observations,
        trading_dates=fold.calibration_dates,
    )
    feature_model = build_v3_feature_model(
        calibration_observations,
        full_dates=fold.calibration_dates,
        recent_dates=fold.calibration_dates[-126:],
    )
    variants: list[FiveDayV3VariantReview] = []
    for policy in policies:
        result = rank_five_day_plans_v3(
            evaluation_plans,
            windows,
            feature_model,
            policy=policy,
        )
        for selection_mode in V3_SELECTION_MODES:
            ranking, scored = _mode_ranking(result, selection_mode)
            selection = admit_five_day_ranking(
                ranking,
                evaluation_observations,
                capacity=3,
            )
            variants.append(
                FiveDayV3VariantReview(
                    fold_id=fold.fold_id,
                    policy_id=policy.policy_id,
                    selection_mode=selection_mode,
                    scored=scored,
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
    return tuple(variants)


def build_five_day_ranking_v3_train_review(
    research: FiveDayResearchReview,
    *,
    parent_research_identity: str,
) -> FiveDayRankingV3TrainReview:
    """Evaluate all V3 policies from train outcomes only."""
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
        raise ValueError("ranking v3 requires the 378/126/126 split")

    train_dates = tuple(research.split.train)
    train_set = frozenset(train_dates)
    train_observations = tuple(
        value
        for value in research.observations
        if value.plan.candidate.signal_date in train_set
    )
    validation_boundary = research.split.validation[0]
    visible_train_observations = tuple(
        value
        for value in train_observations
        if not _is_resolved(value)
        or value.resolution_date < validation_boundary
    )
    folds: list[FiveDayV3Fold] = []
    for base in v2_fold_specs(train_dates):
        calibration_set = frozenset(base.calibration_dates)
        candidates = tuple(
            value
            for value in train_observations
            if value.plan.candidate.signal_date in calibration_set
        )
        boundary = base.evaluation_dates[0]
        folds.append(
            FiveDayV3Fold(
                fold_id=base.fold_id,
                calibration_dates=base.calibration_dates,
                evaluation_dates=base.evaluation_dates,
                calibration_data_end=base.calibration_data_end,
                excluded_unresolved_calibration_rows=sum(
                    not _is_resolved(value)
                    or value.resolution_date >= boundary
                    for value in candidates
                ),
            )
        )

    policies = build_five_day_v3_policies()
    variants: list[FiveDayV3VariantReview] = []
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
            and not _profile_stop_rejection_reasons(value.plan)
        )
        evaluation_observations = tuple(
            value
            for value in train_observations
            if value.plan.candidate.signal_date in evaluation_set
        )
        visible_evaluation_observations = tuple(
            value
            for value in evaluation_observations
            if not _is_resolved(value)
            or value.resolution_date < validation_boundary
        )
        variants.extend(
            _fold_variants(
                fold=fold,
                calibration_observations=calibration_observations,
                evaluation_plans=tuple(
                    value.plan for value in evaluation_observations
                ),
                evaluation_observations=visible_evaluation_observations,
                policies=policies,
            )
        )

    combined_dates = tuple(
        value for fold in folds for value in fold.evaluation_dates
    )
    for policy in policies:
        for selection_mode in V3_SELECTION_MODES:
            fold_values = tuple(
                value
                for value in variants
                if value.policy_id == policy.policy_id
                and value.selection_mode == selection_mode
            )
            combined_selection = combine_v2_selections(
                tuple(value.segment.selection for value in fold_values)
            )
            variants.append(
                FiveDayV3VariantReview(
                    fold_id="train-combined",
                    policy_id=policy.policy_id,
                    selection_mode=selection_mode,
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

    assessments: list[FiveDayV3PolicyAssessment] = []
    fingerprints: list[FiveDayV3PolicyFingerprint] = []
    for policy in policies:
        formal = {
            value.fold_id: value
            for value in variants
            if value.policy_id == policy.policy_id
            and value.selection_mode == "FORMAL"
        }
        fold_scored = tuple(
            row
            for fold_id in ("train-fold-1", "train-fold-2")
            for row in formal[fold_id].scored
        )
        bands = _rank_bands(fold_scored, visible_train_observations)
        monotonicity = _assess_rank_monotonicity(
            bands,
            admitted_expectancy=(
                formal["train-combined"].segment.metrics.net_expectancy
            ),
        )
        assessments.append(
            assess_five_day_v3_policy(
                policy=policy,
                fold1=formal["train-fold-1"].segment,
                fold2=formal["train-fold-2"].segment,
                combined=formal["train-combined"].segment,
                monotonicity=monotonicity,
            )
        )
        selected_keys = tuple(
            _structure_key_text(plan)
            for fold_id in ("train-fold-1", "train-fold-2")
            for plan in formal[fold_id].segment.selection.ranking.plans
        )
        fingerprints.append(
            FiveDayV3PolicyFingerprint(
                policy_id=policy.policy_id,
                selected_structure_keys=selected_keys,
                fingerprint=five_day_v3_selection_fingerprint(selected_keys),
            )
        )

    validation_calibration = tuple(
        value
        for value in train_observations
        if _is_resolved(value) and value.resolution_date < validation_boundary
        and not _profile_stop_rejection_reasons(value.plan)
    )
    validation_windows = build_v3_evidence_windows(
        validation_calibration,
        trading_dates=train_dates,
    )
    validation_feature_model = build_v3_feature_model(
        validation_calibration,
        full_dates=train_dates,
        recent_dates=train_dates[-126:],
    )
    review = FiveDayRankingV3TrainReview(
        schema=V3_TRAIN_SCHEMA,
        ranking_version=V3_RANKING_VERSION,
        parent_research_identity=parent_research_identity,
        parent_input_fingerprint=research.input_fingerprint,
        split=research.split,
        formal_rule_version=research.formal_rule_version,
        formal_policy_hash=research.formal_policy_hash,
        profile_matrix_hash=research.profile_matrix_hash,
        sizing_version=research.sizing_version,
        evaluator_version=research.evaluator_version,
        cost_version=research.cost_version,
        policy_set_hash=five_day_v3_policy_set_hash(),
        policies=policies,
        folds=tuple(folds),
        variants=tuple(variants),
        assessments=tuple(assessments),
        policy_fingerprints=tuple(fingerprints),
        fingerprint_groups=(),
        validation_evidence_windows=validation_windows,
        validation_feature_model=validation_feature_model,
        validation_excluded_unresolved_train_rows=sum(
            not _is_resolved(value)
            or value.resolution_date >= validation_boundary
            for value in train_observations
        ),
        winner_policy_id=None,
        winner_policy_hash=None,
        winner_train_samples=0,
        status="NO_TRAIN_CANDIDATE",
        validation_eligible=False,
        validation_outcomes_read=False,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )
    return finalize_five_day_ranking_v3_train(review)


def _split_payload(split: ChronologicalSplit) -> dict[str, list[str]]:
    return {
        "train": [value.isoformat() for value in split.train],
        "validation": [value.isoformat() for value in split.validation],
        "test": [value.isoformat() for value in split.test],
    }


def _validation_train_is_consistent(
    research: FiveDayResearchReview,
    train: "FiveDayRankingV3TrainArtifact",
    *,
    parent_research_identity: str,
    policy: FiveDayV3Policy | None,
) -> bool:
    try:
        payload = train.payload
        content = {
            key: value
            for key, value in payload.items()
            if key != "artifact_identity"
        }
        train_dates = tuple(research.split.train)
        return (
            policy is not None
            and train.policy_set_hash == five_day_v3_policy_set_hash()
            and payload["schema"] == V3_TRAIN_SCHEMA
            and payload["ranking_version"] == V3_RANKING_VERSION
            and payload["artifact_identity"] == train.artifact_identity
            and train.artifact_identity == _sha256(content)
            and payload["policy_set_hash"] == train.policy_set_hash
            and payload["winner_policy_id"] == train.winner_policy_id
            and payload["winner_policy_hash"] == train.winner_policy_hash
            and payload["winner_train_samples"]
            == train.winner_train_samples
            and payload["status"] == "TRAIN_CANDIDATE_SELECTED"
            and payload["validation_eligible"] is True
            and payload["validation_outcomes_read"] is False
            and payload["test_outcomes_read"] is False
            and payload["promotion_eligible"] is False
            and payload["trade_permission"] == "NO-TRADE"
            and five_day_v3_policy_hash(policy)
            == train.winner_policy_hash
            and train.parent_research_identity
            == parent_research_identity
            and payload["parent_research_identity"]
            == parent_research_identity
            and train.parent_input_fingerprint
            == research.input_fingerprint
            and payload["parent_input_fingerprint"]
            == research.input_fingerprint
            and train.split == research.split
            and payload["split"] == _split_payload(research.split)
            and train.validation_evidence_windows.full_dates == train_dates
            and train.validation_evidence_windows.recent_dates
            == train_dates[-126:]
            and train.validation_feature_model.data_end == train_dates[-1]
            and payload["validation_evidence_windows"]["full_dates"]
            == [value.isoformat() for value in train_dates]
            and payload["validation_evidence_windows"]["recent_dates"]
            == [value.isoformat() for value in train_dates[-126:]]
            and payload["validation_feature_model"]["data_end"]
            == train_dates[-1].isoformat()
            and research.point_in_time_complete
            and not research.test_outcomes_read
        )
    except (KeyError, TypeError, IndexError):
        return False


def build_five_day_ranking_v3_validation_review(
    research: FiveDayResearchReview,
    train: "FiveDayRankingV3TrainArtifact",
    *,
    parent_research_identity: str,
) -> FiveDayRankingV3ValidationReview:
    """Evaluate one locked winner with train-frozen V3 evidence only."""
    if (
        not train.validation_eligible
        or train.winner_policy_id is None
        or train.winner_policy_hash is None
    ):
        raise ValueError(
            "ranking v3 validation requires a unique train winner"
        )
    policy = next(
        (
            value
            for value in build_five_day_v3_policies()
            if value.policy_id == train.winner_policy_id
        ),
        None,
    )
    if not _validation_train_is_consistent(
        research,
        train,
        parent_research_identity=parent_research_identity,
        policy=policy,
    ):
        raise ValueError("ranking v3 winner policy or lineage mismatch")

    validation_dates = frozenset(research.split.validation)
    validation_end = research.split.validation[-1]
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
    ranked = rank_five_day_plans_v3(
        tuple(value.plan for value in observations),
        train.validation_evidence_windows,
        train.validation_feature_model,
        policy=policy,
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
    return FiveDayRankingV3ValidationReview(
        schema=V3_VALIDATION_SCHEMA,
        trial_identity=v3_validation_trial_identity(
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


def v3_validation_trial_identity(
    train_identity: str,
    winner_policy_hash: str,
) -> str:
    """Derive the one V3 validation identity before reading outcomes."""
    return _sha256(
        {
            "schema": V3_VALIDATION_SCHEMA,
            "parent_train_identity": train_identity,
            "winner_policy_hash": winner_policy_hash,
        }
    )
