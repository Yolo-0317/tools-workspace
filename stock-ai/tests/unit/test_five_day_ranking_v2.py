from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module

import pytest

from stock_ai.buy_point_selection.five_day_return_profiles import (
    build_five_day_return_profiles,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayCalibration,
)
from stock_ai.buy_point_selection.models import DetectedSetup, SetupType


START = date(2023, 1, 2)


def _plan(
    *,
    code: str = "600001",
    profile_index: int = 0,
    setup_type: SetupType = SetupType.PRE_BREAKOUT,
    market_status: str = "ALLOW",
    sector_resonating: bool | None = True,
    resistance_basis: str = "NO_RELIABLE_LEVEL",
    quality: str = "0.80",
    signal_date: date = START,
) -> FiveDaySignalPlan:
    profile = build_five_day_return_profiles()[profile_index]
    setup = DetectedSetup(
        code=code,
        setup_type=setup_type,
        analysis_date=signal_date,
        structure_start=signal_date - timedelta(days=10),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.50"),
        quality=Decimal(quality),
        reasons=("FIXTURE",),
        metrics={},
    )
    candidate = FiveDaySignalCandidate(
        code=code,
        signal_date=signal_date,
        setup=setup,
        market_status=market_status,
        sector_code="801010",
        sector_resonating=sector_resonating,
        anti_chase_passed=True,
        average_amount5_qian=Decimal("200000"),
        valid_through_trade_date=signal_date + timedelta(days=2),
    )
    return FiveDaySignalPlan(
        candidate=candidate,
        profile=profile,
        structure_id=f"{code}-{signal_date.isoformat()}-{profile.profile_id}",
        signal_close=Decimal("10.00"),
        breakout_trigger=Decimal("10.01"),
        structure_stop=Decimal("9.50"),
        reference_entry=Decimal("10.01"),
        resistance_basis=resistance_basis,
        resistance_effective_r=None,
    )


def _calibration(
    plan: FiveDaySignalPlan,
    *,
    expectancy: str = "0.02",
    profit_factor: str | None = "1.50",
    wilson_lower: str = "0.50",
    positive_windows: str = "0.70",
    mae_p75: str = "0.01",
    stop_rate: str = "0.20",
    triggered_resolved: int = 30,
    data_end: date | None = None,
) -> FiveDayCalibration:
    market = plan.candidate.market_status
    sector = plan.candidate.sector_resonating
    key = "|".join(
        (
            plan.profile.profile_id,
            plan.candidate.setup.setup_type.value,
            market if market is not None else "*",
            str(sector) if sector is not None else "*",
        )
    )
    return FiveDayCalibration(
        key=key,
        profile_id=plan.profile.profile_id,
        setup_type=plan.candidate.setup.setup_type,
        market_status=market,
        sector_resonating=sector,
        data_end=data_end or plan.candidate.signal_date - timedelta(days=1),
        total_plans=triggered_resolved,
        triggered_resolved=triggered_resolved,
        positive_net=20,
        profitable_rate=Decimal("0.6666666667"),
        profitable_interval=(Decimal(wilson_lower), Decimal("0.80")),
        net_expectancy=Decimal(expectancy),
        profit_factor=(
            Decimal(profit_factor) if profit_factor is not None else None
        ),
        stop_rate=Decimal(stop_rate),
        mae_p75=Decimal(mae_p75),
        positive_window_ratio=Decimal(positive_windows),
    )


def _policy(policy_id: str):
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    return next(
        value
        for value in ranking_v2.build_five_day_v2_policies()
        if value.policy_id == policy_id
    )


