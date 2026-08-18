"""Train-only score-component attribution for five-day ranking V3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from itertools import groupby
from typing import TypeAlias

from .five_day_ranking_v3 import (
    FiveDayV3Policy,
    build_five_day_v3_policies,
)
from .five_day_ranking_v3_attribution import AttributedReturn
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
