from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    FiveDayV3Policy,
    build_five_day_v3_policies,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_component_attribution import (
    ComponentOutcome,
    ExperimentRanking,
    ExperimentalRankedOutcome,
    ScoreComponents,
    experiment_score,
    rank_component_experiment,
    reconstruct_score_components,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (
    AttributedReturn,
)


def _policy(policy_id: str) -> FiveDayV3Policy:
    return next(
        value
        for value in build_five_day_v3_policies()
        if value.policy_id == policy_id
    )


def test_reconstructs_signed_policy_components_exactly() -> None:
    value = reconstruct_score_components(
        edge=Decimal("0.004"),
        consistency=Decimal("0.001"),
        feature_adjustment=Decimal("-0.002"),
        downside=Decimal("0.003"),
        policy=_policy("STRUCTURE-K60"),
        persisted_score=Decimal("0.001"),
    )

    assert value == ScoreComponents(
        edge=Decimal("0.004"),
        consistency=Decimal("0.0005"),
        structure=Decimal("-0.002"),
        downside=Decimal("-0.0015"),
    )
    assert value.baseline_score == Decimal("0.001")


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("edge", Decimal("NaN")),
        ("consistency", Decimal("Infinity")),
        ("feature_adjustment", Decimal("-Infinity")),
        ("downside", Decimal("NaN")),
        ("persisted_score", Decimal("Infinity")),
    ),
)
def test_score_reconstruction_rejects_non_finite_input(
    field: str,
    invalid: Decimal,
) -> None:
    values = {
        "edge": Decimal("0.004"),
        "consistency": Decimal("0.001"),
        "feature_adjustment": Decimal("-0.002"),
        "downside": Decimal("0.003"),
        "persisted_score": Decimal("0.001"),
    }
    values[field] = invalid

    with pytest.raises(ValueError, match="finite"):
        reconstruct_score_components(
            **values,
            policy=_policy("STRUCTURE-K60"),
        )


def test_score_reconstruction_rejects_unregistered_policy() -> None:
    policy = FiveDayV3Policy(
        policy_id="UNREGISTERED-K30",
        shrinkage_k=30,
        consistency_weight=Decimal("0.5"),
        structure_weight=Decimal("0.5"),
        downside_weight=Decimal("0.5"),
    )

    with pytest.raises(ValueError, match="registered"):
        reconstruct_score_components(
            edge=Decimal("0.004"),
            consistency=Decimal("0.001"),
            feature_adjustment=Decimal("-0.002"),
            downside=Decimal("0.003"),
            policy=policy,
            persisted_score=Decimal("0.0025"),
        )


def test_score_reconstruction_rejects_persisted_score_mismatch() -> None:
    with pytest.raises(ValueError, match="score reconstruction mismatch"):
        reconstruct_score_components(
            edge=Decimal("0.004"),
            consistency=Decimal("0.001"),
            feature_adjustment=Decimal("-0.002"),
            downside=Decimal("0.003"),
            policy=_policy("STRUCTURE-K60"),
            persisted_score=Decimal("0.0011"),
        )


def _components(
    edge: str,
    consistency: str = "0",
    structure: str = "0",
    downside: str = "0",
) -> ScoreComponents:
    return ScoreComponents(
        edge=Decimal(edge),
        consistency=Decimal(consistency),
        structure=Decimal(structure),
        downside=Decimal(downside),
    )


def _outcome(
    code: str,
    official_rank: int,
    *,
    components: ScoreComponents,
    full_edge: str = "0.003",
    recent_edge: str = "0.003",
    raw_downside: str = "0.002",
    setup_quality: str = "0.60",
    profile_id: str = "BREAKOUT_TRIGGER__STRUCTURE_ATR",
    signal_date: date = date(2025, 1, 2),
) -> ComponentOutcome:
    return ComponentOutcome(
        signal_date=signal_date,
        plan_identity=(
            signal_date,
            code,
            f"{code}-TREND_PULLBACK-{signal_date.isoformat()}",
            profile_id,
        ),
        profile_id=profile_id,
        setup_quality=Decimal(setup_quality),
        full_edge=Decimal(full_edge),
        recent_edge=Decimal(recent_edge),
        raw_downside=Decimal(raw_downside),
        official_rank=official_rank,
        components=components,
        value=AttributedReturn(
            raw_return=Decimal("0.01"),
            matched_index_return=Decimal("0"),
            market_median_return=Decimal("0"),
            index_excess=Decimal("0.01"),
            market_median_excess=Decimal("0.01"),
            market_members=1000,
        ),
    )