def test_v2_registry_contains_exactly_the_preregistered_twelve() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    policies = ranking_v2.build_five_day_v2_policies()

    assert tuple(value.policy_id for value in policies) == (
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
    assert all(sum(value.weights.as_tuple()) == 100 for value in policies)
    hashes = {
        ranking_v2.five_day_v2_policy_hash(value) for value in policies
    }
    assert len(hashes) == 12
    assert all(len(value) == 64 for value in hashes)
    assert len(ranking_v2.five_day_v2_policy_set_hash()) == 64


def test_v2_policy_types_reject_nonpreregistered_parameters() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    weights = ranking_v2.V2Weights(35, 20, 15, 10, 10, 5, 5)

    with pytest.raises(ValueError, match="weights must sum to 100"):
        ranking_v2.V2Weights(34, 20, 15, 10, 10, 5, 5)
    with pytest.raises(ValueError, match="shrinkage_k must be 30 or 60"):
        ranking_v2.FiveDayV2Policy(
            policy_id="EDGE-K10-BASE",
            ranking_version=ranking_v2.V2_RANKING_VERSION,
            shrinkage_k=10,
            gate_mode="BASE",
            weights=weights,
        )
    with pytest.raises(ValueError, match="unsupported gate mode"):
        ranking_v2.FiveDayV2Policy(
            policy_id="EDGE-K30-UNKNOWN",
            ranking_version=ranking_v2.V2_RANKING_VERSION,
            shrinkage_k=30,
            gate_mode="UNKNOWN",
            weights=weights,
        )


def test_shrinkage_has_literal_boundary_and_rejects_invalid_inputs() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    assert ranking_v2.shrink_five_day_edge(
        Decimal("0.02"),
        30,
        30,
    ) == Decimal("0.01")
    with pytest.raises(ValueError, match="invalid shrinkage inputs"):
        ranking_v2.shrink_five_day_edge(Decimal("0.02"), -1, 30)
    with pytest.raises(ValueError, match="invalid shrinkage inputs"):
        ranking_v2.shrink_five_day_edge(Decimal("0.02"), 30, 0)


def test_relative_percentiles_preserve_ties_direction_and_boundaries() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    assert ranking_v2.relative_percentiles(
        (Decimal("1"), Decimal("2"), Decimal("2"), Decimal("4")),
        higher_is_better=True,
    ) == (
        Decimal("0"),
        Decimal("0.5"),
        Decimal("0.5"),
        Decimal("1"),
    )
    assert ranking_v2.relative_percentiles(
        (Decimal("1"), Decimal("2"), Decimal("4")),
        higher_is_better=False,
    ) == (Decimal("1"), Decimal("0.5"), Decimal("0"))
    assert ranking_v2.relative_percentiles(
        (Decimal("7"),),
        higher_is_better=False,
    ) == (Decimal("0.5"),)
    with pytest.raises(ValueError, match="percentile input must not be empty"):
        ranking_v2.relative_percentiles((), higher_is_better=True)


def test_context_score_uses_only_the_three_literal_signal_time_inputs() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    best = _plan(
        market_status="ALLOW",
        sector_resonating=True,
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
    )
    middle = _plan(
        market_status="LIMITED",
        sector_resonating=None,
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
    )
    worst = _plan(
        market_status="LIMITED",
        sector_resonating=False,
        resistance_basis="LEVEL_BELOW_2R",
    )

    assert ranking_v2.five_day_v2_context_score(best) == Decimal("1")
    assert ranking_v2.five_day_v2_context_score(middle) == Decimal("0.5")
    assert ranking_v2.five_day_v2_context_score(worst) == Decimal("0")


def test_v2_base_gate_rejects_nonpositive_edge_and_weak_profit_factor() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    negative_edge = _plan(code="600001", profile_index=0)
    weak_profit_factor = _plan(code="600002", profile_index=1)
    eligible = _plan(code="600003", profile_index=2)
    calibration_values = (
        _calibration(negative_edge, expectancy="-0.01"),
        _calibration(weak_profit_factor, profit_factor="1.0"),
        _calibration(eligible, expectancy="0.03"),
    )

    result = ranking_v2.rank_five_day_plans_v2(
        (negative_edge, weak_profit_factor, eligible),
        {value.key: value for value in calibration_values},
        policy=_policy("EDGE-K30-BASE"),
    )

    assert result.ranking.plans == (eligible,)
    assert result.ranking.rejection_counts == {
        "NON_POSITIVE_SHRUNK_EDGE": 1,
        "PROFIT_FACTOR_NOT_ABOVE_ONE": 1,
    }


def test_v2_stable_negative_gate_is_literal_and_unknown_is_not_false() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    nonresonating = _plan(
        code="600001",
        profile_index=0,
        sector_resonating=False,
    )
    first_launch_pullback = _plan(
        code="600002",
        profile_index=1,
        setup_type=SetupType.FIRST_LAUNCH_PULLBACK,
    )
    unknown_sector = _plan(
        code="600003",
        profile_index=2,
        sector_resonating=None,
    )
    allowed = _plan(code="600004", profile_index=3)
    calibration_values = (
        _calibration(nonresonating),
        _calibration(first_launch_pullback),
        _calibration(unknown_sector, expectancy="0.04"),
        _calibration(allowed, expectancy="0.02"),
    )

    result = ranking_v2.rank_five_day_plans_v2(
        (nonresonating, first_launch_pullback, unknown_sector, allowed),
        {value.key: value for value in calibration_values},
        policy=_policy("BALANCED-K60-STABLE_NEGATIVE"),
    )

    assert result.ranking.plans == (unknown_sector, allowed)
    assert result.ranking.rejection_counts == {
        "STABLE_NEGATIVE_SECTOR": 1,
        "STABLE_NEGATIVE_SETUP": 1,
    }


def test_v2_rejects_active_missing_and_non_point_in_time_plans() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    active = _plan(code="600001", profile_index=0)
    missing = _plan(code="600002", profile_index=1)
    future_calibration = _plan(code="600003", profile_index=2)
    calibration_values = (
        _calibration(active),
        _calibration(
            future_calibration,
            data_end=future_calibration.candidate.signal_date,
        ),
    )

    result = ranking_v2.rank_five_day_plans_v2(
        (active, missing, future_calibration),
        {value.key: value for value in calibration_values},
        policy=_policy("EDGE-K30-BASE"),
        active_structure_ids=frozenset((active.structure_id,)),
    )

    assert result.ranking.plans == ()
    assert result.ranking.rejection_counts == {
        "CALIBRATION_NOT_POINT_IN_TIME": 1,
        "EXISTING_ACTIVE_STRUCTURE": 1,
        "INSUFFICIENT_CALIBRATION": 1,
    }


def test_v2_rejects_negative_daily_limit() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    with pytest.raises(ValueError, match="daily_limit must not be negative"):
        ranking_v2.rank_five_day_plans_v2(
            (),
            {},
            policy=_policy("EDGE-K30-BASE"),
            daily_limit=-1,
        )


def test_v2_composite_score_uses_all_seven_weighted_percentiles() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    edge_only = _plan(
        code="600001",
        profile_index=0,
        market_status="LIMITED",
        sector_resonating=False,
        resistance_basis="LEVEL_BELOW_2R",
        quality="0.50",
    )
    other_six = _plan(
        code="600002",
        profile_index=1,
        market_status="ALLOW",
        sector_resonating=True,
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
        quality="0.90",
    )
    calibration_values = (
        _calibration(
            edge_only,
            expectancy="0.04",
            wilson_lower="0.40",
            positive_windows="0.50",
            mae_p75="0.03",
            stop_rate="0.30",
        ),
        _calibration(
            other_six,
            expectancy="0.02",
            wilson_lower="0.60",
            positive_windows="0.80",
            mae_p75="0.01",
            stop_rate="0.10",
        ),
    )

    result = ranking_v2.rank_five_day_plans_v2(
        (edge_only, other_six),
        {value.key: value for value in calibration_values},
        policy=_policy("EDGE-K30-BASE"),
    )

    assert result.ranking.plans == (other_six, edge_only)
    assert tuple(value.score for value in result.scored) == (
        Decimal("65"),
        Decimal("35"),
    )
    assert result.scored[0].components == ranking_v2.V2ScoreComponents(
        edge=Decimal("0"),
        wilson=Decimal("1"),
        positive_windows=Decimal("1"),
        low_mae=Decimal("1"),
        low_stop_rate=Decimal("1"),
        context=Decimal("1"),
        setup_quality=Decimal("1"),
    )
    assert result.scored[1].components == ranking_v2.V2ScoreComponents(
        edge=Decimal("1"),
        wilson=Decimal("0"),
        positive_windows=Decimal("0"),
        low_mae=Decimal("0"),
        low_stop_rate=Decimal("0"),
        context=Decimal("0"),
        setup_quality=Decimal("0"),
    )


def test_v2_keeps_one_profile_per_structure_and_never_fills_to_three() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    same_structure_low = _plan(code="600001", profile_index=0)
    same_structure_high = _plan(code="600001", profile_index=1)
    only_other_structure = _plan(code="600002", profile_index=2)
    calibration_values = (
        _calibration(same_structure_low, expectancy="0.01"),
        _calibration(same_structure_high, expectancy="0.04"),
        _calibration(only_other_structure, expectancy="0.02"),
    )

    result = ranking_v2.rank_five_day_plans_v2(
        (
            same_structure_low,
            same_structure_high,
            only_other_structure,
        ),
        {value.key: value for value in calibration_values},
        policy=_policy("EDGE-K30-BASE"),
        daily_limit=3,
    )

    assert result.ranking.plans == (
        same_structure_high,
        only_other_structure,
    )
    assert result.ranking.rejection_counts == {
        "DUPLICATE_ACTIVE_STRUCTURE": 1,
    }
    assert tuple(value.plan for value in result.scored) == (
        same_structure_high,
        only_other_structure,
    )


def test_v2_score_ties_prefer_higher_shrunk_edge() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    edge_winner = _plan(code="600001", profile_index=0)
    rate_winner = _plan(code="600002", profile_index=1)
    calibration_values = (
        _calibration(
            edge_winner,
            expectancy="0.04",
            wilson_lower="0.40",
            positive_windows="0.50",
        ),
        _calibration(
            rate_winner,
            expectancy="0.02",
            wilson_lower="0.60",
            positive_windows="0.80",
        ),
    )

    result = ranking_v2.rank_five_day_plans_v2(
        (rate_winner, edge_winner),
        {value.key: value for value in calibration_values},
        policy=_policy("EDGE-K30-BASE"),
    )

    assert tuple(value.score for value in result.scored) == (
        Decimal("50"),
        Decimal("50"),
    )
    assert result.ranking.plans == (edge_winner, rate_winner)


def test_v2_score_and_edge_ties_prefer_higher_setup_quality() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    context_winner = _plan(
        code="600001",
        profile_index=0,
        market_status="ALLOW",
        sector_resonating=True,
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
        quality="0.50",
    )
    quality_winner = _plan(
        code="600002",
        profile_index=1,
        market_status="LIMITED",
        sector_resonating=False,
        resistance_basis="LEVEL_BELOW_2R",
        quality="0.90",
    )
    calibration_values = (
        _calibration(context_winner),
        _calibration(quality_winner),
    )

    result = ranking_v2.rank_five_day_plans_v2(
        (context_winner, quality_winner),
        {value.key: value for value in calibration_values},
        policy=_policy("EDGE-K30-BASE"),
    )

    assert tuple(value.score for value in result.scored) == (
        Decimal("50"),
        Decimal("50"),
    )
    assert result.ranking.plans == (quality_winner, context_winner)


def test_v2_remaining_ties_follow_normalized_code_and_profile() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    plan_600001_profile_a = _plan(
        code="600001.SH",
        profile_index=0,
        setup_type=SetupType.PRE_BREAKOUT,
    )
    plan_600001_profile_b = _plan(
        code="600001",
        profile_index=1,
        setup_type=SetupType.TREND_PULLBACK,
    )
    plan_600002 = _plan(code="600002", profile_index=2)
    plans = (
        plan_600002,
        plan_600001_profile_b,
        plan_600001_profile_a,
    )
    calibration_values = tuple(_calibration(value) for value in plans)
    calibrations = {value.key: value for value in calibration_values}
    policy = _policy("EDGE-K30-BASE")

    first = ranking_v2.rank_five_day_plans_v2(
        plans,
        calibrations,
        policy=policy,
    )
    second = ranking_v2.rank_five_day_plans_v2(
        tuple(reversed(plans)),
        calibrations,
        policy=policy,
    )

    expected = (
        plan_600001_profile_a,
        plan_600001_profile_b,
        plan_600002,
    )
    assert tuple(value.plan for value in first.scored) == expected
    assert tuple(value.plan for value in second.scored) == expected
    assert first == second


def test_v2_daily_limit_marks_overflow_and_zero_is_valid_abstention() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    plans = tuple(
        _plan(code=f"60000{index}", profile_index=index - 1)
        for index in range(1, 5)
    )
    calibration_values = tuple(_calibration(value) for value in plans)
    calibrations = {value.key: value for value in calibration_values}
    policy = _policy("EDGE-K30-BASE")

    top_three = ranking_v2.rank_five_day_plans_v2(
        tuple(reversed(plans)),
        calibrations,
        policy=policy,
        daily_limit=3,
    )
    abstain = ranking_v2.rank_five_day_plans_v2(
        plans,
        calibrations,
        policy=policy,
        daily_limit=0,
    )

    assert top_three.ranking.plans == plans[:3]
    assert tuple(value.selected for value in top_three.scored) == (
        True,
        True,
        True,
        False,
    )
    assert top_three.ranking.rejection_counts == {
        "DAILY_CANDIDATE_LIMIT": 1,
    }
    assert abstain.ranking.plans == ()
    assert tuple(value.selected for value in abstain.scored) == (
        False,
        False,
        False,
        False,
    )
    assert abstain.ranking.rejection_counts == {
        "DAILY_CANDIDATE_LIMIT": 4,
    }
