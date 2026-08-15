from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.execution import ExecutionCosts
from stock_ai.buy_point_selection.five_day_return_execution import (
    simulate_five_day_plan,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    build_five_day_return_profiles,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
)
from stock_ai.buy_point_selection.models import BuyPointBar, DetectedSetup, SetupType


SIGNAL = date(2026, 8, 10)
CALENDAR = tuple(
    date(2026, 8, day)
    for day in (10, 11, 12, 13, 14, 17, 18, 19, 20)
)
ZERO_COSTS = ExecutionCosts(
    commission_rate=Decimal("0"),
    minimum_commission=Decimal("0"),
    slippage_rate=Decimal("0"),
    sell_tax_rate=Decimal("0"),
)


def _bar(
    trade_date: date,
    *,
    open_: str,
    high: str,
    low: str,
    close: str,
    pct_chg: str = "0",
    amount_qian: str = "200000",
) -> BuyPointBar:
    return BuyPointBar(
        trade_date=trade_date,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        pct_chg=Decimal(pct_chg),
        amount_qian=Decimal(amount_qian),
    )


def _plan(
    profile_index: int,
    *,
    breakout_trigger: str = "10.01",
    structure_stop: str | None = "9.70",
    signal_close: str = "10.00",
) -> FiveDaySignalPlan:
    profile = build_five_day_return_profiles()[profile_index]
    setup = DetectedSetup(
        code="600001",
        setup_type=SetupType.TREND_PULLBACK,
        analysis_date=SIGNAL,
        structure_start=date(2026, 8, 3),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.74"),
        quality=Decimal("0.80"),
        reasons=("FIXTURE_SETUP",),
        metrics={},
    )
    candidate = FiveDaySignalCandidate(
        code="600001",
        signal_date=SIGNAL,
        setup=setup,
        market_status="ALLOW",
        sector_code="801010",
        sector_resonating=True,
        anti_chase_passed=True,
        average_amount5_qian=Decimal("200000"),
        valid_through_trade_date=CALENDAR[2],
    )
    reference_entry = (
        Decimal(breakout_trigger)
        if profile.entry_kind == "BREAKOUT_TRIGGER"
        else Decimal(signal_close)
    )
    return FiveDaySignalPlan(
        candidate=candidate,
        profile=profile,
        structure_id=f"structure-{profile.profile_id}",
        signal_close=Decimal(signal_close),
        breakout_trigger=Decimal(breakout_trigger),
        structure_stop=(
            None if structure_stop is None else Decimal(structure_stop)
        ),
        reference_entry=reference_entry,
        resistance_basis="NO_RELIABLE_LEVEL",
        resistance_effective_r=None,
    )


def _second_day_miss() -> BuyPointBar:
    return _bar(
        CALENDAR[2],
        open_="9.95",
        high="10.00",
        low="9.90",
        close="9.98",
    )


def test_breakout_uses_open_when_the_open_is_above_the_trigger() -> None:
    trade = simulate_five_day_plan(
        _plan(0),
        (
            _bar(
                CALENDAR[1],
                open_="10.02",
                high="10.10",
                low="9.95",
                close="10.05",
            ),
        ),
        CALENDAR[:2],
    )

    assert trade.entry_date == CALENDAR[1]
    assert trade.entry_price == Decimal("10.03002")
    assert trade.evaluation_shares == 900
    assert trade.evaluation_notional == Decimal("9027.01800")
    assert trade.entry_fees == Decimal("9.02701800")
    assert trade.executable_shares == 0
    assert trade.status == "PENDING"


def test_breakout_uses_the_trigger_for_an_intraday_cross() -> None:
    trade = simulate_five_day_plan(
        _plan(0),
        (
            _bar(
                CALENDAR[1],
                open_="9.95",
                high="10.02",
                low="9.90",
                close="10.01",
            ),
        ),
        CALENDAR[:2],
    )

    assert trade.entry_price == Decimal("10.02001")


