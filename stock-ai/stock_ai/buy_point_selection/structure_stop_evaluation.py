"""Bounded outcomes and frozen selection for structure-stop research."""

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
from .models import BuyPointBar
from .structure_stop_shadow import (
    StructureStopCandidate,
    StructureStopProfile,
    build_structure_stop_profiles,
    structure_stop_profile_hash as compute_profile_matrix_hash,
    validate_structure_stop_profiles,
)


@dataclass(frozen=True)
class StructureStopOutcome:
    profile_id: str
    setup_type: str
    code: str
    signal_date: date
    outcome: CaseOutcome
    executable_shares: int = 0


@dataclass(frozen=True)
class StructureStopMetrics:
    profile_id: str
    setup_type: str
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
class FrozenStructureStopProfile:
    profile_id: str
    rank: int
    training_metrics: StructureStopMetrics


@dataclass(frozen=True)
class StructureStopFreeze:
    schema: str
    training_identities: tuple[str, ...]
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    profiles: tuple[FrozenStructureStopProfile, ...]
    retrospective: bool
    empty: bool
    risk_coverage_complete: bool
    promotion_eligible: bool
    freeze_hash: str


def evaluate_structure_stop_outcomes(
    candidates: Sequence[StructureStopCandidate],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    *,
    outcome_cutoff: date,
    costs: ExecutionCosts | None = None,
) -> tuple[StructureStopOutcome, ...]:
    rows = []
    supported = {
        profile.profile_id for profile in build_structure_stop_profiles()
    }
    for candidate in candidates:
        if not isinstance(candidate, StructureStopCandidate):
            raise ValueError("structure stop candidate required")
        if candidate.profile.profile_id not in supported:
            raise ValueError("unsupported structure stop profile")
        if (
            candidate.executable_shares != 0
            or candidate.hit.executable_shares != 0
            or candidate.anchor.executable_shares != 0
            or candidate.status != "CASE_ANALYSIS_ONLY"
            or candidate.trade_permission != "NO-TRADE"
        ):
            raise ValueError(
                "structure stop candidate must remain zero-share research"
            )
        adapted = CaseCandidate(
            candidate.hit.code,
            candidate.hit.signal_date,
            candidate.hit.setup,
            candidate.plan,
            "STRUCTURE_STOP_SHADOW",
            candidate.profile.profile_id,
            (
                -candidate.hit.setup.quality,
                -candidate.two_r_space_buffer,
                -candidate.average_amount5_qian,
                normalize_code6(candidate.hit.code),
            ),
        )
        outcome = evaluate_case_plan(
            adapted,
            bars_by_code.get(candidate.hit.code, ()),
            outcome_cutoff=outcome_cutoff,
            costs=costs,
        )
        rows.append(
            StructureStopOutcome(
                candidate.profile.profile_id,
                candidate.hit.setup.setup_type.value,
                normalize_code6(candidate.hit.code),
                candidate.hit.signal_date,
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


def aggregate_structure_stop_metrics(
    candidate_profile_setup_ids: Sequence[tuple[str, str]],
    outcomes: Sequence[StructureStopOutcome],
) -> tuple[StructureStopMetrics, ...]:
    candidate_counts = Counter(candidate_profile_setup_ids)
    profiles = {
        profile_id for profile_id, _ in candidate_profile_setup_ids
    } | {value.profile_id for value in outcomes}
    rows = []
    for profile_id in sorted(profiles):
        setup_types = {
            setup_type
            for candidate_profile_id, setup_type in candidate_profile_setup_ids
            if candidate_profile_id == profile_id
        } | {
            value.setup_type
            for value in outcomes
            if value.profile_id == profile_id
        }
        for setup_type in ("ALL", *sorted(setup_types)):
            grouped = [
                value
                for value in outcomes
                if value.profile_id == profile_id
                and (setup_type == "ALL" or value.setup_type == setup_type)
            ]
            triggered = [
                value
                for value in grouped
                if value.outcome.trigger_date is not None
            ]
            resolved = [
                value
                for value in triggered
                if value.outcome.net_return is not None
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
            if resolved_count < 10:
                reasons.append("MINIMUM_RESOLVED_TRIGGERED")
            if mean_net is None or mean_net <= 0:
                reasons.append("MEAN_NET_RETURN_NOT_POSITIVE")
            if positive_rate is None or positive_rate < Decimal("0.50"):
                reasons.append("POSITIVE_NET_RATE_BELOW_HALF")
            if stop_rate is None or stop_rate > Decimal("0.40"):
                reasons.append("STOP_FIRST_RATE_ABOVE_40_PERCENT")
            candidate_count = (
                sum(
                    count
                    for (candidate_profile_id, _), count in candidate_counts.items()
                    if candidate_profile_id == profile_id
                )
                if setup_type == "ALL"
                else candidate_counts.get((profile_id, setup_type), 0)
            )
            rows.append(
                StructureStopMetrics(
                    profile_id,
                    setup_type,
                    candidate_count,
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
    return tuple(rows)


def _qualification_reasons(
    value: StructureStopMetrics,
) -> tuple[str, ...]:
    reasons = []
    if value.resolved < 10:
        reasons.append("MINIMUM_RESOLVED_TRIGGERED")
    if value.mean_net_return is None or value.mean_net_return <= 0:
        reasons.append("MEAN_NET_RETURN_NOT_POSITIVE")
    if (
        value.positive_net_rate is None
        or value.positive_net_rate < Decimal("0.50")
    ):
        reasons.append("POSITIVE_NET_RATE_BELOW_HALF")
    if (
        value.stop_first_rate is None
        or value.stop_first_rate > Decimal("0.40")
    ):
        reasons.append("STOP_FIRST_RATE_ABOVE_40_PERCENT")
    return tuple(reasons)


def _metrics_payload(value: StructureStopMetrics) -> dict[str, object]:
    def decimal(item: Decimal | None) -> str | None:
        return None if item is None else str(item)

    return {
        "profile_id": value.profile_id,
        "setup_type": value.setup_type,
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


def _profile_rank_key(value: StructureStopMetrics) -> tuple[object, ...]:
    return (
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


def _calculate_freeze_hash(
    *,
    training_identities: Sequence[str],
    formal_rule_version: str,
    formal_policy_hash: str,
    profile_matrix_hash: str,
    profiles: Sequence[FrozenStructureStopProfile],
    risk_coverage_complete: bool,
) -> str:
    payload = {
        "schema": "buy-point-structure-stop-shadow-v1",
        "training_identities": list(training_identities),
        "formal_rule_version": formal_rule_version,
        "formal_policy_hash": formal_policy_hash,
        "profile_matrix_hash": profile_matrix_hash,
        "profiles": [
            {
                "profile_id": value.profile_id,
                "rank": value.rank,
                "training_metrics": _metrics_payload(
                    value.training_metrics
                ),
            }
            for value in profiles
        ],
        "retrospective": True,
        "empty": not profiles,
        "risk_coverage_complete": risk_coverage_complete,
        "promotion_eligible": False,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def freeze_structure_stop_profiles(
    *,
    profiles: Sequence[StructureStopProfile],
    training_identities: Sequence[str],
    metrics: Sequence[StructureStopMetrics],
    formal_rule_version: str,
    formal_policy_hash: str,
    profile_matrix_hash: str,
    risk_coverage_complete: bool,
) -> StructureStopFreeze:
    validate_structure_stop_profiles(profiles)
    identities = tuple(sorted(training_identities))
    if len(identities) != 8 or len(set(identities)) != 8:
        raise ValueError("freeze requires eight distinct research identities")
    if profile_matrix_hash != compute_profile_matrix_hash(profiles):
        raise ValueError("structure stop profile matrix hash mismatch")
    supported = {value.profile_id for value in profiles}
    if any(value.profile_id not in supported for value in metrics):
        raise ValueError("metrics contain unsupported structure stop profile")
    for value in metrics:
        expected_reasons = _qualification_reasons(value)
        if (
            value.qualification_reasons != expected_reasons
            or value.qualifies != (not expected_reasons)
        ):
            raise ValueError("structure stop metric qualification mismatch")
    overall = [value for value in metrics if value.setup_type == "ALL"]
    if len({value.profile_id for value in overall}) != len(overall):
        raise ValueError("duplicate overall structure stop metrics")
    qualifying = [
        value
        for value in overall
        if value.qualifies and not _qualification_reasons(value)
    ]
    qualifying.sort(key=_profile_rank_key)
    frozen_profiles = tuple(
        FrozenStructureStopProfile(value.profile_id, index, value)
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
    return StructureStopFreeze(
        "buy-point-structure-stop-shadow-v1",
        identities,
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


def _is_hash(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def validate_structure_stop_freeze(value: StructureStopFreeze) -> None:
    supported = {
        profile.profile_id for profile in build_structure_stop_profiles()
    }
    metrics = tuple(item.training_metrics for item in value.profiles)
    expected_order = tuple(sorted(metrics, key=_profile_rank_key))
    if (
        value.schema != "buy-point-structure-stop-shadow-v1"
        or len(value.training_identities) != 8
        or tuple(sorted(set(value.training_identities)))
        != value.training_identities
        or not value.formal_rule_version
        or not _is_hash(value.formal_policy_hash)
        or value.profile_matrix_hash
        != compute_profile_matrix_hash(build_structure_stop_profiles())
        or not value.retrospective
        or value.empty != (not value.profiles)
        or value.promotion_eligible
        or tuple(item.rank for item in value.profiles)
        != tuple(range(1, len(value.profiles) + 1))
        or len({item.profile_id for item in value.profiles})
        != len(value.profiles)
        or any(
            item.profile_id not in supported
            or item.training_metrics.profile_id != item.profile_id
            or item.training_metrics.setup_type != "ALL"
            or not item.training_metrics.qualifies
            or item.training_metrics.qualification_reasons
            or _qualification_reasons(item.training_metrics)
            for item in value.profiles
        )
        or metrics != expected_order
    ):
        raise ValueError("structure stop freeze model mismatch")
    expected_hash = _calculate_freeze_hash(
        training_identities=value.training_identities,
        formal_rule_version=value.formal_rule_version,
        formal_policy_hash=value.formal_policy_hash,
        profile_matrix_hash=value.profile_matrix_hash,
        profiles=value.profiles,
        risk_coverage_complete=value.risk_coverage_complete,
    )
    if not _is_hash(value.freeze_hash) or value.freeze_hash != expected_hash:
        raise ValueError("structure stop freeze hash mismatch")


def select_frozen_structure_stop_candidates(
    candidates: Sequence[StructureStopCandidate],
    freeze: StructureStopFreeze,
    *,
    maximum_per_date: int = 5,
) -> tuple[StructureStopCandidate, ...]:
    validate_structure_stop_freeze(freeze)
    if maximum_per_date < 1:
        raise ValueError("maximum_per_date must be positive")
    supported = {
        profile.profile_id for profile in build_structure_stop_profiles()
    }
    for candidate in candidates:
        if not isinstance(candidate, StructureStopCandidate):
            raise ValueError("structure stop candidate required")
        if candidate.profile.profile_id not in supported:
            raise ValueError("unsupported structure stop profile")
        if (
            candidate.executable_shares != 0
            or candidate.hit.executable_shares != 0
            or candidate.anchor.executable_shares != 0
            or candidate.status != "CASE_ANALYSIS_ONLY"
            or candidate.trade_permission != "NO-TRADE"
        ):
            raise ValueError(
                "screen candidate must remain zero-share research"
            )
    rank_by_profile = {
        value.profile_id: value.rank for value in freeze.profiles
    }
    eligible = [
        value
        for value in candidates
        if value.profile.profile_id in rank_by_profile
    ]
    deduplicated: dict[tuple[date, str], StructureStopCandidate] = {}
    for candidate in sorted(
        eligible,
        key=lambda value: (
            value.hit.signal_date,
            normalize_code6(value.hit.code),
            rank_by_profile[value.profile.profile_id],
            -value.hit.setup.quality,
            -value.two_r_space_buffer,
            -value.average_amount5_qian,
            value.profile.profile_id,
        ),
    ):
        deduplicated.setdefault(
            (
                candidate.hit.signal_date,
                normalize_code6(candidate.hit.code),
            ),
            candidate,
        )
    by_date: dict[date, list[StructureStopCandidate]] = {}
    for candidate in deduplicated.values():
        by_date.setdefault(candidate.hit.signal_date, []).append(candidate)
    selected = []
    for signal_date in sorted(by_date):
        ranked = sorted(
            by_date[signal_date],
            key=lambda value: (
                rank_by_profile[value.profile.profile_id],
                -value.hit.setup.quality,
                -value.two_r_space_buffer,
                -value.average_amount5_qian,
                normalize_code6(value.hit.code),
            ),
        )
        selected.extend(ranked[:maximum_per_date])
    return tuple(selected)
