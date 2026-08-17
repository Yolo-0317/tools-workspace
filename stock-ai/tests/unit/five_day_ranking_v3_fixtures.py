from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from stock_ai.buy_point_selection.five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
    FiveDayExit,
    FiveDayTrade,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    SIZING_VERSION,
    build_five_day_return_profiles,
    evaluation_position,
    five_day_profile_hash,
    resolve_profile_stop,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayResearchReview,
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayObservation,
    FiveDayPortfolioMetrics,
)
from stock_ai.buy_point_selection.models import (
    DetectedSetup,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.validation import (
    ChronologicalSplit,
    policy_hash,
)


def weekday_dates(
    count: int,
    start: date = date(2023, 1, 2),
) -> tuple[date, ...]:
    values: list[date] = []
    current = start
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def make_v3_plan(
    signal_date: date,
    *,
    code: str = "600001",
    profile_id: str = "BREAKOUT_TRIGGER__STRUCTURE_ATR",
    setup_type: SetupType = SetupType.TREND_PULLBACK,
    market_status: str = "ALLOW",
    sector_resonating: bool = True,
    setup_quality: Decimal = Decimal("0.60"),
    structure_start: date | None = None,
    structure_high: Decimal = Decimal("11"),
    structure_low: Decimal = Decimal("9"),
    signal_close: Decimal = Decimal("10"),
    breakout_trigger: Decimal = Decimal("10.10"),
    structure_stop: Decimal = Decimal("9.70"),
    resistance_effective_r: Decimal | None = Decimal("2"),
    average_amount5_qian: Decimal = Decimal("200000"),
) -> FiveDaySignalPlan:
    profile = next(
        value
        for value in build_five_day_return_profiles()
        if value.profile_id == profile_id
    )
    setup = DetectedSetup(
        code=code,
        setup_type=setup_type,
        analysis_date=signal_date,
        structure_start=structure_start or signal_date - timedelta(days=10),
        structure_high=structure_high,
        structure_low=structure_low,
        quality=setup_quality,
        reasons=(),
        metrics={},
    )
    candidate = FiveDaySignalCandidate(
        code=code,
        signal_date=signal_date,
        setup=setup,
        market_status=market_status,
        sector_code="TEST",
        sector_resonating=sector_resonating,
        anti_chase_passed=True,
        average_amount5_qian=average_amount5_qian,
        valid_through_trade_date=signal_date + timedelta(days=7),
    )
    resistance_basis = (
        "NO_RELIABLE_LEVEL"
        if resistance_effective_r is None
        else "LEVEL_AT_OR_ABOVE_2R"
        if resistance_effective_r >= Decimal("2")
        else "LEVEL_BELOW_2R"
    )
    return FiveDaySignalPlan(
        candidate=candidate,
        profile=profile,
        structure_id=(
            f"{code}-{setup_type.value}-{signal_date.isoformat()}-{profile_id}"
        ),
        signal_close=signal_close,
        breakout_trigger=breakout_trigger,
        structure_stop=structure_stop,
        reference_entry=(
            breakout_trigger
            if profile.entry_kind == "BREAKOUT_TRIGGER"
            else signal_close
        ),
        resistance_basis=resistance_basis,
        resistance_effective_r=resistance_effective_r,
    )


def make_v3_observation(
    plan: FiveDaySignalPlan,
    *,
    net_return: Decimal = Decimal("0.01"),
    net_pnl: Decimal = Decimal("100"),
    status: str = "TIME_EXIT_GAIN",
    mae: Decimal = Decimal("0.02"),
    resolution_date: date | None = None,
) -> FiveDayObservation:
    resolved_on = resolution_date or plan.candidate.signal_date + timedelta(
        days=7
    )
    stop = resolve_profile_stop(
        plan.profile,
        plan.reference_entry,
        plan.structure_stop,
    )
    assert stop.stop_price is not None
    position = evaluation_position(plan.reference_entry)
    exit_value = FiveDayExit(
        planned_exit_date=resolved_on,
        actual_exit_date=resolved_on,
        price=plan.reference_entry * (Decimal("1") + net_return),
        reason=status,
        fees=Decimal("0"),
        delayed=False,
    )
    trade = FiveDayTrade(
        profile_id=plan.profile.profile_id,
        structure_id=plan.structure_id,
        code=plan.candidate.code,
        signal_date=plan.candidate.signal_date,
        status=status,
        entry_date=plan.candidate.signal_date + timedelta(days=1),
        entry_price=plan.reference_entry,
        stop_price=stop.stop_price,
        evaluation_target_notional=position.evaluation_target_notional,
        evaluation_shares=position.evaluation_shares,
        evaluation_notional=position.evaluation_notional,
        entry_fees=Decimal("0"),
        exit=exit_value,
        net_pnl=net_pnl,
        net_return=net_return,
        mfe=max(net_return, Decimal("0")),
        mae=mae,
        intraday_order_ambiguous=False,
        reasons=(),
    )
    return FiveDayObservation(
        plan=plan,
        trade=trade,
        resolution_date=resolved_on,
    )


def make_v3_research_review(
    observations: tuple[FiveDayObservation, ...],
) -> FiveDayResearchReview:
    sessions = weekday_dates(630)
    policy = SelectionPolicy()
    empty_portfolio = FiveDayPortfolioMetrics(
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
    return FiveDayResearchReview(
        split=ChronologicalSplit(
            train=sessions[:378],
            validation=sessions[378:504],
            test=sessions[504:630],
        ),
        input_fingerprint="f" * 64,
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
        sizing_version=SIZING_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        cost_version=COST_VERSION,
        observations=observations,
        train_calibrations={},
        validation_metrics=(),
        validation_portfolio=empty_portfolio,
        point_in_time_complete=True,
        test_outcomes_read=False,
    )
