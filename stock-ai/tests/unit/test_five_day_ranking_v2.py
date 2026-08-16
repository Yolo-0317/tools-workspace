from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v2_report import (
    load_five_day_ranking_v2_train,
    write_five_day_ranking_v2_train,
)
from stock_ai.buy_point_selection.five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
    FiveDayExit,
    FiveDayTrade,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    SIZING_VERSION,
    build_five_day_return_profiles,
    five_day_profile_hash,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayResearchReview,
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayCalibration,
    FiveDayObservation,
    FiveDayPortfolioMetrics,
    FiveDayRanking,
    FiveDaySegmentMetrics,
    FiveDaySelectedSegment,
    FiveDaySelection,
)
from stock_ai.buy_point_selection.models import DetectedSetup, SetupType
from stock_ai.buy_point_selection.validation import ChronologicalSplit


START = date(2023, 1, 2)
PARENT_IDENTITY = "a" * 64


def _sessions(count: int) -> tuple[date, ...]:
    return tuple(START + timedelta(days=index) for index in range(count))


def _split() -> ChronologicalSplit:
    sessions = _sessions(630)
    return ChronologicalSplit(
        train=sessions[:378],
        validation=sessions[378:504],
        test=sessions[504:630],
    )


def _empty_portfolio() -> FiveDayPortfolioMetrics:
    return FiveDayPortfolioMetrics(
        accepted_trades=0,
        maximum_drawdown=Decimal("0"),
        maximum_stock_trade_share=Decimal("0"),
        maximum_stock_profit_share=Decimal("0"),
        maximum_sector_trade_share=Decimal("0"),
        maximum_sector_profit_share=Decimal("0"),
        top5_profit_share=Decimal("0"),
        qualifies=False,
        reasons=("NO_ACCEPTED_TRADES",),
    )


def _complete_review_fixture(
    observations: tuple[FiveDayObservation, ...] = (),
) -> FiveDayResearchReview:
    return FiveDayResearchReview(
        split=_split(),
        input_fingerprint="f" * 64,
        formal_rule_version="five-day-ranking-fixture-v1",
        formal_policy_hash="b" * 64,
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
        sizing_version=SIZING_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        cost_version=COST_VERSION,
        observations=observations,
        train_calibrations={},
        validation_metrics=(),
        validation_portfolio=_empty_portfolio(),
        point_in_time_complete=True,
        test_outcomes_read=False,
    )


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


def _scored(
    plan: FiveDaySignalPlan,
    *,
    rank: int,
):
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    return ranking_v2.FiveDayV2ScoredPlan(
        plan=plan,
        calibration=_calibration(plan),
        shrunk_edge=Decimal("0.01"),
        components=ranking_v2.V2ScoreComponents(
            edge=Decimal("0.5"),
            wilson=Decimal("0.5"),
            positive_windows=Decimal("0.5"),
            low_mae=Decimal("0.5"),
            low_stop_rate=Decimal("0.5"),
            context=Decimal("0.5"),
            setup_quality=Decimal("0.5"),
        ),
        score=Decimal("50"),
        rank=rank,
        selected=rank <= 3,
    )


def _observation_for_plan(
    plan: FiveDaySignalPlan,
    *,
    net_return: str,
) -> FiveDayObservation:
    resolution_date = plan.candidate.signal_date + timedelta(days=6)
    exit_value = FiveDayExit(
        planned_exit_date=resolution_date,
        actual_exit_date=resolution_date,
        price=Decimal("10.20"),
        reason=(
            "TIME_EXIT_GAIN"
            if Decimal(net_return) > 0
            else "TIME_EXIT_LOSS"
        ),
        fees=Decimal("0"),
        delayed=False,
    )
    trade = FiveDayTrade(
        profile_id=plan.profile.profile_id,
        structure_id=plan.structure_id,
        code=plan.candidate.code,
        signal_date=plan.candidate.signal_date,
        status=exit_value.reason,
        entry_date=plan.candidate.signal_date + timedelta(days=1),
        entry_price=Decimal("10.00"),
        stop_price=Decimal("9.70"),
        evaluation_target_notional=Decimal("10000"),
        evaluation_shares=1000,
        evaluation_notional=Decimal("10000"),
        entry_fees=Decimal("0"),
        exit=exit_value,
        net_pnl=Decimal(net_return) * Decimal("10000"),
        net_return=Decimal(net_return),
        mfe=Decimal("0.03"),
        mae=Decimal("0.01"),
        intraday_order_ambiguous=False,
        reasons=(),
    )
    return FiveDayObservation(plan, trade, resolution_date)


