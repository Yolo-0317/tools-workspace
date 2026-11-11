from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from .models import ChainMetrics, ChainScore, RotationPolicy, RotationState

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDREDTH = Decimal("0.01")


def _clamp(value: Decimal) -> Decimal:
    return max(_ZERO, min(_ONE, value))


def _mean(*values: Decimal) -> Decimal:
    return sum(values, _ZERO) / Decimal(len(values))


def _scale(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    if high <= low:
        raise ValueError("scale upper bound must exceed lower bound")
    return _clamp((value - low) / (high - low))


def score_chain(metrics: ChainMetrics, policy: RotationPolicy) -> ChainScore:
    normalized_rank_improvement = _clamp(metrics.rank_improvement)
    strength = Decimal("30") * _clamp(
        _mean(metrics.return_percentile, normalized_rank_improvement)
    )
    breadth = Decimal("25") * _clamp(
        _mean(metrics.breadth_ratio, metrics.above_ma5_ratio, metrics.above_ma20_ratio)
    )
    amount = Decimal("20") * _clamp(
        _mean(
            _scale(metrics.amount_ratio, Decimal("0.70"), Decimal("1.50")),
            metrics.advancing_amount_ratio,
        )
    )
    persistence = Decimal("15") * _clamp(
        Decimal(metrics.persistence_count) / Decimal(policy.confirm_snapshots)
    )
    structure = Decimal("10") * _clamp(_ONE - metrics.leader_concentration)

    reasons: list[str] = []
    penalty = _ZERO
    if metrics.leader_concentration >= Decimal("0.75") and metrics.breadth_ratio < Decimal("0.30"):
        reasons.append("LEADER_ONLY")
        penalty += Decimal("15")
    if metrics.breadth_ratio < Decimal("0.35"):
        reasons.append("BREADTH_WEAK")
        penalty += Decimal("8")
    if metrics.amount_ratio < Decimal("0.80"):
        reasons.append("AMOUNT_WEAK")
        penalty += Decimal("6")
    if not metrics.data_complete:
        reasons.append("DATA_INCOMPLETE")
        penalty += Decimal("10")

    total = max(
        _ZERO,
        strength + breadth + amount + persistence + structure - penalty,
    )
    return ChainScore(
        total=total.quantize(_HUNDREDTH),
        strength_score=strength.quantize(_HUNDREDTH),
        breadth_score=breadth.quantize(_HUNDREDTH),
        amount_score=amount.quantize(_HUNDREDTH),
        persistence_score=persistence.quantize(_HUNDREDTH),
        structure_score=structure.quantize(_HUNDREDTH),
        overheat_penalty=penalty.quantize(_HUNDREDTH),
        reasons=tuple(reasons),
    )


def classify_state(
    score: ChainScore,
    metrics: ChainMetrics,
    previous: Sequence[tuple[RotationState, ChainScore]],
    policy: RotationPolicy,
) -> tuple[RotationState | None, tuple[str, ...]]:
    reasons = list(score.reasons)

    if not metrics.data_complete:
        return (
            RotationState.LATENT if score.total >= policy.latent_score_min else None,
            tuple(dict.fromkeys(reasons)),
        )

    if "LEADER_ONLY" in reasons:
        return RotationState.OVERHEATED, tuple(dict.fromkeys(reasons))

    latest_state, latest_score = previous[-1] if previous else (None, None)
    previously_confirmed = latest_state is RotationState.CONFIRMED
    if previously_confirmed and latest_score is not None:
        if latest_score.total - score.total >= policy.fading_score_drop:
            reasons.append("SCORE_DROPPED")
        if metrics.breadth_ratio < Decimal("0.35"):
            reasons.append("BREADTH_COLLAPSED")
        if "SCORE_DROPPED" in reasons or "BREADTH_COLLAPSED" in reasons:
            return RotationState.FADING, tuple(dict.fromkeys(reasons))

    valid_prior_states = {RotationState.STARTING, RotationState.CONFIRMED}
    consecutive = 0
    for prior_state, _ in reversed(previous):
        if prior_state not in valid_prior_states:
            break
        consecutive += 1
    if score.total >= policy.starting_score_min and consecutive >= policy.confirm_snapshots:
        reasons.append("PERSISTENCE_CONFIRMED")
        return RotationState.CONFIRMED, tuple(dict.fromkeys(reasons))
    if score.total >= policy.starting_score_min:
        reasons.append("STARTING_THRESHOLD_MET")
        return RotationState.STARTING, tuple(dict.fromkeys(reasons))
    if score.total >= policy.latent_score_min:
        reasons.append("LATENT_THRESHOLD_MET")
        return RotationState.LATENT, tuple(dict.fromkeys(reasons))
    return None, tuple(dict.fromkeys(reasons))