@pytest.mark.parametrize(
    ("experiment_id", "expected"),
    (
        ("BASELINE", Decimal("0.010")),
        ("WITHOUT_CONSISTENCY", Decimal("0.008")),
        ("WITHOUT_STRUCTURE", Decimal("0.007")),
        ("WITHOUT_DOWNSIDE", Decimal("0.015")),
    ),
)
def test_four_experiments_remove_exactly_one_signed_component(
    experiment_id: str,
    expected: Decimal,
) -> None:
    value = _components("0.010", "0.002", "0.003", "-0.005")

    assert experiment_score(value, experiment_id) == expected


def test_baseline_reproduces_v3_score_and_edge_tie_break_order() -> None:
    lower_edge = _outcome(
        "600002",
        2,
        components=_components("0.004", "0.006"),
    )
    higher_edge = _outcome(
        "600001",
        1,
        components=_components("0.006", "0.004"),
    )

    ranking = rank_component_experiment(
        (lower_edge, higher_edge),
        "BASELINE",
    )

    assert isinstance(ranking, ExperimentRanking)
    assert tuple(row.plan_identity[1] for row in ranking.rows) == (
        "600001",
        "600002",
    )
    assert tuple(row.rank for row in ranking.rows) == (1, 2)
    assert all(isinstance(row, ExperimentalRankedOutcome) for row in ranking.rows)
    assert ranking.candidate_rows == 2
    assert ranking.boundary_ties == 0


def test_ablation_uses_only_identity_after_equal_experimental_score() -> None:
    rows = (
        _outcome("600004", 4, components=_components("0.01")),
        _outcome(
            "600003",
            3,
            components=_components("0.02", downside="-0.004"),
            raw_downside="0.001",
        ),
        _outcome(
            "600002",
            2,
            components=_components("0.02", downside="-0.001"),
            raw_downside="0.003",
        ),
        _outcome("600001", 1, components=_components("0.03")),
    )

    ranking = rank_component_experiment(rows, "WITHOUT_DOWNSIDE")

    assert tuple(row.plan_identity[1] for row in ranking.rows) == (
        "600001",
        "600002",
        "600003",
        "600004",
    )
    assert ranking.boundary_ties == 0


@pytest.mark.parametrize(
    "scores",
    (
        ("0.03", "0.03", "0.02", "0.01"),
        ("0.04", "0.03", "0.02", "0.02"),
    ),
)
def test_tie_crossing_rank_one_or_rank_three_is_counted(
    scores: tuple[str, ...],
) -> None:
    rows = tuple(
        _outcome(
            f"60000{index}",
            index,
            components=_components(score),
        )
        for index, score in enumerate(scores, start=1)
    )

    ranking = rank_component_experiment(rows, "WITHOUT_STRUCTURE")

    assert ranking.boundary_ties == 1


def test_baseline_rejects_persisted_official_rank_mismatch() -> None:
    rows = (
        _outcome("600001", 2, components=_components("0.02")),
        _outcome("600002", 1, components=_components("0.01")),
    )

    with pytest.raises(ValueError, match="baseline rank reproduction"):
        rank_component_experiment(rows, "BASELINE")


def test_experiment_ranking_rejects_duplicate_plan_identity() -> None:
    row = _outcome("600001", 1, components=_components("0.02"))

    with pytest.raises(ValueError, match="duplicate plan identity"):
        rank_component_experiment((row, row), "WITHOUT_STRUCTURE")


def test_experiment_ranking_rejects_non_contiguous_official_ranks() -> None:
    rows = (
        _outcome("600001", 1, components=_components("0.02")),
        _outcome("600002", 3, components=_components("0.01")),
    )

    with pytest.raises(ValueError, match="official ranks"):
        rank_component_experiment(rows, "WITHOUT_STRUCTURE")


def test_experiment_ranking_rejects_unknown_experiment() -> None:
    row = _outcome("600001", 1, components=_components("0.02"))

    with pytest.raises(ValueError, match="experiment"):
        rank_component_experiment((row,), "WITHOUT_EDGE")
