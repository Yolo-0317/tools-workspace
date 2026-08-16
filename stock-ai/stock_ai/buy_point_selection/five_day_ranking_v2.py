"""Conservative point-in-time ranking policies for five-day research."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from typing import Sequence

from .five_day_return_runtime import FiveDaySignalPlan


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