def _not_triggered_for_plan(plan: FiveDaySignalPlan) -> FiveDayObservation:
    value = _observation_for_plan(plan, net_return="0")
    return replace(
        value,
        trade=replace(
            value.trade,
            status="NOT_TRIGGERED",
            entry_date=None,
            entry_price=None,
            stop_price=None,
            evaluation_shares=0,
            evaluation_notional=Decimal("0"),
            exit=None,
            net_pnl=Decimal("0"),
            net_return=None,
            mfe=None,
            mae=None,
        ),
    )


def _pending_for_plan(plan: FiveDaySignalPlan) -> FiveDayObservation:
    value = _not_triggered_for_plan(plan)
    return replace(value, trade=replace(value.trade, status="PENDING"))


def _review_with_boundary_resolution() -> FiveDayResearchReview:
    split = _split()
    plan = _plan(
        code="600099",
        profile_index=0,
        signal_date=split.train[251],
    )
    value = _observation_for_plan(plan, net_return="0.01")
    boundary = split.train[252]
    boundary_exit = replace(
        value.trade.exit,
        planned_exit_date=boundary,
        actual_exit_date=boundary,
    )
    return _complete_review_fixture(
        (
            replace(
                value,
                trade=replace(value.trade, exit=boundary_exit),
                resolution_date=boundary,
            ),
        )
    )


def _review_with_incomplete_train_selection() -> FiveDayResearchReview:
    split = _split()
    calibration = tuple(
        _observation_for_plan(
            _plan(
                code=f"61{index:04d}",
                profile_index=0,
                signal_date=split.train[index],
            ),
            net_return="0.02" if index < 20 else "-0.01",
        )
        for index in range(30)
    )
    pending = _pending_for_plan(
        _plan(
            code="620001",
            profile_index=0,
            signal_date=split.train[252],
        )
    )
    later = (
        _observation_for_plan(
            _plan(
                code="630001",
                profile_index=0,
                signal_date=split.validation[0],
            ),
            net_return="0.05",
        ),
        _observation_for_plan(
            _plan(
                code="630002",
                profile_index=0,
                signal_date=split.test[0],
            ),
            net_return="0.05",
        ),
    )
    return _complete_review_fixture((*calibration, pending, *later))


def _settled_observation(
    plan: FiveDaySignalPlan,
    *,
    net_return: str,
) -> FiveDayObservation:
    value = _observation_for_plan(plan, net_return=net_return)
    settlement = plan.candidate.signal_date + timedelta(days=1)
    return replace(
        value,
        trade=replace(
            value.trade,
            exit=replace(
                value.trade.exit,
                planned_exit_date=settlement,
                actual_exit_date=settlement,
            ),
        ),
        resolution_date=settlement,
    )


def _qualifying_train_review() -> FiveDayResearchReview:
    split = _split()
    calibration = tuple(
        _settled_observation(
            _plan(
                code=f"70{index:04d}",
                profile_index=0,
                signal_date=split.train[index],
            ),
            net_return="0.02" if index < 20 else "-0.01",
        )
        for index in range(30)
    )
    rank_returns = (
        "0.012",
        "0.008",
        "-0.002",
        "0.003",
        "0.001",
        "0.0005",
    )
    evaluation: list[FiveDayObservation] = []
    for fold_index, start_index in ((1, 252), (2, 315)):
        for day_index in range(8):
            signal_date = split.train[start_index + day_index]
            evaluation.extend(
                _settled_observation(
                    _plan(
                        code=f"7{fold_index}{day_index:02d}{rank:02d}",
                        profile_index=0,
                        signal_date=signal_date,
                    ),
                    net_return=rank_returns[rank - 1],
                )
                for rank in range(1, 7)
            )
    return _complete_review_fixture((*calibration, *evaluation))


