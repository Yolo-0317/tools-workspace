from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.execution import ExecutionCosts
from stock_ai.buy_point_selection.models import BuyPointBar
from stock_ai.buy_point_selection.public_challenger_execution import (
    ChallengerPlan,
    simulate_direct_five_day,
    simulate_next_open_after_reclaim,
    simulate_reclaim_five_day,
)
from stock_ai.buy_point_selection.public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    RESIDUAL_TRACK,
    ChallengerSignal,
)


SIGNAL_DATE = date(2026, 1, 12)
ZERO_COSTS = ExecutionCosts(
    commission_rate=Decimal("0"),
    minimum_commission=Decimal("0"),
    slippage_rate=Decimal("0"),
    sell_tax_rate=Decimal("0"),
)


def _signal(track_id: str = RESIDUAL_TRACK) -> ChallengerSignal:
    return ChallengerSignal(
        track_id=track_id,
        signal_date=SIGNAL_DATE,
        code="600001",
        sector_code="S1",
        matched_index_id="sh.000001",
        signal_close=Decimal("10.00"),
        formation_return=Decimal("-0.10"),
        residual_5d=Decimal("-0.20"),
        market_percentile=Decimal("0.01"),
        sector_percentile=Decimal("0.01"),
        reference_bucket=None,
        in_candidate_pool=True,
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


def _future_bars() -> tuple[BuyPointBar, ...]:
    return (
        _bar(date(2026, 1, 13), open_="9.80", high="10.00", low="9.70", close="9.90"),
        _bar(date(2026, 1, 14), open_="9.95", high="10.10", low="9.90", close="10.00"),
        _bar(date(2026, 1, 15), open_="10.00", high="10.20", low="9.95", close="10.10"),
        _bar(date(2026, 1, 16), open_="10.10", high="10.30", low="10.00", close="10.20"),
        _bar(date(2026, 1, 19), open_="10.20", high="10.40", low="10.10", close="10.30"),
    )


def _history() -> tuple[BuyPointBar, ...]:
    dates: list[date] = []
    current = SIGNAL_DATE
    while len(dates) < 13:
        if current.weekday() < 5:
            dates.append(current)
        current -= timedelta(days=1)
    return tuple(
        _bar(
            trade_date,
            open_="10.00",
            high="10.20",
            low="9.70",
            close="10.00",
        )
        for trade_date in reversed(dates)
    )


def _reclaim_bars(
    *,
    low: str = "9.70",
    high: str = "10.20",
    close: str = "10.10",
) -> tuple[BuyPointBar, ...]:
    return _history() + (
        _bar(date(2026, 1, 13), open_="9.90", high=high, low=low, close=close),
        _bar(date(2026, 1, 14), open_="10.05", high="10.20", low="9.80", close="10.10"),
        _bar(date(2026, 1, 15), open_="10.10", high="10.30", low="9.90", close="10.20"),
        _bar(date(2026, 1, 16), open_="10.20", high="10.40", low="10.00", close="10.30"),
        _bar(date(2026, 1, 19), open_="10.30", high="10.50", low="10.10", close="10.40"),
        _bar(date(2026, 1, 20), open_="10.40", high="10.60", low="10.20", close="10.50"),
    )


def test_direct_track_enters_next_open_and_exits_fifth_holding_close() -> None:
    trade = simulate_direct_five_day(
        _signal(),
        _future_bars(),
        costs=ZERO_COSTS,
    )

    assert trade.entry_date == date(2026, 1, 13)
    assert trade.entry_price == Decimal("9.80")
    assert trade.exit_date == date(2026, 1, 19)
    assert trade.exit_price == Decimal("10.30")
    assert trade.status == "TIME_EXIT_GAIN"
    assert trade.net_return == Decimal(
        "0.051020408163265306122448979591836734693877551020408"
    )


def test_public_contrarian_reference_uses_the_same_direct_execution() -> None:
    trade = simulate_direct_five_day(
        _signal(CONTRARIAN_TRACK),
        _future_bars(),
        costs=ZERO_COSTS,
    )

    assert trade.track_id == CONTRARIAN_TRACK
    assert trade.entry_date == date(2026, 1, 13)
    assert trade.exit_date == date(2026, 1, 19)


@pytest.mark.parametrize("pct_chg", ["10", "-10"])
def test_direct_track_does_not_fill_a_locked_limit_session(pct_chg: str) -> None:
    locked = _bar(
        date(2026, 1, 13),
        open_="11.00" if pct_chg == "10" else "9.00",
        high="11.00" if pct_chg == "10" else "9.00",
        low="11.00" if pct_chg == "10" else "9.00",
        close="11.00" if pct_chg == "10" else "9.00",
        pct_chg=pct_chg,
    )

    trade = simulate_direct_five_day(_signal(), (locked,), costs=ZERO_COSTS)

    assert trade.status == "CANCELLED"
    assert trade.entry_date is None
    assert trade.reasons == (
        "LOCKED_LIMIT_UP" if pct_chg == "10" else "LOCKED_LIMIT_DOWN",
    )


def test_direct_track_stays_pending_until_five_holding_sessions_exist() -> None:
    trade = simulate_direct_five_day(
        _signal(),
        _future_bars()[:4],
        costs=ZERO_COSTS,
    )

    assert trade.status == "PENDING"
    assert trade.net_return is None
    assert trade.exit_date is None


def test_direct_time_exit_waits_through_locked_limit_down() -> None:
    bars = _future_bars()[:4] + (
        _bar(
            date(2026, 1, 19),
            open_="9.00",
            high="9.00",
            low="9.00",
            close="9.00",
            pct_chg="-10",
        ),
        _bar(
            date(2026, 1, 20),
            open_="8.90",
            high="9.10",
            low="8.80",
            close="9.00",
        ),
    )

    trade = simulate_direct_five_day(_signal(), bars, costs=ZERO_COSTS)

    assert trade.exit_date == date(2026, 1, 20)
    assert trade.exit_price == Decimal("8.90")
    assert trade.reasons == ("EXIT_DELAYED",)


def test_challenger_plan_is_always_no_trade() -> None:
    plan = ChallengerPlan(
        signal=_signal(EXECUTION_TRACK),
        valid_entry_dates=(date(2026, 1, 13), date(2026, 1, 14)),
        entry_kind="RECLAIM_CLOSE",
    )

    assert plan.status == "CASE_ANALYSIS_ONLY"
    assert plan.trade_permission == "NO-TRADE"
    assert plan.executable_shares == 0


def test_reclaim_requires_touch_reclaim_and_upper_sixty_percent_close() -> None:
    trade = simulate_reclaim_five_day(
        _signal(EXECUTION_TRACK),
        _reclaim_bars(),
        costs=ZERO_COSTS,
    )

    assert trade.entry_date == date(2026, 1, 13)
    assert trade.entry_price == Decimal("10.10")
    assert trade.stop_price == Decimal("9.60")
    assert trade.exit_date == date(2026, 1, 19)
    assert trade.status == "TIME_EXIT_GAIN"


@pytest.mark.parametrize(
    ("reason", "low", "high", "close"),
    (
        ("NO_TOUCH", "10.01", "10.20", "10.10"),
        ("NO_RECLAIM", "9.70", "10.20", "9.99"),
        ("WEAK_CLOSE", "9.70", "10.30", "10.00"),
        ("CHASE_CANCELLED", "9.70", "10.40", "10.31"),
    ),
)
def test_reclaim_rejects_invalid_confirmation(
    reason: str,
    low: str,
    high: str,
    close: str,
) -> None:
    trade = simulate_reclaim_five_day(
        _signal(EXECUTION_TRACK),
        _history()
        + (
                _bar(
                    date(2026, 1, 13),
                    open_=close,
                    high=high,
                    low=low,
                    close=close,
            ),
        ),
        costs=ZERO_COSTS,
    )

    assert reason in trade.reasons
    assert trade.entry_date is None


def test_reclaim_rejects_risk_outside_one_point_five_to_five_percent() -> None:
    trade = simulate_reclaim_five_day(
        _signal(EXECUTION_TRACK),
        _reclaim_bars(low="9.00", high="10.20", close="10.10"),
        costs=ZERO_COSTS,
    )

    assert trade.status == "CANCELLED"
    assert trade.reasons == ("RISK_DISTANCE_OUT_OF_RANGE",)


def test_reclaim_stop_waits_through_locked_limit_down() -> None:
    bars = _history() + (
        _bar(date(2026, 1, 13), open_="9.90", high="10.20", low="9.70", close="10.10"),
        _bar(
            date(2026, 1, 14),
            open_="9.00",
            high="9.00",
            low="9.00",
            close="9.00",
            pct_chg="-10",
        ),
        _bar(date(2026, 1, 15), open_="8.90", high="9.10", low="8.80", close="9.00"),
    )

    trade = simulate_reclaim_five_day(
        _signal(EXECUTION_TRACK),
        bars,
        costs=ZERO_COSTS,
    )

    assert trade.status == "STOPPED"
    assert trade.exit_date == date(2026, 1, 15)
    assert trade.exit_price == Decimal("8.90")
    assert trade.reasons == ("EXIT_DELAYED",)


def test_next_open_sensitivity_enters_session_after_reclaim() -> None:
    trade = simulate_next_open_after_reclaim(
        _signal(EXECUTION_TRACK),
        _reclaim_bars(),
        costs=ZERO_COSTS,
    )

    assert trade.entry_date == date(2026, 1, 14)
    assert trade.entry_price == Decimal("10.05")
    assert trade.exit_date == date(2026, 1, 20)
