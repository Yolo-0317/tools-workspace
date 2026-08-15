"""Outcome metrics and retrospective freezing for gate-shadow research."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .case_review import CaseCandidate, CaseOutcome, evaluate_case_plan
from .execution import ExecutionCosts
from .gate_shadow_research import (
    GateShadowCandidate,
    GateShadowProfile,
    gate_profile_matrix_hash as compute_profile_matrix_hash,
    validate_gate_shadow_profiles,
)
from .models import BuyPointBar


@dataclass(frozen=True)
class GateShadowOutcome:
    profile_id: str
    code: str
    signal_date: date
    outcome: CaseOutcome
    executable_shares: int = 0


@dataclass(frozen=True)
class GateProfileMetrics:
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
class FrozenGateProfile:
    profile_id: str
    rank: int
    training_metrics: GateProfileMetrics


@dataclass(frozen=True)
class GateProfileFreeze:
    schema: str
    training_identities: tuple[str, str, str]
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    profiles: tuple[FrozenGateProfile, ...]
    retrospective: bool
    empty: bool
    risk_coverage_complete: bool
    promotion_eligible: bool
    freeze_hash: str


def evaluate_gate_shadow_outcomes(
    candidates: Sequence[GateShadowCandidate],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    *,
    outcome_cutoff: date,
    costs: ExecutionCosts | None = None,
) -> tuple[GateShadowOutcome, ...]:
    rows = []
    for candidate in candidates:
        if candidate.executable_shares != 0 or candidate.hit.executable_shares != 0:
            raise ValueError("gate shadow candidate must be zero-share")
        adapted = CaseCandidate(
            candidate.hit.code,
            candidate.hit.signal_date,
            candidate.hit.setup,
            candidate.plan,
            "GATE_SHADOW",
            candidate.hit.profile.failure_reason,
            (
                -candidate.hit.setup.quality,
                -candidate.two_r_space_buffer,
                -candidate.average_amount5_qian,
                candidate.hit.code,
            ),
        )
        outcome = evaluate_case_plan(
            adapted,
            bars_by_code.get(candidate.hit.code, ()),
            outcome_cutoff=outcome_cutoff,
            costs=costs,
        )
        rows.append(
            GateShadowOutcome(
                candidate.hit.profile.profile_id,
                normalize_code6(candidate.hit.code),
                candidate.hit.signal_date,
                outcome,
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda value: (value.signal_date, value.code, value.profile_id),
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


def aggregate_gate_profile_metrics(
    candidate_profile_ids: Sequence[str],
    outcomes: Sequence[GateShadowOutcome],
) -> tuple[GateProfileMetrics, ...]:
    candidate_counts = Counter(candidate_profile_ids)
    outcome_by_profile: dict[str, list[GateShadowOutcome]] = {}
    for row in outcomes:
        outcome_by_profile.setdefault(row.profile_id, []).append(row)
    metrics = []
    for profile_id in sorted(set(candidate_counts) | set(outcome_by_profile)):
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
        resolved_count = len(resolved)
        positive = sum(value > 0 for value in net_returns)
        stopped = sum(value.outcome.stop_first for value in resolved)
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
        if profile_id.startswith("MARKET:"):
            reasons.append("DIAGNOSTIC_ONLY_MARKET_PROFILE")
        if resolved_count < 10:
            reasons.append("MINIMUM_RESOLVED_TRIGGERED")
        if mean_net is None or mean_net <= 0:
            reasons.append("MEAN_NET_RETURN_NOT_POSITIVE")
        if positive_rate is None or positive_rate < Decimal("0.50"):
            reasons.append("POSITIVE_NET_RATE_BELOW_HALF")
        if stop_rate is None or stop_rate > Decimal("0.40"):
            reasons.append("STOP_FIRST_RATE_ABOVE_40_PERCENT")
        metrics.append(
            GateProfileMetrics(
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


def _metrics_payload(value: GateProfileMetrics) -> dict[str, object]:
    def decimal(item: Decimal | None) -> str | None:
        return None if item is None else str(item)

    return {
        "profile_id": value.profile_id,
        "candidate_count": value.candidate_count,
        "triggered": value.triggered,
        "resolved": value.resolved,
        "positive_net": value.positive_net,
        "stop_first": value.stop_first,
        "mean_net_return": decimal(value.mean_net_return),
        "median_net_return": decimal(value.median_net_return),
        "positive_net_rate": decimal(value.positive_net_rate),
        "stop_first_rate": decimal(value.stop_first_rate),
        "mean_mfe": decimal(value.mean_mfe),
        "mean_mae": decimal(value.mean_mae),
        "qualifies": value.qualifies,
        "qualification_reasons": list(value.qualification_reasons),
    }


def _calculate_freeze_hash(
    *,
    training_identities: Sequence[str],
    formal_rule_version: str,
    formal_policy_hash: str,
    profile_matrix_hash: str,
    profiles: Sequence[FrozenGateProfile],
    risk_coverage_complete: bool,
) -> str:
    payload = {
        "schema": "buy-point-gate-shadow-v1",
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
        "retrospective": True,
        "empty": not profiles,
        "risk_coverage_complete": risk_coverage_complete,
        "promotion_eligible": False,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def freeze_sector_gate_profiles(
    *,
    profiles: Sequence[GateShadowProfile],
    training_identities: Sequence[str],
    metrics: Sequence[GateProfileMetrics],
    formal_rule_version: str,
    formal_policy_hash: str,
    profile_matrix_hash: str,
    risk_coverage_complete: bool,
) -> GateProfileFreeze:
    validate_gate_shadow_profiles(profiles)
    identities = tuple(sorted(training_identities))
    if len(identities) != 3 or len(set(identities)) != 3:
        raise ValueError("freeze requires three distinct research identities")
    if profile_matrix_hash != compute_profile_matrix_hash(profiles):
        raise ValueError("gate profile matrix hash mismatch")
    profile_by_id = {value.profile_id: value for value in profiles}
    if any(value.profile_id not in profile_by_id for value in metrics):
        raise ValueError("metrics contain unsupported gate profile")
    qualifying = [
        value
        for value in metrics
        if value.qualifies and profile_by_id[value.profile_id].freeze_eligible
    ]
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
            value.profile_id,
        )
    )
    frozen_profiles = tuple(
        FrozenGateProfile(value.profile_id, index, value)
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
    return GateProfileFreeze(
        "buy-point-gate-shadow-v1",
        (identities[0], identities[1], identities[2]),
        formal_rule_version,
        formal_policy_hash,
        profile_matrix_hash,
        frozen_profiles,
        True,
        not frozen_profiles,
        risk_coverage_complete,
        False,
        freeze_hash,
    )


def validate_gate_profile_freeze(value: GateProfileFreeze) -> None:
    if (
        value.schema != "buy-point-gate-shadow-v1"
        or len(value.training_identities) != 3
        or tuple(sorted(set(value.training_identities)))
        != value.training_identities
        or not value.retrospective
        or value.empty != (not value.profiles)
        or value.promotion_eligible
        or tuple(item.rank for item in value.profiles)
        != tuple(range(1, len(value.profiles) + 1))
        or any(
            item.profile_id.startswith("MARKET:")
            or not item.training_metrics.qualifies
            for item in value.profiles
        )
    ):
        raise ValueError("gate freeze model mismatch")
    expected = _calculate_freeze_hash(
        training_identities=value.training_identities,
        formal_rule_version=value.formal_rule_version,
        formal_policy_hash=value.formal_policy_hash,
        profile_matrix_hash=value.profile_matrix_hash,
        profiles=value.profiles,
        risk_coverage_complete=value.risk_coverage_complete,
    )
    if value.freeze_hash != expected:
        raise ValueError("gate freeze hash mismatch")


def select_frozen_gate_candidates(
    candidates: Sequence[GateShadowCandidate],
    freeze: GateProfileFreeze,
    *,
    maximum_per_date: int = 5,
) -> tuple[GateShadowCandidate, ...]:
    validate_gate_profile_freeze(freeze)
    if maximum_per_date < 1:
        raise ValueError("maximum_per_date must be positive")
    rank_by_profile = {
        value.profile_id: value.rank for value in freeze.profiles
    }
    eligible = [
        value
        for value in candidates
        if value.hit.profile.profile_id in rank_by_profile
    ]
    if any(
        value.executable_shares != 0
        or value.hit.executable_shares != 0
        or value.hit.profile.gate != "SECTOR"
        for value in eligible
    ):
        raise ValueError("screen candidates must be zero-share sector profiles")
    deduplicated: dict[tuple[date, str], GateShadowCandidate] = {}
    for candidate in sorted(
        eligible,
        key=lambda value: (
            value.hit.signal_date,
            normalize_code6(value.hit.code),
            rank_by_profile[value.hit.profile.profile_id],
            -value.hit.setup.quality,
            -value.two_r_space_buffer,
            -value.average_amount5_qian,
            value.hit.profile.profile_id,
        ),
    ):
        deduplicated.setdefault(
            (candidate.hit.signal_date, normalize_code6(candidate.hit.code)),
            candidate,
        )
    by_date: dict[date, list[GateShadowCandidate]] = {}
    for candidate in deduplicated.values():
        by_date.setdefault(candidate.hit.signal_date, []).append(candidate)
    selected = []
    for signal_date in sorted(by_date):
        ranked = sorted(
            by_date[signal_date],
            key=lambda value: (
                rank_by_profile[value.hit.profile.profile_id],
                -value.hit.setup.quality,
                -value.two_r_space_buffer,
                -value.average_amount5_qian,
                normalize_code6(value.hit.code),
            ),
        )
        selected.extend(ranked[:maximum_per_date])
    return tuple(selected)
