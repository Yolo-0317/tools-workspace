from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    FiveDayV3Policy,
    build_five_day_v3_policies,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_component_attribution import (
    AblationDelta,
    ComponentOutcome,
    ComponentEffectReview,
    ExperimentRanking,
    ExperimentalRankedOutcome,
    RankMetricAuditTotals,
    RobustRankMetrics,
    ScoreComponents,
    classify_component_effect,
    compare_ablation,
    experiment_score,
    rank_component_experiment,
    reconstruct_score_components,
    summarize_component_correlations,
    summarize_experiment_ranking,
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
    raw_return: str = "0.01",
) -> ComponentOutcome:
    raw = Decimal(raw_return)
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
            raw_return=raw,
            matched_index_return=Decimal("0"),
            market_median_return=Decimal("0"),
            index_excess=raw,
            market_median_excess=raw,
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


def _perfect_ranking(days: int = 30) -> ExperimentRanking:
    rows: list[ExperimentalRankedOutcome] = []
    for day_index in range(days):
        signal_date = date(2025, 2, 3) + timedelta(days=day_index)
        for rank, raw in enumerate(
            ("0.05", "0.04", "0.03", "0.02", "0.01"),
            start=1,
        ):
            code = f"60{day_index:02d}{rank:02d}"
            outcome = _outcome(
                code,
                rank,
                components=_components(raw),
                signal_date=signal_date,
                raw_return=raw,
            )
            rows.append(
                ExperimentalRankedOutcome(
                    signal_date=signal_date,
                    plan_identity=outcome.plan_identity,
                    rank=rank,
                    value=outcome.value,
                    components=outcome.components,
                )
            )
    return ExperimentRanking(
        experiment_id="BASELINE",
        rows=tuple(rows),
        candidate_rows=len(rows),
        boundary_ties=0,
    )


def test_robust_rank_metrics_keep_exact_pair_and_correlation_audits() -> None:
    value = summarize_experiment_ranking(_perfect_ranking())

    assert isinstance(value, RobustRankMetrics)
    assert value.candidate_rows == 150
    assert value.paired_dates == 30
    assert value.correlation_eligible_dates == 30
    assert value.correlation_dates == 30
    assert value.audit == RankMetricAuditTotals(
        raw_difference_sum=Decimal("0.450"),
        index_excess_difference_sum=Decimal("0.450"),
        market_excess_difference_sum=Decimal("0.450"),
        rank_one_win_dates=30,
        raw_correlation_sum=Decimal("30"),
        index_excess_correlation_sum=Decimal("30"),
        market_excess_correlation_sum=Decimal("30"),
    )
    assert value.mean_raw_difference == Decimal("0.015")
    assert value.median_raw_difference == Decimal("0.015")
    assert value.rank_one_win_ratio == Decimal("1")
    assert value.rank_one_win_interval is not None
    assert value.rank_one_win_interval[1] == Decimal("1")
    assert value.mean_raw_correlation == Decimal("1")
    assert value.median_raw_correlation == Decimal("1")


def test_robust_rank_metrics_never_pair_across_dates() -> None:
    first = date(2025, 3, 3)
    second = first + timedelta(days=1)
    rows = (
        _outcome(
            "600001",
            1,
            components=_components("0.01"),
            signal_date=first,
            raw_return="0.03",
        ),
        _outcome(
            "600002",
            2,
            components=_components("0.01"),
            signal_date=first,
            raw_return="0.01",
        ),
        _outcome(
            "600003",
            1,
            components=_components("0.01"),
            signal_date=second,
            raw_return="-0.02",
        ),
        _outcome(
            "600004",
            2,
            components=_components("0.01"),
            signal_date=second,
            raw_return="0.01",
        ),
    )
    ranking = ExperimentRanking(
        experiment_id="BASELINE",
        rows=tuple(
            ExperimentalRankedOutcome(
                signal_date=row.signal_date,
                plan_identity=row.plan_identity,
                rank=row.official_rank,
                value=row.value,
                components=row.components,
            )
            for row in rows
        ),
        candidate_rows=4,
        boundary_ties=0,
    )

    value = summarize_experiment_ranking(ranking)

    assert value.paired_dates == 2
    assert value.audit.raw_difference_sum == Decimal("-0.01")
    assert value.median_raw_difference == Decimal("-0.005")