@pytest.mark.parametrize(
    ("plan", "bar", "reason"),
    (
        (
            _plan(0),
            _bar(
                CALENDAR[1],
                open_="10.31",
                high="10.40",
                low="10.20",
                close="10.30",
            ),
            "GAP_CANCELLED",
        ),
        (
            _plan(0, breakout_trigger="10.51"),
            _bar(
                CALENDAR[1],
                open_="10.00",
                high="10.60",
                low="9.95",
                close="10.55",
            ),
            "CHASE_CANCELLED",
        ),
        (
            _plan(0),
            _bar(
                CALENDAR[1],
                open_="11.00",
                high="11.00",
                low="11.00",
                close="11.00",
                pct_chg="10",
            ),
            "LOCKED_LIMIT_UP",
        ),
    ),
)
def test_breakout_cancels_unfillable_or_overheated_entries(
    plan: FiveDaySignalPlan,
    bar: BuyPointBar,
    reason: str,
) -> None:
    trade = simulate_five_day_plan(plan, (bar,), CALENDAR[:2])

    assert trade.status == "CANCELLED"
    assert trade.reasons == (reason,)
    assert trade.entry_date is None
    assert trade.evaluation_shares == 0
    assert trade.entry_fees == 0


def test_pullback_reclaim_enters_at_the_confirmed_close() -> None:
    trade = simulate_five_day_plan(
        _plan(2),
        (
            _bar(
                CALENDAR[1],
                open_="10.00",
                high="10.30",
                low="9.90",
                close="10.20",
            ),
        ),
        CALENDAR[:2],
    )

    assert trade.entry_date == CALENDAR[1]
    assert trade.entry_price == Decimal("10.21020")


@pytest.mark.parametrize(
    ("low", "high", "close", "expected_status"),
    (
        ("9.80", "10.30", "10.10", "PENDING"),
        ("9.80", "10.30", "10.099", "NOT_TRIGGERED"),
        ("9.80", "10.40", "10.30", "PENDING"),
        ("9.80", "10.40", "10.301", "CANCELLED"),
        ("10.01", "10.30", "10.10", "NOT_TRIGGERED"),
        ("9.90", "10.30", "9.99", "NOT_TRIGGERED"),
    ),
)
def test_pullback_reclaim_respects_location_chase_touch_and_reclaim_boundaries(
    low: str,
    high: str,
    close: str,
    expected_status: str,
) -> None:
    bars = (
        _bar(
            CALENDAR[1],
            open_="10.00",
            high=high,
            low=low,
            close=close,
        ),
        _second_day_miss(),
    )

    calendar = CALENDAR[:2] if expected_status == "PENDING" else CALENDAR[:3]
    trade = simulate_five_day_plan(_plan(2), bars, calendar)

    assert trade.status == expected_status


def test_pullback_reclaim_cancels_a_locked_limit_up() -> None:
    locked = _bar(
        CALENDAR[1],
        open_="11.00",
        high="11.00",
        low="11.00",
        close="11.00",
        pct_chg="10",
    )

    trade = simulate_five_day_plan(_plan(2), (locked,), CALENDAR[:2])

    assert trade.status == "CANCELLED"
    assert trade.reasons == ("LOCKED_LIMIT_UP",)


def test_entry_hard_blocker_cancels_before_price_evaluation() -> None:
    entry = _bar(
        CALENDAR[1],
        open_="10.02",
        high="10.10",
        low="9.95",
        close="10.05",
    )

    trade = simulate_five_day_plan(
        _plan(0),
        (entry,),
        CALENDAR[:2],
        entry_blockers={CALENDAR[1]: ("MARKET_FREEZE",)},
    )

    assert trade.status == "CANCELLED"
    assert trade.reasons == ("MARKET_FREEZE",)
    assert trade.entry_date is None


def _pullback_holding_bars(
    fifth_close: str = "10.20",
) -> tuple[BuyPointBar, ...]:
    return (
        _bar(
            CALENDAR[1],
            open_="10.00",
            high="10.20",
            low="9.60",
            close="10.00",
        ),
        _bar(
            CALENDAR[2],
            open_="10.00",
            high="10.15",
            low="9.90",
            close="10.05",
        ),
        _bar(
            CALENDAR[3],
            open_="10.05",
            high="10.25",
            low="9.85",
            close="10.10",
        ),
        _bar(
            CALENDAR[4],
            open_="10.10",
            high="10.20",
            low="9.95",
            close="10.10",
        ),
        _bar(
            CALENDAR[5],
            open_="10.10",
            high="10.30",
            low="10.00",
            close=fifth_close,
        ),
    )


