"""Outcome evaluation and freezing for threshold-shadow research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from collections import Counter
import hashlib
import json
from typing import Collection, Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .case_review import CaseCandidate, CaseOutcome, evaluate_case_plan
from .execution import ExecutionCosts
from .models import BuyPointBar
from .threshold_shadow_research import (
    ThresholdProfile,
    ThresholdShadowCandidate,
    profile_matrix_hash as compute_profile_matrix_hash,
)


@dataclass(frozen=True)
class ThresholdShadowOutcome:
    profile_id: str
    code: str
    signal_date: date
    outcome: CaseOutcome
    executable_shares: int = 0


@dataclass(frozen=True)
class ThresholdProfileMetrics:
    profile_id: str
    candidate_count: int
    triggered: int
    resolved: int
    positive_net: int
    stop_first: int
    mean_net_return: Decimal | None
    median_net_return: Decimal | None
    positive_net_rate: Decimal | None
    stop_first_rate: Decimal | None
    mean_mfe: Decimal | None
    mean_mae: Decimal | None
    qualifies: bool
    qualification_reasons: tuple[str, ...]


@dataclass(frozen=True)
class FrozenThresholdProfile:
    profile_id: str
    rank: int
    training_metrics: ThresholdProfileMetrics


@dataclass(frozen=True)
class ThresholdProfileFreeze:
    schema: str
    training_identities: tuple[str, str]
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    profiles: tuple[FrozenThresholdProfile, ...]
    empty: bool
    risk_coverage_complete: bool
    promotion_eligible: bool
    freeze_hash: str


@dataclass(frozen=True)
class ExactRecallComparison:
    actionable_winner_pairs: int
    formal_captured_pairs: int
    shadow_captured_pairs: int
    incremental_captured_pairs: int
    selected_non_winner_pairs: int


def evaluate_threshold_outcomes(
    candidates: Sequence[ThresholdShadowCandidate],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    *,
    outcome_cutoff: date,
    costs: ExecutionCosts | None = None,
) -> tuple[ThresholdShadowOutcome, ...]:
    rows = []
    for candidate in candidates:
        if candidate.executable_shares != 0:
            raise ValueError("shadow candidate must be zero-share")
        adapted = CaseCandidate(
            candidate.code,
            candidate.signal_date,
            candidate.shadow_setup.setup,
            candidate.plan,
            "THRESHOLD_SHADOW",
            candidate.profile_id,
            (
                candidate.shadow_setup.actual_deviation,
                candidate.code,
            ),
        )
        outcome = evaluate_case_plan(
            adapted,
            bars_by_code.get(candidate.code, ()),
            outcome_cutoff=outcome_cutoff,
            costs=costs,
        )
        rows.append(
            ThresholdShadowOutcome(
                candidate.profile_id,
                candidate.code,
                candidate.signal_date,
                outcome,
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda value: (
                value.signal_date,
                value.code,
                value.profile_id,
            ),
        )
    )


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = tuple(sorted(values))
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def aggregate_profile_metrics(
    candidate_profile_ids: Sequence[str],
    outcomes: Sequence[ThresholdShadowOutcome],
) -> tuple[ThresholdProfileMetrics, ...]:
    candidate_counts = Counter(candidate_profile_ids)
    outcome_by_profile: dict[str, list[ThresholdShadowOutcome]] = {}
    for row in outcomes:
        outcome_by_profile.setdefault(row.profile_id, []).append(row)
    profile_ids = sorted(set(candidate_counts) | set(outcome_by_profile))
    metrics = []
    for profile_id in profile_ids:
        rows = outcome_by_profile.get(profile_id, [])
        triggered = [value for value in rows if value.outcome.trigger_date is not None]
        resolved = [
            value for value in triggered if value.outcome.net_return is not None
        ]
        net_returns = [
            value.outcome.net_return
            for value in resolved
            if value.outcome.net_return is not None
        ]
        positive = sum(value > 0 for value in net_returns)
        stopped = sum(value.outcome.stop_first for value in resolved)
        resolved_count = len(resolved)
        mean_net = _mean(net_returns)
        positive_rate = (
            Decimal(positive) / Decimal(resolved_count)
            if resolved_count
            else None
        )
        stop_rate = (
            Decimal(stopped) / Decimal(resolved_count)
            if resolved_count
            else None
        )
        reasons = []
        if resolved_count < 10:
            reasons.append("MINIMUM_RESOLVED_TRIGGERED")
        if mean_net is None or mean_net <= 0:
            reasons.append("MEAN_NET_RETURN_NOT_POSITIVE")
        if positive_rate is None or positive_rate < Decimal("0.50"):
            reasons.append("POSITIVE_NET_RATE_BELOW_HALF")
        if stop_rate is None or stop_rate > Decimal("0.40"):
            reasons.append("STOP_FIRST_RATE_ABOVE_40_PERCENT")
        metrics.append(
            ThresholdProfileMetrics(
                profile_id,
                candidate_counts.get(profile_id, 0),
                len(triggered),
                resolved_count,
                positive,
                stopped,
                mean_net,
                _median(net_returns),
                positive_rate,
                stop_rate,
                _mean(
                    [
                        value.outcome.mfe
                        for value in resolved
                        if value.outcome.mfe is not None
                    ]
                ),
                _mean(
                    [
                        value.outcome.mae
                        for value in resolved
                        if value.outcome.mae is not None
                    ]
                ),
                not reasons,
                tuple(reasons),
            )
        )
    return tuple(metrics)


def _metrics_payload(value: ThresholdProfileMetrics) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "candidate_count": value.candidate_count,
        "triggered": value.triggered,
        "resolved": value.resolved,
        "positive_net": value.positive_net,
        "stop_first": value.stop_first,
        "mean_net_return": None if value.mean_net_return is None else str(value.mean_net_return),
        "median_net_return": None if value.median_net_return is None else str(value.median_net_return),
        "positive_net_rate": None if value.positive_net_rate is None else str(value.positive_net_rate),
        "stop_first_rate": None if value.stop_first_rate is None else str(value.stop_first_rate),
        "mean_mfe": None if value.mean_mfe is None else str(value.mean_mfe),
        "mean_mae": None if value.mean_mae is None else str(value.mean_mae),
        "qualifies": value.qualifies,
        "qualification_reasons": list(value.qualification_reasons),
    }


def _calculate_freeze_hash(
    *,
    training_identities: Sequence[str],
    formal_rule_version: str,
    formal_policy_hash: str,
    profile_matrix_hash: str,
    profiles: Sequence[FrozenThresholdProfile],
    risk_coverage_complete: bool,
) -> str:
    payload = {
        "schema": "buy-point-threshold-shadow-v1",
        "training_identities": list(training_identities),
        "formal_rule_version": formal_rule_version,
        "formal_policy_hash": formal_policy_hash,
        "profile_matrix_hash": profile_matrix_hash,
        "profiles": [
            {
                "profile_id": value.profile_id,
                "rank": value.rank,
                "training_metrics": _metrics_payload(value.training_metrics),
            }
            for value in profiles
        ],
        "empty": not profiles,
        "risk_coverage_complete": risk_coverage_complete,
        "promotion_eligible": False,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def freeze_threshold_profiles(
    *,
    profiles: Sequence[ThresholdProfile],
    training_identities: Sequence[str],
    metrics: Sequence[ThresholdProfileMetrics],
    formal_rule_version: str,
    formal_policy_hash: str,
    profile_matrix_hash: str,
    risk_coverage_complete: bool,
) -> ThresholdProfileFreeze:
    identities = tuple(sorted(training_identities))
    if len(identities) != 2 or len(set(identities)) != 2:
        raise ValueError("freeze requires two distinct research identities")
    expected_matrix_hash = compute_profile_matrix_hash(tuple(profiles))
    if profile_matrix_hash != expected_matrix_hash:
        raise ValueError("profile matrix hash mismatch")
    profile_by_id = {value.profile_id: value for value in profiles}
    if any(value.profile_id not in profile_by_id for value in metrics):
        raise ValueError("metrics contain unsupported threshold profile")
    qualifying = [value for value in metrics if value.qualifies]
    qualifying.sort(
        key=lambda value: (
            -(
                value.mean_net_return
                if value.mean_net_return is not None
                else Decimal("-Infinity")
            ),
            -(
                value.positive_net_rate
                if value.positive_net_rate is not None
                else Decimal("-Infinity")
            ),
            (
                value.stop_first_rate
                if value.stop_first_rate is not None
                else Decimal("Infinity")
            ),
            profile_by_id[value.profile_id].relaxation_rate,
            value.profile_id,
        )
    )
    frozen_profiles = tuple(
        FrozenThresholdProfile(value.profile_id, index, value)
        for index, value in enumerate(qualifying, start=1)
    )
    freeze_hash = _calculate_freeze_hash(
        training_identities=identities,
        formal_rule_version=formal_rule_version,
        formal_policy_hash=formal_policy_hash,
        profile_matrix_hash=profile_matrix_hash,
        profiles=frozen_profiles,
        risk_coverage_complete=risk_coverage_complete,
    )
    return ThresholdProfileFreeze(
        "buy-point-threshold-shadow-v1",
        identities,
        formal_rule_version,
        formal_policy_hash,
        profile_matrix_hash,
        frozen_profiles,
        not frozen_profiles,
        risk_coverage_complete,
        False,
        freeze_hash,
    )


def validate_threshold_freeze(value: ThresholdProfileFreeze) -> None:
    if (
        value.schema != "buy-point-threshold-shadow-v1"
        or len(value.training_identities) != 2
        or tuple(sorted(set(value.training_identities)))
        != value.training_identities
        or value.empty != (not value.profiles)
        or value.promotion_eligible
        or tuple(item.rank for item in value.profiles)
        != tuple(range(1, len(value.profiles) + 1))
        or any(not item.training_metrics.qualifies for item in value.profiles)
    ):
        raise ValueError("freeze model mismatch")
    expected = _calculate_freeze_hash(
        training_identities=value.training_identities,
        formal_rule_version=value.formal_rule_version,
        formal_policy_hash=value.formal_policy_hash,
        profile_matrix_hash=value.profile_matrix_hash,
        profiles=value.profiles,
        risk_coverage_complete=value.risk_coverage_complete,
    )
    if value.freeze_hash != expected:
        raise ValueError("frozen profile hash mismatch")


def select_frozen_daily_candidates(
    candidates: Sequence[ThresholdShadowCandidate],
    freeze: ThresholdProfileFreeze,
    *,
    maximum_per_date: int = 5,
) -> tuple[ThresholdShadowCandidate, ...]:
    validate_threshold_freeze(freeze)
    if maximum_per_date < 1:
        raise ValueError("maximum_per_date must be positive")
    rank_by_profile = {
        value.profile_id: value.rank for value in freeze.profiles
    }
    eligible = [
        value
        for value in candidates
        if value.profile_id in rank_by_profile
    ]
    if any(value.executable_shares != 0 for value in eligible):
        raise ValueError("shadow candidate must be zero-share")
    deduplicated: dict[tuple[date, str], ThresholdShadowCandidate] = {}
    for candidate in sorted(
        eligible,
        key=lambda value: (
            value.signal_date,
            normalize_code6(value.code),
            value.shadow_setup.profile.relaxation_rate,
            value.shadow_setup.actual_deviation,
            -value.shadow_setup.setup.quality,
            value.profile_id,
        ),
    ):
        deduplicated.setdefault(
            (candidate.signal_date, normalize_code6(candidate.code)),
            candidate,
        )
    by_date: dict[date, list[ThresholdShadowCandidate]] = {}
    for candidate in deduplicated.values():
        by_date.setdefault(candidate.signal_date, []).append(candidate)
    selected = []
    for signal_date in sorted(by_date):
        ranked = sorted(
            by_date[signal_date],
            key=lambda value: (
                rank_by_profile[value.profile_id],
                value.shadow_setup.profile.relaxation_rate,
                value.shadow_setup.actual_deviation,
                -value.shadow_setup.setup.quality,
                -value.two_r_space_buffer,
                normalize_code6(value.code),
            ),
        )
        selected.extend(ranked[:maximum_per_date])
    return tuple(selected)


def compare_exact_recall(
    selected: Sequence[ThresholdShadowCandidate],
    winner_keys: Collection[tuple[date, str]],
    formal_keys: Collection[tuple[date, str]],
) -> ExactRecallComparison:
    winners = {
        (signal_date, normalize_code6(code))
        for signal_date, code in winner_keys
    }
    formal = {
        (signal_date, normalize_code6(code))
        for signal_date, code in formal_keys
    }
    shadow = {
        (value.signal_date, normalize_code6(value.code))
        for value in selected
    }
    return ExactRecallComparison(
        len(winners),
        len(winners & formal),
        len(winners & shadow),
        len((winners & shadow) - formal),
        len(shadow - winners),
    )