def _train_artifact(
    research: FiveDayResearchReview,
    tmp_path,
):
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    review = ranking_v2.build_five_day_ranking_v2_train_review(
        research,
        parent_research_identity=PARENT_IDENTITY,
    )
    return load_five_day_ranking_v2_train(
        write_five_day_ranking_v2_train(review, tmp_path),
        expected_parent_research_identity=PARENT_IDENTITY,
    )


def _validation_research_fixture() -> FiveDayResearchReview:
    research = _qualifying_train_review()
    validation = _settled_observation(
        _plan(
            code="800001",
            profile_index=0,
            signal_date=research.split.validation[0],
        ),
        net_return="0.01",
    )
    return replace(
        research,
        observations=(*research.observations, validation),
    )


def _bands(
    *,
    rank1: str,
    rank2_3: str,
    rank4_5: str,
    rank6: str,
    rank1_n: int = 15,
):
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    return (
        ranking_v2.V2RankBandMetrics(
            "RANK_1", rank1_n, Decimal(rank1)
        ),
        ranking_v2.V2RankBandMetrics(
            "RANK_2_3", 15, Decimal(rank2_3)
        ),
        ranking_v2.V2RankBandMetrics(
            "RANK_4_5", 15, Decimal(rank4_5)
        ),
        ranking_v2.V2RankBandMetrics(
            "RANK_6_PLUS", 15, Decimal(rank6)
        ),
    )


def _segment(
    *,
    samples: int,
    expectancy: str,
    profit_factor: str | None = "1.11",
    incomplete: bool = False,
    maximum_drawdown: str = "0.05",
) -> FiveDaySelectedSegment:
    metrics = FiveDaySegmentMetrics(
        profile_id="V2",
        segment="TRAIN",
        triggered_resolved=samples,
        net_expectancy=Decimal(expectancy),
        profit_factor=(
            Decimal(profit_factor) if profit_factor is not None else None
        ),
        profitable_wilson_lower=Decimal("0.50"),
        stop_rate=Decimal("0.20"),
        positive_window_ratio=Decimal("0.60"),
        maximum_drawdown=Decimal(maximum_drawdown),
        qualifies=True,
        reasons=(),
    )
    return FiveDaySelectedSegment(
        metric_version="selected-portfolio-v2",
        metrics=metrics,
        portfolio=FiveDayPortfolioMetrics(
            accepted_trades=samples,
            maximum_drawdown=Decimal(maximum_drawdown),
            maximum_stock_trade_share=Decimal("0.10"),
            maximum_stock_profit_share=Decimal("0.10"),
            maximum_sector_trade_share=Decimal("0.20"),
            maximum_sector_profit_share=Decimal("0.20"),
            top5_profit_share=Decimal("0.30"),
            qualifies=True,
            reasons=(),
        ),
        selection=FiveDaySelection(
            ranking=FiveDayRanking(plans=(), rejection_counts={}),
            selected_observations=(),
            admitted=(),
            funnel_counts={},
            incomplete=incomplete,
        ),
    )


def _passing_monotonicity():
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    return ranking_v2.assess_v2_rank_monotonicity(
        _bands(
            rank1="0.006",
            rank2_3="0.005",
            rank4_5="0.004",
            rank6="0.002",
        ),
        admitted_top3_expectancy=Decimal("0.003"),
    )


def _qualifying_assessment_inputs(
    *,
    fold1_samples: int = 15,
    fold2_samples: int = 15,
    combined_samples: int = 40,
    fold1_expectancy: str = "0.001",
    fold2_expectancy: str = "0.002",
    combined_expectancy: str = "0.003",
    combined_profit_factor: str | None = "1.11",
    fold1_incomplete: bool = False,
    fold2_incomplete: bool = False,
    combined_incomplete: bool = False,
) -> dict[str, object]:
    return {
        "policy": _policy("EDGE-K30-BASE"),
        "fold1": _segment(
            samples=fold1_samples,
            expectancy=fold1_expectancy,
            incomplete=fold1_incomplete,
        ),
        "fold2": _segment(
            samples=fold2_samples,
            expectancy=fold2_expectancy,
            incomplete=fold2_incomplete,
        ),
        "combined": _segment(
            samples=combined_samples,
            expectancy=combined_expectancy,
            profit_factor=combined_profit_factor,
            incomplete=combined_incomplete,
        ),
        "monotonicity": _passing_monotonicity(),
    }


