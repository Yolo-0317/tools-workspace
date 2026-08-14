from __future__ import annotations

from datetime import date
from decimal import Decimal

from stock_ai.buy_point_selection.execution import ExecutionCosts
from stock_ai.buy_point_selection.historical_replay import (
    HistoricalPlan,
    replay_historical_plans,
    replay_observation_payload,
    second_trading_date_after,
)
from stock_ai.buy_point_selection.models import BuyPointBar, OutcomeLabel, SetupType
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.reference_data import ReferenceCoverage


ZERO_COSTS = ExecutionCosts(
    commission_rate=Decimal("0"),
    minimum_commission=Decimal("0"),
    slippage_rate=Decimal("0"),
    sell_tax_rate=Decimal("0"),
)


def _bar(day: date, *, high: str = "10.20", low: str = "9.90", close: str = "10.10") -> BuyPointBar:
    return BuyPointBar(
        trade_date=day,
        open=Decimal("10.00"),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        pct_chg=Decimal("0"),
        amount_qian=Decimal("200000"),
    )


def _plan(signal_date: date, valid_through: date, *, identity: str = "structure-1") -> PricePlan:
    return PricePlan(
        structure_id=identity,
        code="600001",
        setup_type=SetupType.PRE_BREAKOUT,
        signal_date=signal_date,
        signal_close=Decimal("10.00"),
        trigger_price=Decimal("10.10"),
        invalidation_price=Decimal("9.80"),
        target_2r=Decimal("10.70"),
        risk_distance=Decimal("0.30"),
        risk_reward_ratio=Decimal("2"),
        maximum_shares=100,
        valid_through_trade_date=valid_through,
    )


def _historical_plan(signal_date: date, valid_through: date, *, identity: str = "structure-1") -> HistoricalPlan:
    return HistoricalPlan(
        signal_date=signal_date,
        code="600001",
        sector_code="S1",
        market_status="ALLOW",
        sector_resonating=True,
        plan=_plan(signal_date, valid_through, identity=identity),
    )


def test_second_trigger_session_uses_actual_trading_dates_across_holiday() -> None:
    """Catches weekday arithmetic expiring a plan during a market holiday."""
    trading_dates = (
        date(2024, 2, 7),
        date(2024, 2, 8),
        date(2024, 2, 19),
        date(2024, 2, 20),
    )

    assert second_trading_date_after(trading_dates, date(2024, 2, 7)) == date(2024, 2, 19)


def test_replay_deduplicates_the_same_structure_and_records_two_r_outcome() -> None:
    """Catches repeated daily signals inflating samples and 2R paths losing their result."""
    signal = date(2024, 2, 7)
    first = date(2024, 2, 8)
    second = date(2024, 2, 19)
    plans = (
        _historical_plan(signal, second),
        _historical_plan(first, date(2024, 2, 20)),
    )
    bars = {
        "600001": (
            _bar(first, high="10.20", low="9.90", close="10.10"),
            _bar(second, high="10.80", low="10.00", close="10.70"),
        )
    }
    coverage = {
        signal: ReferenceCoverage(signal, True, True, True),
        first: ReferenceCoverage(first, True, True, True),
    }

    result = replay_historical_plans(plans, bars, coverage, costs=ZERO_COSTS)

    assert len(result.opportunities) == 1
    assert result.integrity.duplicate_structures == 1
    assert result.opportunities[0].trade.outcome is OutcomeLabel.TARGET_2R_FIRST


def test_incomplete_pit_date_emits_no_plan_and_fails_integrity() -> None:
    """Catches missing announcement history being silently treated as no risk flags."""
    signal = date(2024, 2, 7)
    valid_through = date(2024, 2, 19)
    coverage = {
        signal: ReferenceCoverage(signal, True, True, False),
    }

    result = replay_historical_plans(
        (_historical_plan(signal, valid_through),),
        {"600001": ()},
        coverage,
        costs=ZERO_COSTS,
    )

    assert result.opportunities == ()
    assert not result.integrity.complete
    assert result.integrity.missing_announcement_dates == (signal,)


def test_integrity_checks_every_signal_date_even_when_no_setup_exists() -> None:
    """Catches a reference or market gap disappearing on a day with zero candidates."""
    signal = date(2024, 2, 7)

    result = replay_historical_plans(
        (),
        {},
        {signal: ReferenceCoverage(signal, True, True, False)},
        signal_dates=(signal,),
        market_complete_by_date={signal: False},
    )

    assert not result.integrity.complete
    assert result.integrity.missing_announcement_dates == (signal,)
    assert result.integrity.missing_market_dates == (signal,)


def test_observation_payload_retains_signal_identity_and_resolution_date() -> None:
    """Catches calibration rows becoming impossible to rank or audit by signal date."""
    signal = date(2024, 2, 7)
    first = date(2024, 2, 8)
    second = date(2024, 2, 19)
    result = replay_historical_plans(
        (_historical_plan(signal, second),),
        {
            "600001": (
                _bar(first, high="10.20", low="9.90", close="10.10"),
                _bar(second, high="10.80", low="10.00", close="10.70"),
            )
        },
        {signal: ReferenceCoverage(signal, True, True, True)},
        costs=ZERO_COSTS,
    )

    payload = replay_observation_payload(result.opportunities[0])

    assert payload["signal_date"] == "2024-02-07"
    assert payload["exit_date"] == "2024-02-19"
    assert payload["structure_id"] == "structure-1"
    assert payload["outcome"] == "TARGET_2R_FIRST"
    assert payload["risk_fraction"] == "0.02970297029702970297029702970"
