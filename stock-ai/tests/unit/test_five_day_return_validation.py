from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection import (
    five_day_return_validation as validation,
)
from stock_ai.buy_point_selection.five_day_return_execution import (
    FiveDayExit,
    FiveDayTrade,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    build_five_day_return_profiles,
    five_day_profile_hash,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayCalibration,
    FiveDayObservation,
    assess_five_day_portfolio,
    assess_five_day_segment,
    build_five_day_calibrations,
    build_five_day_portfolio_metrics,
    evaluate_selected_five_day_segment,
    evaluate_frozen_test,
    evaluate_validation_freeze,
    rank_five_day_plans,
    resolve_five_day_calibration,
    select_five_day_portfolio,
)
from stock_ai.buy_point_selection.models import DetectedSetup, SetupType
from stock_ai.buy_point_selection.validation import chronological_split


PROFILE = "BREAKOUT_TRIGGER__FIXED_3_PERCENT"
START = date(2023, 1, 2)


def _trading_dates(count: int) -> tuple[date, ...]:
    return tuple(START + timedelta(days=index) for index in range(count))


def _plan(
    signal_date: date,
    *,
    code: str = "600001",
    profile_index: int = 0,
    setup_type: SetupType = SetupType.PRE_BREAKOUT,
    market_status: str = "ALLOW",
    sector_resonating: bool = True,
) -> FiveDaySignalPlan:
    profile = build_five_day_return_profiles()[profile_index]
    setup = DetectedSetup(
        code=code,
        setup_type=setup_type,
        analysis_date=signal_date,
        structure_start=signal_date - timedelta(days=10),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.50"),
        quality=Decimal("0.80"),
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
        resistance_basis="NO_RELIABLE_LEVEL",
        resistance_effective_r=None,
    )