def _assessment(
    *,
    policy_id: str,
    fold1_expectancy: str,
    fold2_expectancy: str,
    combined_expectancy: str,
    combined_samples: int = 40,
    maximum_drawdown: str = "0.05",
):
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    return ranking_v2.assess_five_day_v2_policy(
        policy=_policy(policy_id),
        fold1=_segment(samples=20, expectancy=fold1_expectancy),
        fold2=_segment(samples=20, expectancy=fold2_expectancy),
        combined=_segment(
            samples=combined_samples,
            expectancy=combined_expectancy,
            maximum_drawdown=maximum_drawdown,
        ),
        monotonicity=_passing_monotonicity(),
    )


def test_monotonicity_accepts_the_exact_two_bps_tolerance() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.assess_v2_rank_monotonicity(
        _bands(
            rank1="0.004",
            rank2_3="0.006",
            rank4_5="0.008",
            rank6="0",
        ),
        admitted_top3_expectancy=Decimal("0.003"),
    )

    assert result.qualifies is True
    assert result.reasons == ()


def test_monotonicity_fails_small_bands_and_top3_below_rank6() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.assess_v2_rank_monotonicity(
        _bands(
            rank1="0.01",
            rank2_3="0",
            rank4_5="-0.01",
            rank6="0.004",
            rank1_n=14,
        ),
        admitted_top3_expectancy=Decimal("0.003"),
    )

    assert result.qualifies is False
    assert result.reasons == (
        "RANK_BAND_SAMPLES_TOO_LOW",
        "TOP3_NOT_ABOVE_RANK6_PLUS",
    )


def test_rank_bands_use_triggered_completed_trace_not_admission() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    plan_rank1 = _plan(code="600001", profile_index=0)
    plan_rank4 = _plan(code="600002", profile_index=1)
    plan_rank6 = _plan(code="600003", profile_index=2)

    bands = ranking_v2.build_v2_rank_bands(
        (
            _scored(plan_rank1, rank=1),
            _scored(plan_rank4, rank=4),
            _scored(plan_rank6, rank=6),
        ),
        (
            _observation_for_plan(plan_rank1, net_return="0.01"),
            _not_triggered_for_plan(plan_rank4),
            _observation_for_plan(plan_rank6, net_return="-0.01"),
        ),
    )

    assert tuple(value.triggered_completed for value in bands) == (1, 0, 0, 1)
    assert bands[0].net_expectancy == Decimal("0.01")
    assert bands[3].net_expectancy == Decimal("-0.01")


def test_policy_requires_both_positive_folds_and_combined_edge() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.assess_five_day_v2_policy(
        policy=_policy("EDGE-K30-BASE"),
        fold1=_segment(samples=15, expectancy="0.001"),
        fold2=_segment(samples=25, expectancy="0"),
        combined=_segment(
            samples=40,
            expectancy="0.003",
            profit_factor="1.11",
        ),
        monotonicity=_passing_monotonicity(),
    )

    assert result.qualifies is False
    assert "FOLD_2_NON_POSITIVE_EXPECTANCY" in result.reasons


@pytest.mark.parametrize(
    ("overrides", "reason"),
    (
        ({"fold1_incomplete": True}, "FOLD_1_INCOMPLETE"),
        ({"fold2_incomplete": True}, "FOLD_2_INCOMPLETE"),
        ({"combined_incomplete": True}, "COMBINED_INCOMPLETE"),
        ({"fold1_samples": 14}, "FOLD_1_SAMPLES_TOO_LOW"),
        ({"fold2_samples": 14}, "FOLD_2_SAMPLES_TOO_LOW"),
        ({"combined_samples": 39}, "COMBINED_SAMPLES_TOO_LOW"),
        ({"combined_expectancy": "0.0029"}, "COMBINED_EDGE_TOO_LOW"),
        (
            {"combined_profit_factor": "1.10"},
            "PROFIT_FACTOR_NOT_ABOVE_1_10",
        ),
        (
            {"combined_profit_factor": None},
            "PROFIT_FACTOR_NOT_ABOVE_1_10",
        ),
    ),
)
def test_v2_policy_qualification_boundaries(
    overrides: dict[str, object],
    reason: str,
) -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.assess_five_day_v2_policy(
        **_qualifying_assessment_inputs(**overrides)
    )

    assert result.qualifies is False
    assert reason in result.reasons