def test_breakout_intraday_cross_and_same_bar_stop_is_conservative() -> None:
    entry_and_stop = _bar(
        CALENDAR[1],
        open_="9.95",
        high="10.10",
        low="9.70",
        close="10.00",
    )

    trade = simulate_five_day_plan(
        _plan(0),
        (entry_and_stop,),
        CALENDAR[:2],
    )

    assert trade.status == "STOPPED"
    assert trade.stop_price == Decimal("9.71")
    assert trade.exit is not None
    assert trade.exit.reason == "STOP"
    assert trade.exit.actual_exit_date == CALENDAR[1]
    assert trade.intraday_order_ambiguous


def test_pullback_entry_day_low_does_not_stop_a_close_entry() -> None:
    trade = simulate_five_day_plan(
        _plan(2),
        _pullback_holding_bars(),
        CALENDAR[:6],
    )

    assert trade.status == "TIME_EXIT_GAIN"
    assert trade.stop_price == Decimal("9.70")
    assert trade.exit is not None
    assert trade.exit.actual_exit_date == CALENDAR[5]
    assert not trade.intraday_order_ambiguous


def test_stop_gap_uses_the_worse_open_instead_of_the_stop_price() -> None:
    bars = (
        _bar(
            CALENDAR[1],
            open_="10.02",
            high="10.10",
            low="9.95",
            close="10.00",
        ),
        _bar(
            CALENDAR[2],
            open_="9.60",
            high="9.70",
            low="9.50",
            close="9.60",
        ),
    )

    trade = simulate_five_day_plan(_plan(0), bars, CALENDAR[:3])

    assert trade.status == "STOPPED"
    assert trade.exit is not None
    assert trade.exit.price == Decimal("9.59040")
    assert trade.exit.price < trade.stop_price


def test_time_exit_charges_exact_default_costs_and_excludes_pre_entry_low() -> None:
    trade = simulate_five_day_plan(
        _plan(2),
        _pullback_holding_bars(),
        CALENDAR[:6],
    )

    assert trade.entry_price == Decimal("10.01000")
    assert trade.evaluation_shares == 900
    assert trade.entry_fees == Decimal("9.00900000")
    assert trade.exit is not None
    assert trade.exit.price == Decimal("10.18980")
    assert trade.exit.fees == Decimal("18.34164000")
    assert trade.net_pnl == Decimal("134.46936000")
    assert trade.net_return == Decimal("134.46936000") / Decimal(
        "9018.00900000"
    )
    assert trade.mfe == Decimal("10.30") / Decimal("10.01000") - Decimal("1")
    assert trade.mae == Decimal("1") - Decimal("9.85") / Decimal("10.01000")


def test_excursions_ignore_bars_outside_the_confirmed_calendar() -> None:
    bars = _pullback_holding_bars()
    off_calendar = _bar(
        date(2026, 8, 16),
        open_="10.00",
        high="20.00",
        low="1.00",
        close="10.00",
    )

    baseline = simulate_five_day_plan(_plan(2), bars, CALENDAR[:6])
    contaminated = simulate_five_day_plan(
        _plan(2),
        (*bars, off_calendar),
        CALENDAR[:6],
    )

    assert contaminated.mfe == baseline.mfe
    assert contaminated.mae == baseline.mae


@pytest.mark.parametrize(
    ("fifth_close", "expected_status"),
    (
        ("10.20", "TIME_EXIT_GAIN"),
        ("10.00", "TIME_EXIT_FLAT"),
        ("9.90", "TIME_EXIT_LOSS"),
    ),
)
def test_time_exit_status_depends_on_net_return(
    fifth_close: str,
    expected_status: str,
) -> None:
    trade = simulate_five_day_plan(
        _plan(2),
        _pullback_holding_bars(fifth_close),
        CALENDAR[:6],
        ZERO_COSTS,
    )

    assert trade.status == expected_status


