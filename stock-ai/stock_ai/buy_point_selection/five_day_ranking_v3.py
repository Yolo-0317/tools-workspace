"""Hierarchical confidence scores for five-day ranking V3 research."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json

from .five_day_ranking_v3_evidence import V3CandidateEvidence
from .five_day_ranking_v3_features import (
    V3_FEATURE_NAMES,
    V3_FEATURE_VERSION,
    V3FeatureAdjustment,
)
from .five_day_return_profiles import resolve_profile_stop
from .five_day_return_runtime import FiveDaySignalPlan


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