def test_v2_policy_accepts_inclusive_and_exclusive_boundaries() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.assess_five_day_v2_policy(
        **_qualifying_assessment_inputs(
            fold1_samples=15,
            fold2_samples=15,
            combined_samples=40,
            combined_expectancy="0.0030",
            combined_profit_factor="1.1001",
        )
    )

    assert result.qualifies is True
    assert result.reasons == ()


def test_winner_maximizes_worst_fold_before_combined_expectancy() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    high_combined = _assessment(
        policy_id="EDGE-K30-BASE",
        fold1_expectancy="0.001",
        fold2_expectancy="0.004",
        combined_expectancy="0.005",
    )
    high_worst_fold = _assessment(
        policy_id="BALANCED-K30-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
    )

    winner = ranking_v2.select_five_day_v2_winner(
        (high_combined, high_worst_fold)
    )

    assert winner is not None
    assert winner.policy.policy_id == "BALANCED-K30-BASE"


def test_winner_uses_combined_expectancy_after_equal_worst_fold() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    lower_combined = _assessment(
        policy_id="EDGE-K30-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
    )
    higher_combined = _assessment(
        policy_id="EDGE-K60-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.005",
    )

    winner = ranking_v2.select_five_day_v2_winner(
        (lower_combined, higher_combined)
    )

    assert winner is not None
    assert winner.policy.policy_id == "EDGE-K60-BASE"


def test_winner_uses_samples_drawdown_then_registered_policy_order() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    fewer_samples = _assessment(
        policy_id="EDGE-K30-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
        combined_samples=40,
        maximum_drawdown="0.07",
    )
    more_samples = _assessment(
        policy_id="EDGE-K60-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
        combined_samples=41,
        maximum_drawdown="0.09",
    )
    lower_drawdown = _assessment(
        policy_id="BALANCED-K60-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
        combined_samples=41,
        maximum_drawdown="0.08",
    )
    later_policy = _assessment(
        policy_id="DOWNSIDE-K60-BASE",
        fold1_expectancy="0.002",
        fold2_expectancy="0.003",
        combined_expectancy="0.004",
        combined_samples=41,
        maximum_drawdown="0.08",
    )

    winner = ranking_v2.select_five_day_v2_winner(
        (fewer_samples, later_policy, lower_drawdown, more_samples)
    )

    assert winner is not None
    assert winner.policy.policy_id == "BALANCED-K60-BASE"


def test_winner_returns_none_instead_of_unqualified_fallback() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    unqualified = ranking_v2.assess_five_day_v2_policy(
        **_qualifying_assessment_inputs(fold1_expectancy="0")
    )

    winner = ranking_v2.select_five_day_v2_winner((unqualified,))

    assert unqualified.qualifies is False
    assert winner is None


def test_v2_train_review_uses_exact_folds_and_all_twelve_policies() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.build_five_day_ranking_v2_train_review(
        _complete_review_fixture(),
        parent_research_identity=PARENT_IDENTITY,
    )

    assert tuple(len(value.calibration_dates) for value in result.folds) == (
        252,
        315,
    )
    assert tuple(len(value.evaluation_dates) for value in result.folds) == (
        63,
        63,
    )
    assert len(result.assessments) == 12
    assert len(result.variants) == 12 * 3 * 3
    assert result.policy_set_hash == ranking_v2.five_day_v2_policy_set_hash()
    assert result.validation_outcomes_read is False
    assert result.test_outcomes_read is False