def test_locked_limit_down_delays_the_fifth_session_exit() -> None:
    bars = (
        *_pullback_holding_bars()[:4],
        _bar(
            CALENDAR[5],
            open_="9.80",
            high="9.80",
            low="9.80",
            close="9.80",
            pct_chg="-10",
        ),
        _bar(
            CALENDAR[6],
            open_="9.85",
            high="10.00",
            low="9.80",
            close="9.90",
        ),
    )

    trade = simulate_five_day_plan(_plan(2), bars, CALENDAR[:7])

    assert trade.exit is not None
    assert trade.exit.planned_exit_date == CALENDAR[5]
    assert trade.exit.actual_exit_date == CALENDAR[6]
    assert trade.exit.delayed
    assert trade.exit.reason == "TIME_EXIT"
    assert "EXIT_DELAYED" in trade.reasons


def test_suspension_delays_the_fifth_session_exit() -> None:
    bars = (
        *_pullback_holding_bars()[:4],
        _bar(
            CALENDAR[5],
            open_="0",
            high="0",
            low="0",
            close="0",
            amount_qian="0",
        ),
        _bar(
            CALENDAR[6],
            open_="10.05",
            high="10.10",
            low="10.00",
            close="10.05",
        ),
    )

    trade = simulate_five_day_plan(_plan(2), bars, CALENDAR[:7])

    assert trade.exit is not None
    assert trade.exit.actual_exit_date == CALENDAR[6]
    assert trade.exit.delayed


def test_entry_with_fewer_than_five_holding_sessions_remains_pending() -> None:
    bars = _pullback_holding_bars()[:4]

    trade = simulate_five_day_plan(_plan(2), bars, CALENDAR[:5])

    assert trade.status == "PENDING"
    assert trade.entry_date == CALENDAR[1]
    assert trade.evaluation_shares == 900
    assert trade.exit is None
    assert trade.net_return is None


def test_locked_limit_down_stop_without_a_later_tradable_bar_is_pending() -> None:
    bars = (
        _bar(
            CALENDAR[1],
            open_="10.02",
            high="10.10",
            low="9.95",
            close="10.00",
        ),
        _bar(
            CALENDAR[2],
            open_="9.60",
            high="9.60",
            low="9.60",
            close="9.60",
            pct_chg="-10",
        ),
    )

    trade = simulate_five_day_plan(_plan(0), bars, CALENDAR[:3])

    assert trade.status == "PENDING"
    assert trade.entry_date == CALENDAR[1]
    assert trade.exit is None


def test_structure_stop_below_the_one_point_five_percent_floor_cancels() -> None:
    plan = _plan(
        1,
        breakout_trigger="10.00",
        structure_stop="9.851",
    )
    entry = _bar(
        CALENDAR[1],
        open_="10.00",
        high="10.10",
        low="9.90",
        close="10.00",
    )

    trade = simulate_five_day_plan(
        plan,
        (entry,),
        CALENDAR[:2],
        ZERO_COSTS,
    )

    assert trade.status == "CANCELLED"
    assert trade.reasons == ("RISK_DISTANCE_OUT_OF_RANGE",)
    assert trade.evaluation_shares == 0


def test_price_above_one_hundred_uses_one_lot_and_records_the_exception() -> None:
    plan = _plan(
        0,
        breakout_trigger="101.00",
        signal_close="100.00",
    )
    entry = _bar(
        CALENDAR[1],
        open_="101.00",
        high="102.00",
        low="100.00",
        close="101.00",
    )

    trade = simulate_five_day_plan(
        plan,
        (entry,),
        CALENDAR[:2],
        ZERO_COSTS,
    )

    assert trade.entry_price == Decimal("101.00")
    assert trade.evaluation_shares == 100
    assert trade.evaluation_notional == Decimal("10100.00")
    assert trade.reasons == ("MINIMUM_LOT_EXCEEDS_TARGET_NOTIONAL",)
    assert trade.executable_shares == 0