def test_component_correlations_use_signed_component_contributions() -> None:
    rows: list[ComponentOutcome] = []
    signal_date = date(2025, 4, 1)
    for rank, raw in enumerate(
        ("0.05", "0.04", "0.03", "0.02", "0.01"),
        start=1,
    ):
        rows.append(
            _outcome(
                f"60000{rank}",
                rank,
                components=_components(
                    raw,
                    consistency=str(-Decimal(raw)),
                    structure="0",
                    downside=str(-Decimal(raw)),
                ),
                signal_date=signal_date,
                raw_return=raw,
            )
        )

    values = {
        value.component_id: value
        for value in summarize_component_correlations(tuple(rows))
    }

    assert values["EDGE"].completed_dates == 1
    assert values["EDGE"].mean_raw_correlation == Decimal("1")
    assert values["CONSISTENCY"].mean_raw_correlation == Decimal("-1")
    assert values["DOWNSIDE"].mean_raw_correlation == Decimal("-1")
    assert values["STRUCTURE"].eligible_dates == 1
    assert values["STRUCTURE"].completed_dates == 0
    assert values["STRUCTURE"].mean_raw_correlation is None


def test_compare_ablation_uses_ablation_minus_baseline() -> None:
    baseline = summarize_experiment_ranking(_perfect_ranking())
    ablation = replace(
        baseline,
        median_raw_difference=Decimal("0.020"),
        rank_one_win_ratio=Decimal("0.9"),
        mean_raw_correlation=Decimal("0.8"),
        mean_index_excess_difference=Decimal("0.017"),
        mean_market_excess_difference=Decimal("0.018"),
        boundary_ties=1,
    )

    value = compare_ablation(baseline, ablation)

    assert value == AblationDelta(
        paired_dates=30,
        correlation_dates=30,
        boundary_ties=1,
        median_raw_difference_delta=Decimal("0.005"),
        rank_one_win_ratio_delta=Decimal("-0.1"),
        mean_raw_correlation_delta=Decimal("-0.2"),
        mean_index_excess_difference_delta=Decimal("0.002"),
        mean_market_excess_difference_delta=Decimal("0.003"),
    )


def _delta(
    core: str,
    benchmark: str,
    *,
    paired_dates: int = 30,
    correlation_dates: int = 30,
    boundary_ties: int = 0,
) -> AblationDelta:
    return AblationDelta(
        paired_dates=paired_dates,
        correlation_dates=correlation_dates,
        boundary_ties=boundary_ties,
        median_raw_difference_delta=Decimal(core),
        rank_one_win_ratio_delta=Decimal(core),
        mean_raw_correlation_delta=Decimal(core),
        mean_index_excess_difference_delta=Decimal(benchmark),
        mean_market_excess_difference_delta=Decimal(benchmark),
    )


@pytest.mark.parametrize(
    ("fold1", "fold2", "expected"),
    (
        (_delta("0.01", "0"), _delta("0.02", "0.01"), "CONSISTENTLY_HARMFUL"),
        (_delta("-0.01", "0"), _delta("-0.02", "-0.01"), "CONSISTENTLY_HELPFUL"),
        (_delta("0.01", "0"), _delta("-0.01", "0"), "REGIME_UNSTABLE"),
        (_delta("0.01", "-0.01"), _delta("0.01", "0"), "INCONCLUSIVE"),
    ),
)
def test_component_effect_label_truth_table(
    fold1: AblationDelta,
    fold2: AblationDelta,
    expected: str,
) -> None:
    value = classify_component_effect(
        fold1,
        fold2,
        component_id="STRUCTURE",
    )

    assert isinstance(value, ComponentEffectReview)
    assert value.component_id == "STRUCTURE"
    assert value.label == expected


@pytest.mark.parametrize(
    "fold1",
    (
        _delta("0.01", "0.01", paired_dates=29),
        _delta("0.01", "0.01", correlation_dates=29),
        _delta("0.01", "0.01", boundary_ties=1),
        _delta("0", "0.01"),
    ),
)
def test_component_effect_is_inconclusive_without_strict_usable_evidence(
    fold1: AblationDelta,
) -> None:
    value = classify_component_effect(
        fold1,
        _delta("0.01", "0.01"),
        component_id="CONSISTENCY",
    )

    assert value.label == "INCONCLUSIVE"