def test_v2_train_excludes_calibration_outcome_at_fold_start() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.build_five_day_ranking_v2_train_review(
        _review_with_boundary_resolution(),
        parent_research_identity=PARENT_IDENTITY,
    )

    assert result.folds[0].excluded_unresolved_calibration_rows == 1
    assert (
        result.folds[0].calibration_data_end
        < result.folds[0].evaluation_dates[0]
    )


def test_v2_train_records_no_candidate_without_validation_eligibility() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.build_five_day_ranking_v2_train_review(
        _complete_review_fixture(),
        parent_research_identity=PARENT_IDENTITY,
    )

    assert result.winner_policy_id is None
    assert result.status == "NO_TRAIN_CANDIDATE"
    assert result.validation_eligible is False
    assert all(not value.qualifies for value in result.assessments)


def test_v2_train_propagates_incomplete_and_never_reads_later_splits() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    research = _review_with_incomplete_train_selection()

    result = ranking_v2.build_five_day_ranking_v2_train_review(
        research,
        parent_research_identity=PARENT_IDENTITY,
    )

    affected = next(
        value
        for value in result.assessments
        if value.policy.policy_id == "EDGE-K30-BASE"
    )
    later_dates = frozenset((*research.split.validation, *research.split.test))
    assert affected.qualifies is False
    assert "FOLD_1_INCOMPLETE" in affected.reasons
    assert "COMBINED_INCOMPLETE" in affected.reasons
    assert all(
        row.plan.candidate.signal_date not in later_dates
        for variant in result.variants
        for row in variant.scored
    )


def test_v2_train_marks_a_qualified_winner_validation_only() -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )

    result = ranking_v2.build_five_day_ranking_v2_train_review(
        _qualifying_train_review(),
        parent_research_identity=PARENT_IDENTITY,
    )

    assert result.winner_policy_id == "EDGE-K30-BASE"
    assert result.winner_train_samples == 48
    assert result.status == "TRAIN_CANDIDATE_SELECTED"
    assert result.validation_eligible is True
    assert result.promotion_eligible is False
    assert result.trade_permission == "NO-TRADE"


def test_v2_validation_requires_exactly_one_frozen_train_winner(
    tmp_path,
) -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    research = _complete_review_fixture()
    train = _train_artifact(research, tmp_path)

    with pytest.raises(ValueError, match="unique train winner"):
        ranking_v2.build_five_day_ranking_v2_validation_review(
            research,
            train,
            parent_research_identity=PARENT_IDENTITY,
        )


def test_v2_validation_rejects_changed_winner_policy_before_outcomes(
    tmp_path,
) -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    research = _qualifying_train_review()
    train = _train_artifact(research, tmp_path)
    changed = replace(
        train,
        winner_policy_id="DOWNSIDE-K60-STABLE_NEGATIVE",
    )

    with pytest.raises(ValueError, match="winner policy or lineage"):
        ranking_v2.build_five_day_ranking_v2_validation_review(
            research,
            changed,
            parent_research_identity=PARENT_IDENTITY,
        )


def test_v2_validation_evaluates_only_the_locked_winner_validation_only(
    tmp_path,
) -> None:
    ranking_v2 = import_module(
        "stock_ai.buy_point_selection.five_day_ranking_v2"
    )
    research = _validation_research_fixture()
    train = _train_artifact(research, tmp_path)

    result = ranking_v2.build_five_day_ranking_v2_validation_review(
        research,
        train,
        parent_research_identity=PARENT_IDENTITY,
    )

    assert result.winner_policy_id == "EDGE-K30-BASE"
    assert result.validation_dates == research.split.validation
    assert len(result.segment.selection.ranking.plans) == 1
    assert result.segment.selection.ranking.plans[0].candidate.code == "800001"
    assert result.qualifies_for_test_design is False
    assert "SEGMENT_SAMPLES_TOO_LOW" in result.reasons
    assert "TRAIN_VALIDATION_SAMPLES_TOO_LOW" in result.reasons
    assert result.validation_outcomes_read is True
    assert result.test_outcomes_read is False
    assert result.promotion_eligible is False
    assert result.trade_permission == "NO-TRADE"


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