def _observation(
    signal_date: date,
    *,
    market_status: str = "ALLOW",
    sector_resonating: bool = True,
    net_return: str = "0.02",
) -> FiveDayObservation:
    plan = _plan(
        signal_date,
        market_status=market_status,
        sector_resonating=sector_resonating,
    )
    exit_value = FiveDayExit(
        planned_exit_date=signal_date + timedelta(days=6),
        actual_exit_date=signal_date + timedelta(days=6),
        price=Decimal("10.20"),
        reason="TIME_EXIT_GAIN",
        fees=Decimal("0"),
        delayed=False,
    )
    trade = FiveDayTrade(
        profile_id=plan.profile.profile_id,
        structure_id=plan.structure_id,
        code=plan.candidate.code,
        signal_date=signal_date,
        status="TIME_EXIT_GAIN" if Decimal(net_return) > 0 else "TIME_EXIT_LOSS",
        entry_date=signal_date + timedelta(days=1),
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
    return FiveDayObservation(plan, trade, exit_value.actual_exit_date)


def _observation_for_plan(
    plan: FiveDaySignalPlan,
    *,
    net_return: str,
) -> FiveDayObservation:
    template = _observation(plan.candidate.signal_date, net_return=net_return)
    return replace(
        template,
        plan=plan,
        trade=replace(
            template.trade,
            profile_id=plan.profile.profile_id,
            structure_id=plan.structure_id,
            code=plan.candidate.code,
            signal_date=plan.candidate.signal_date,
        ),
    )


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


def test_split_is_existing_sixty_twenty_twenty_contract() -> None:
    split = chronological_split(_trading_dates(630))

    assert (len(split.train), len(split.validation), len(split.test)) == (
        378,
        126,
        126,
    )


def test_calibration_falls_back_without_merging_samples() -> None:
    dates = _trading_dates(630)[:66]
    observations = tuple(
        _observation(value, market_status="ALLOW", sector_resonating=True)
        for value in dates[:29]
    ) + (
        _observation(
            dates[29], market_status="ALLOW", sector_resonating=False
        ),
    ) + tuple(
        _observation(
            value,
            market_status="LIMITED",
            sector_resonating=False,
        )
        for value in dates[30:60]
    )

    values = build_five_day_calibrations(
        observations,
        trading_dates=dates,
    )
    resolved = resolve_five_day_calibration(
        values,
        profile_id=PROFILE,
        setup_type=SetupType.PRE_BREAKOUT,
        market_status="ALLOW",
        sector_resonating=True,
    )

    assert values[f"{PROFILE}|PRE_BREAKOUT|ALLOW|True"].triggered_resolved == 29
    assert resolved is not None
    assert resolved.key == f"{PROFILE}|PRE_BREAKOUT|ALLOW|*"
    assert resolved.triggered_resolved == 30
    assert values[f"{PROFILE}|PRE_BREAKOUT|*|*"].triggered_resolved == 60


def test_non_resolved_rows_count_as_plans_but_not_resolved_triggers() -> None:
    observation = _observation(START)
    unresolved = replace(
        observation,
        trade=replace(
            observation.trade,
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

    values = build_five_day_calibrations(
        (observation, unresolved),
        trading_dates=_trading_dates(63),
    )
    calibration = values[f"{PROFILE}|PRE_BREAKOUT|ALLOW|True"]

    assert calibration.total_plans == 2
    assert calibration.triggered_resolved == 1


def test_calibration_does_not_use_an_outcome_resolved_after_its_cutoff() -> None:
    observation = _observation(START)
    future = replace(
        observation,
        resolution_date=START + timedelta(days=64),
    )

    values = build_five_day_calibrations(
        (future,),
        trading_dates=_trading_dates(63),
    )
    calibration = values[f"{PROFILE}|PRE_BREAKOUT|ALLOW|True"]

    assert calibration.total_plans == 1
    assert calibration.triggered_resolved == 0


def _calibration(
    plan: FiveDaySignalPlan,
    *,
    expectancy: str = "0.02",
    wilson_lower: str = "0.50",
    mae_p75: str = "0.01",
    stop_rate: str = "0.20",
) -> FiveDayCalibration:
    return FiveDayCalibration(
        key=(
            f"{plan.profile.profile_id}|"
            f"{plan.candidate.setup.setup_type.value}|ALLOW|True"
        ),
        profile_id=plan.profile.profile_id,
        setup_type=plan.candidate.setup.setup_type,
        market_status="ALLOW",
        sector_resonating=True,
        data_end=plan.candidate.signal_date - timedelta(days=1),
        total_plans=30,
        triggered_resolved=30,
        positive_net=20,
        profitable_rate=Decimal("0.6666666667"),
        profitable_interval=(Decimal(wilson_lower), Decimal("0.80")),
        net_expectancy=Decimal(expectancy),
        profit_factor=Decimal("1.50"),
        stop_rate=Decimal(stop_rate),
        mae_p75=Decimal(mae_p75),
        positive_window_ratio=Decimal("0.70"),
    )


def test_ranking_uses_the_literal_frozen_key() -> None:
    base = _plan(START)
    limited = replace(
        _plan(START, code="600002"),
        candidate=replace(
            _plan(START, code="600002").candidate,
            market_status="LIMITED",
        ),
    )
    at_two_r = replace(
        _plan(START, code="600003"),
        resistance_basis="LEVEL_AT_OR_ABOVE_2R",
        resistance_effective_r=Decimal("2"),
    )
    lower_expectancy = _plan(START, code="600004", profile_index=2)
    calibrations = {
        _calibration(base).key: _calibration(base),
        (
            f"{limited.profile.profile_id}|PRE_BREAKOUT|LIMITED|True"
        ): replace(
            _calibration(limited),
            key=f"{limited.profile.profile_id}|PRE_BREAKOUT|LIMITED|True",
            market_status="LIMITED",
        ),
        _calibration(at_two_r).key: _calibration(at_two_r),
        _calibration(lower_expectancy).key: _calibration(
            lower_expectancy, expectancy="0.01"
        ),
    }

    result = rank_five_day_plans(
        (limited, base, lower_expectancy, at_two_r),
        calibrations,
    )

    assert tuple(value.candidate.code for value in result.plans) == (
        "600003",
        "600001",
        "600002",
    )
    assert result.rejection_counts == {"DAILY_CANDIDATE_LIMIT": 1}


def test_ranking_deduplicates_profiles_for_the_same_active_structure() -> None:
    fixed = _plan(START, profile_index=0)
    structure = _plan(START, profile_index=1)
    structure = replace(
        structure,
        candidate=fixed.candidate,
        structure_id="profile-specific-structure",
    )
    calibrations = {
        _calibration(fixed).key: _calibration(fixed, expectancy="0.01"),
        _calibration(structure).key: _calibration(
            structure, expectancy="0.02"
        ),
    }

    result = rank_five_day_plans((fixed, structure), calibrations)

    assert tuple(value.profile.profile_id for value in result.plans) == (
        "BREAKOUT_TRIGGER__STRUCTURE_ATR",
    )
    assert result.rejection_counts == {"DUPLICATE_ACTIVE_STRUCTURE": 1}


def test_ranking_excludes_existing_structures_and_missing_calibration() -> None:
    existing = _plan(START)
    missing = _plan(START, code="600002")

    result = rank_five_day_plans(
        (existing, missing),
        {},
        active_structure_ids=frozenset((existing.structure_id,)),
    )

    assert result.plans == ()
    assert result.rejection_counts == {
        "EXISTING_ACTIVE_STRUCTURE": 1,
        "INSUFFICIENT_CALIBRATION": 1,
    }


def test_ranking_rejects_a_calibration_not_frozen_before_the_signal() -> None:
    plan = _plan(START)
    calibration = replace(_calibration(plan), data_end=START)

    result = rank_five_day_plans(
        (plan,),
        {calibration.key: calibration},
    )

    assert result.plans == ()
    assert result.rejection_counts == {
        "CALIBRATION_NOT_POINT_IN_TIME": 1,
    }


def test_selection_trace_does_not_backfill_daily_overflow() -> None:
    plans = tuple(_plan(START, code=f"60000{index}") for index in range(1, 5))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    first = _observation_for_plan(plans[0], net_return="0.02")
    not_triggered = _not_triggered_for_plan(plans[1])
    third = _observation_for_plan(plans[2], net_return="0.01")
    overflow = _observation_for_plan(plans[3], net_return="0.99")

    result = select_five_day_portfolio(
        plans,
        (first, not_triggered, third, overflow),
        calibrations,
        daily_limit=3,
        capacity=3,
    )

    assert tuple((row.rank, row.selected) for row in result.ranking.ranked) == (
        (1, True),
        (2, True),
        (3, True),
        (4, False),
    )
    assert tuple(row.plan.candidate.code for row in result.admitted) == (
        "600001",
        "600003",
    )
    assert result.funnel_counts == {
        "ADMITTED_TRADES": 2,
        "DAILY_CANDIDATE_LIMIT": 1,
        "NOT_TRIGGERED": 1,
        "SELECTED_PLANS": 3,
    }
    assert overflow not in result.admitted


def test_admit_precomputed_ranking_matches_v1_selection() -> None:
    plans = tuple(
        _plan(START, code=f"60000{index}") for index in range(1, 5)
    )
    calibrations = {
        _calibration(plan).key: _calibration(plan) for plan in plans
    }
    observations = (
        _observation_for_plan(plans[0], net_return="0.02"),
        _not_triggered_for_plan(plans[1]),
        _observation_for_plan(plans[2], net_return="-0.01"),
        _observation_for_plan(plans[3], net_return="0.50"),
    )
    ranking = rank_five_day_plans(plans, calibrations, daily_limit=3)

    extracted = validation.admit_five_day_ranking(
        ranking,
        observations,
        capacity=3,
    )
    existing = select_five_day_portfolio(
        plans,
        observations,
        calibrations,
        daily_limit=3,
        capacity=3,
    )

    assert extracted == existing
    assert extracted.funnel_counts["ADMITTED_TRADES"] == 2
    assert plans[3] not in extracted.ranking.plans


def _selected_fixture_segment(
    observations: tuple[FiveDayObservation, ...],
    calibrations: dict[str, FiveDayCalibration],
):
    return evaluate_selected_five_day_segment(
        profile_id=PROFILE,
        segment="train-diagnostic",
        observations=observations,
        trading_dates=_trading_dates(63),
        ranking_calibrations=calibrations,
        daily_limit=3,
        capacity=3,
        cumulative_samples=len(observations),
        required_samples=1,
        required_cumulative_samples=1,
    )


def test_selected_metrics_ignore_daily_overflow_losses() -> None:
    plans = tuple(_plan(START, code=f"60000{index}") for index in range(1, 5))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    observations = tuple(
        _observation_for_plan(
            plan,
            net_return="0.01" if index < 3 else "-0.99",
        )
        for index, plan in enumerate(plans)
    )

    value = _selected_fixture_segment(observations, calibrations)

    assert value.metrics.triggered_resolved == 3
    assert value.metrics.net_expectancy == Decimal("0.01")
    assert value.selection.funnel_counts["DAILY_CANDIDATE_LIMIT"] == 1


def test_selected_metrics_include_an_admitted_loss() -> None:
    plans = tuple(_plan(START, code=f"60000{index}") for index in range(1, 4))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    winning = tuple(
        _observation_for_plan(plan, net_return="0.01") for plan in plans
    )
    losing = (
        *winning[:2],
        _observation_for_plan(plans[2], net_return="-0.03"),
    )

    before = _selected_fixture_segment(winning, calibrations).metrics
    after = _selected_fixture_segment(losing, calibrations).metrics

    assert before.net_expectancy == Decimal("0.01")
    assert after.net_expectancy == Decimal(
        "-0.003333333333333333333333333333"
    )
    assert after.profit_factor == Decimal(
        "0.6666666666666666666666666667"
    )


def test_selected_metrics_exclude_nontrades_and_capacity_rejections() -> None:
    plans = tuple(_plan(START, code=f"60000{index}") for index in range(1, 5))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    observations = (
        _observation_for_plan(plans[0], net_return="0.01"),
        _not_triggered_for_plan(plans[1]),
        _pending_for_plan(plans[2]),
        _observation_for_plan(plans[3], net_return="0.99"),
    )

    value = evaluate_selected_five_day_segment(
        profile_id=PROFILE,
        segment="train-diagnostic",
        observations=observations,
        trading_dates=_trading_dates(63),
        ranking_calibrations=calibrations,
        daily_limit=4,
        capacity=1,
        cumulative_samples=1,
        required_samples=1,
        required_cumulative_samples=1,
    )

    assert value.metrics.triggered_resolved == 1
    assert value.selection.funnel_counts["NOT_TRIGGERED"] == 1
    assert value.selection.funnel_counts["PENDING"] == 1
    assert value.selection.funnel_counts["PORTFOLIO_CAPACITY"] == 1
    assert value.selection.incomplete


def test_pending_selection_prevents_numeric_qualification() -> None:
    plans = tuple(_plan(START, code=f"6000{index:02d}") for index in range(1, 10))
    calibrations = {_calibration(plan).key: _calibration(plan) for plan in plans}
    completed = tuple(
        _observation_for_plan(
            plan,
            net_return="0.01" if index < 7 else "-0.01",
        )
        for index, plan in enumerate(plans[:8])
    )
    observations = (*completed, _pending_for_plan(plans[8]))

    value = evaluate_selected_five_day_segment(
        profile_id=PROFILE,
        segment="train-diagnostic",
        observations=observations,
        trading_dates=_trading_dates(63),
        ranking_calibrations=calibrations,
        daily_limit=9,
        capacity=8,
        cumulative_samples=8,
        required_samples=1,
        required_cumulative_samples=1,
    )

    assert value.metrics.net_expectancy == Decimal("0.0075")
    assert value.metrics.profit_factor == Decimal("7")
    assert not value.metrics.qualifies
    assert value.metrics.reasons == ("SELECTION_INCOMPLETE",)


@pytest.mark.parametrize(
    ("field", "passing", "failing", "reason"),
    (
        ("net_expectancy", "0.0001", "0", "NON_POSITIVE_EXPECTANCY"),
        ("profit_factor", "1.1001", "1.10", "PROFIT_FACTOR_TOO_LOW"),
        (
            "profitable_wilson_lower",
            "0.45",
            "0.4499",
            "WILSON_LOWER_TOO_LOW",
        ),
        ("stop_rate", "0.40", "0.4001", "STOP_RATE_TOO_HIGH"),
        (
            "positive_window_ratio",
            "0.60",
            "0.5999",
            "POSITIVE_WINDOW_RATIO_TOO_LOW",
        ),
        (
            "maximum_drawdown",
            "0.10",
            "0.1001",
            "MAXIMUM_DRAWDOWN_TOO_HIGH",
        ),
    ),
)
def test_segment_metric_boundaries_are_exact(
    field: str,
    passing: str,
    failing: str,
    reason: str,
) -> None:
    values: dict[str, Decimal | int] = {
        "triggered_resolved": 30,
        "net_expectancy": Decimal("0.01"),
        "profit_factor": Decimal("1.50"),
        "profitable_wilson_lower": Decimal("0.50"),
        "stop_rate": Decimal("0.20"),
        "positive_window_ratio": Decimal("0.70"),
        "maximum_drawdown": Decimal("0.05"),
    }
    values[field] = Decimal(passing)
    passed = assess_five_day_segment(
        profile_id=PROFILE,
        segment="validation",
        required_samples=30,
        cumulative_samples=70,
        required_cumulative_samples=70,
        **values,
    )
    values[field] = Decimal(failing)
    failed = assess_five_day_segment(
        profile_id=PROFILE,
        segment="validation",
        required_samples=30,
        cumulative_samples=70,
        required_cumulative_samples=70,
        **values,
    )

    assert passed.qualifies
    assert reason not in passed.reasons
    assert not failed.qualifies
    assert reason in failed.reasons


@pytest.mark.parametrize(
    ("samples", "cumulative", "required_cumulative", "reason"),
    (
        (29, 70, 70, "SEGMENT_SAMPLES_TOO_LOW"),
        (30, 69, 70, "TRAIN_VALIDATION_SAMPLES_TOO_LOW"),
        (30, 99, 100, "TOTAL_SAMPLES_TOO_LOW"),
    ),
)
def test_sample_boundaries_fail_immediately_below_the_minimum(
    samples: int,
    cumulative: int,
    required_cumulative: int,
    reason: str,
) -> None:
    segment = "validation" if required_cumulative == 70 else "test"
    result = assess_five_day_segment(
        profile_id=PROFILE,
        segment=segment,
        triggered_resolved=samples,
        net_expectancy=Decimal("0.01"),
        profit_factor=Decimal("1.50"),
        profitable_wilson_lower=Decimal("0.50"),
        stop_rate=Decimal("0.20"),
        positive_window_ratio=Decimal("0.70"),
        maximum_drawdown=Decimal("0.05"),
        required_samples=30,
        cumulative_samples=cumulative,
        required_cumulative_samples=required_cumulative,
    )

    assert not result.qualifies
    assert reason in result.reasons


def test_all_sample_count_boundaries_pass_at_the_exact_minimum() -> None:
    validation = assess_five_day_segment(
        profile_id=PROFILE,
        segment="validation",
        triggered_resolved=30,
        net_expectancy=Decimal("0.01"),
        profit_factor=Decimal("1.50"),
        profitable_wilson_lower=Decimal("0.50"),
        stop_rate=Decimal("0.20"),
        positive_window_ratio=Decimal("0.60"),
        maximum_drawdown=Decimal("0.10"),
        required_samples=30,
        cumulative_samples=70,
        required_cumulative_samples=70,
    )
    test = replace(
        validation,
        segment="test",
        qualifies=True,
        reasons=(),
    )
    test = assess_five_day_segment(
        profile_id=test.profile_id,
        segment=test.segment,
        triggered_resolved=test.triggered_resolved,
        net_expectancy=test.net_expectancy,
        profit_factor=test.profit_factor,
        profitable_wilson_lower=test.profitable_wilson_lower,
        stop_rate=test.stop_rate,
        positive_window_ratio=test.positive_window_ratio,
        maximum_drawdown=test.maximum_drawdown,
        required_samples=30,
        cumulative_samples=100,
        required_cumulative_samples=100,
    )

    assert validation.qualifies
    assert test.qualifies


@pytest.mark.parametrize(
    ("field", "passing", "failing", "reason"),
    (
        ("maximum_drawdown", "0.10", "0.1001", "MAXIMUM_DRAWDOWN_TOO_HIGH"),
        (
            "maximum_stock_trade_share",
            "0.10",
            "0.1001",
            "STOCK_TRADE_CONCENTRATION_TOO_HIGH",
        ),
        (
            "maximum_stock_profit_share",
            "0.15",
            "0.1501",
            "STOCK_PROFIT_CONCENTRATION_TOO_HIGH",
        ),
        (
            "maximum_sector_trade_share",
            "0.35",
            "0.3501",
            "SECTOR_TRADE_CONCENTRATION_TOO_HIGH",
        ),
        (
            "maximum_sector_profit_share",
            "0.40",
            "0.4001",
            "SECTOR_PROFIT_CONCENTRATION_TOO_HIGH",
        ),
        (
            "top5_profit_share",
            "0.35",
            "0.3501",
            "TOP5_PROFIT_CONCENTRATION_TOO_HIGH",
        ),
    ),
)
def test_portfolio_concentration_boundaries_are_exact(
    field: str,
    passing: str,
    failing: str,
    reason: str,
) -> None:
    values = {
        "maximum_drawdown": Decimal("0.05"),
        "maximum_stock_trade_share": Decimal("0.05"),
        "maximum_stock_profit_share": Decimal("0.10"),
        "maximum_sector_trade_share": Decimal("0.20"),
        "maximum_sector_profit_share": Decimal("0.30"),
        "top5_profit_share": Decimal("0.30"),
    }
    values[field] = Decimal(passing)
    passed = assess_five_day_portfolio(accepted_trades=100, **values)
    values[field] = Decimal(failing)
    failed = assess_five_day_portfolio(accepted_trades=100, **values)

    assert passed.qualifies
    assert not failed.qualifies
    assert reason in failed.reasons


def test_research_portfolio_enforces_three_overlapping_active_trades() -> None:
    plans = tuple(
        _plan(START + timedelta(days=index), code=f"60000{index + 1}")
        for index in range(4)
    )
    observations = tuple(
        replace(
            _observation(plan.candidate.signal_date),
            plan=plan,
            trade=replace(
                _observation(plan.candidate.signal_date).trade,
                profile_id=plan.profile.profile_id,
                structure_id=plan.structure_id,
                code=plan.candidate.code,
                signal_date=plan.candidate.signal_date,
                entry_date=START + timedelta(days=4),
                exit=replace(
                    _observation(plan.candidate.signal_date).trade.exit,
                    actual_exit_date=START + timedelta(days=10),
                ),
            ),
            resolution_date=START + timedelta(days=10),
        )
        for plan in plans
    )
    calibration = _calibration(plans[0])

    metrics = build_five_day_portfolio_metrics(
        plans,
        observations,
        {calibration.key: calibration},
    )

    assert metrics.accepted_trades == 3


def test_profit_factor_without_losses_fails_closed() -> None:
    result = assess_five_day_segment(
        profile_id=PROFILE,
        segment="validation",
        triggered_resolved=30,
        net_expectancy=Decimal("0.01"),
        profit_factor=None,
        profitable_wilson_lower=Decimal("0.50"),
        stop_rate=Decimal("0"),
        positive_window_ratio=Decimal("0.70"),
        maximum_drawdown=Decimal("0"),
        required_samples=30,
        cumulative_samples=70,
        required_cumulative_samples=70,
    )

    assert not result.qualifies
    assert "PROFIT_FACTOR_TOO_LOW" in result.reasons


def _passing_segment_observations(
    sessions: tuple[date, ...],
    count: int,
    *,
    code_offset: int,
) -> tuple[FiveDayObservation, ...]:
    step = max(1, (len(sessions) - 7) // count)
    selected_dates = tuple(sessions[index * step] for index in range(count))
    values: list[FiveDayObservation] = []
    for index, signal_date in enumerate(selected_dates):
        code = f"{600000 + code_offset + index:06d}"
        net_return = "0.01" if index % 10 < 7 else "-0.005"
        value = _observation(signal_date, net_return=net_return)
        plan = _plan(signal_date, code=code)
        plan = replace(
            plan,
            candidate=replace(
                plan.candidate,
                sector_code=f"80{index % 3 + 1:04d}",
            ),
        )
        exit_value = replace(
            value.trade.exit,
            actual_exit_date=signal_date + timedelta(days=6),
            planned_exit_date=signal_date + timedelta(days=6),
        )
        trade = replace(
            value.trade,
            profile_id=plan.profile.profile_id,
            structure_id=plan.structure_id,
            code=code,
            signal_date=signal_date,
            entry_date=signal_date + timedelta(days=1),
            exit=exit_value,
            net_pnl=Decimal(net_return) * Decimal("10000"),
            net_return=Decimal(net_return),
        )
        values.append(
            FiveDayObservation(
                plan=plan,
                trade=trade,
                resolution_date=exit_value.actual_exit_date,
            )
        )
    return tuple(values)


def test_validation_freeze_and_frozen_test_keep_only_proven_profiles() -> None:
    split = chronological_split(_trading_dates(630))
    train = _passing_segment_observations(
        split.train, 40, code_offset=0
    )
    validation = _passing_segment_observations(
        split.validation, 30, code_offset=100
    )
    test = _passing_segment_observations(
        split.test, 30, code_offset=200
    )

    freeze = evaluate_validation_freeze(
        (*train, *validation),
        train_dates=split.train,
        validation_dates=split.validation,
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
        research_identity="research-fixture-1",
    )
    assessment = evaluate_frozen_test(
        freeze,
        test,
        test_dates=split.test,
    )

    assert not freeze.empty
    assert freeze.research_identity == "research-fixture-1"
    assert tuple(value.profile_id for value in freeze.profiles) == (PROFILE,)
    assert freeze.profiles[0].train_validation_samples == 70
    assert freeze.freeze_hash
    assert assessment.eligible_profile_ids == (PROFILE,)
    assert assessment.portfolio_metrics.qualifies


def test_combined_portfolio_failure_creates_an_empty_freeze_without_subset_search() -> None:
    split = chronological_split(_trading_dates(630))
    train = _passing_segment_observations(
        split.train, 40, code_offset=0
    )
    validation = tuple(
        replace(
            value,
            plan=replace(
                value.plan,
                candidate=replace(
                    value.plan.candidate,
                    sector_code="801010",
                ),
            ),
        )
        for value in _passing_segment_observations(
            split.validation, 30, code_offset=100
        )
    )

    freeze = evaluate_validation_freeze(
        (*train, *validation),
        train_dates=split.train,
        validation_dates=split.validation,
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
    )

    assert freeze.empty
    assert freeze.profiles == ()
    assert freeze.calibrations == {}


def test_validation_portfolio_ignores_results_resolved_after_the_cutoff() -> None:
    split = chronological_split(_trading_dates(630))
    train = _passing_segment_observations(split.train, 40, code_offset=0)
    validation = _passing_segment_observations(
        split.validation, 30, code_offset=100
    )
    future = _observation(split.validation[-1], net_return="-1")
    future_plan = _plan(split.validation[-1], code="609999")
    future_exit = replace(
        future.trade.exit,
        actual_exit_date=split.validation[-1] + timedelta(days=10),
        planned_exit_date=split.validation[-1] + timedelta(days=10),
    )
    future = FiveDayObservation(
        plan=future_plan,
        trade=replace(
            future.trade,
            structure_id=future_plan.structure_id,
            code=future_plan.candidate.code,
            signal_date=future_plan.candidate.signal_date,
            entry_date=future_plan.candidate.signal_date + timedelta(days=1),
            exit=future_exit,
            net_pnl=Decimal("-10000"),
            net_return=Decimal("-1"),
        ),
        resolution_date=future_exit.actual_exit_date,
    )

    freeze = evaluate_validation_freeze(
        (*train, *validation, future),
        train_dates=split.train,
        validation_dates=split.validation,
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
    )

    assert not freeze.empty
    assert freeze.profiles[0].train_validation_samples == 70
