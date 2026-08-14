from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from stock_ai.buy_point_selection.case_review import (
    CaseCandidate,
    CaseSignalReplay,
    GateTrace,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    SetupType,
)
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.recall_research import (
    DailyRecallWinner,
    attribute_daily_recall_winners,
    diagnose_market_freeze_winners,
    find_daily_actionable_winners,
    next_five_trading_dates,
)
from stock_ai.buy_point_selection.reference_data import RiskFlag


SIGNAL = date(2026, 8, 3)


def _bar(
    trade_date: date,
    *,
    open_: str = "10.00",
    high: str = "10.10",
    low: str = "9.90",
    close: str = "10.00",
    pct_chg: str = "0",
    amount: str = "200000",
) -> BuyPointBar:
    return BuyPointBar(
        trade_date,
        Decimal(open_),
        Decimal(high),
        Decimal(low),
        Decimal(close),
        Decimal(pct_chg),
        Decimal(amount),
    )


def _history() -> tuple[BuyPointBar, ...]:
    return tuple(
        _bar(SIGNAL - timedelta(days=59 - index))
        for index in range(60)
    )


def _platform_history() -> tuple[BuyPointBar, ...]:
    bars = []
    for index in range(60):
        close = Decimal("10.00") + Decimal(index) * Decimal("0.005")
        high = close + Decimal("0.05")
        low = close - Decimal("0.05")
        amount = Decimal("200000")
        if 40 <= index < 50:
            high = Decimal("10.40")
            low = Decimal("9.70")
        if index >= 50:
            high = close + Decimal("0.03")
            low = close - Decimal("0.03")
        if index >= 55:
            amount = Decimal("120000")
        bars.append(
            BuyPointBar(
                SIGNAL - timedelta(days=59 - index),
                close,
                high,
                low,
                close,
                Decimal("0.05"),
                amount,
            )
        )
    return tuple(bars)


def _outcome_dates() -> tuple[date, ...]:
    return tuple(SIGNAL + timedelta(days=index) for index in range(1, 6))


def _candidate(signal_date: date) -> CaseCandidate:
    setup = DetectedSetup(
        "600001",
        SetupType.PRE_BREAKOUT,
        signal_date,
        signal_date - timedelta(days=20),
        Decimal("10.20"),
        Decimal("9.50"),
        Decimal("0.50"),
        (),
        {},
    )
    return CaseCandidate(
        "600001",
        signal_date,
        setup,
        PricePlan(
            f"structure-{signal_date}",
            "600001",
            setup.setup_type,
            signal_date,
            Decimal("10.00"),
            Decimal("10.10"),
            Decimal("9.80"),
            Decimal("10.70"),
            Decimal("0.30"),
            Decimal("2"),
            0,
            signal_date + timedelta(days=2),
        ),
        "NEAR_MISS",
        "INSUFFICIENT_TWO_R_SPACE",
        (Decimal("0"), "600001"),
    )


def test_normal_entry_before_five_percent_gain_is_actionable() -> None:
    """Catches a forward gain after a normal entry being omitted from recall."""
    dates = _outcome_dates()
    outcome = (
        _bar(dates[0], high="10.20", close="10.10"),
        _bar(dates[1], open_="10.10", high="10.30", close="10.20"),
        _bar(dates[2], open_="10.20", high="10.60", close="10.50"),
        _bar(dates[3], open_="10.50", high="10.55", close="10.40"),
        _bar(dates[4], open_="10.40", high="10.45", close="10.30"),
    )

    cohort = find_daily_actionable_winners(
        signal_date=SIGNAL,
        outcome_dates=dates,
        bars_by_code={"600001": (*_history(), *outcome)},
        risk_flags=(),
        holding_codes=frozenset(),
    )

    assert cohort.complete
    assert cohort.outcome_dates == dates
    assert len(cohort.winners) == 1
    winner = cohort.winners[0]
    assert winner.code == "600001"
    assert winner.signal_date == SIGNAL
    assert winner.horizon_end_date == dates[-1]
    assert winner.entry_date == dates[0]
    assert winner.entry_price == Decimal("10.00")
    assert winner.forward_maximum_gain == Decimal("0.06")
    assert winner.maximum_gain_date == dates[2]
    assert winner.executable_shares == 0


def test_gain_before_first_normal_entry_is_not_actionable() -> None:
    """Catches a locked surge being credited to a later normal entry."""
    dates = _outcome_dates()
    outcome = (
        _bar(
            dates[0],
            open_="11.00",
            high="11.00",
            low="11.00",
            close="11.00",
            pct_chg="10",
        ),
        _bar(dates[1], open_="11.00", high="11.10", close="11.00"),
        _bar(dates[2], open_="11.00", high="11.20", close="11.10"),
        _bar(dates[3], open_="11.10", high="11.25", close="11.10"),
        _bar(dates[4], open_="11.10", high="11.20", close="11.10"),
    )

    cohort = find_daily_actionable_winners(
        signal_date=SIGNAL,
        outcome_dates=dates,
        bars_by_code={"600001": (*_history(), *outcome)},
        risk_flags=(),
        holding_codes=frozenset(),
    )

    assert cohort.winners == ()


def test_gap_above_three_percent_is_not_an_actionable_entry() -> None:
    """Catches a gap-chased opening being treated as a normal buy point."""
    dates = _outcome_dates()
    outcome = (
        _bar(dates[0], open_="10.31", high="10.90", close="10.31"),
        _bar(dates[1], open_="10.31", high="10.50", close="10.35"),
        _bar(dates[2], open_="10.35", high="10.55", close="10.40"),
        _bar(dates[3], open_="10.40", high="10.55", close="10.45"),
        _bar(dates[4], open_="10.45", high="10.55", close="10.45"),
    )

    cohort = find_daily_actionable_winners(
        signal_date=SIGNAL,
        outcome_dates=dates,
        bars_by_code={"600001": (*_history(), *outcome)},
        risk_flags=(),
        holding_codes=frozenset(),
    )

    assert cohort.winners == ()


def test_future_sixth_session_cannot_create_a_five_session_winner() -> None:
    """Catches outcome bars beyond the frozen horizon leaking into recall."""
    dates = _outcome_dates()
    flat = tuple(_bar(value) for value in dates)
    future = _bar(dates[-1] + timedelta(days=1), high="20.00", close="19.00")

    cohort = find_daily_actionable_winners(
        signal_date=SIGNAL,
        outcome_dates=dates,
        bars_by_code={"600001": (*_history(), *flat, future)},
        risk_flags=(),
        holding_codes=frozenset(),
    )

    assert cohort.winners == ()


def test_short_outcome_horizon_fails_closed() -> None:
    dates = _outcome_dates()[:4]

    cohort = find_daily_actionable_winners(
        signal_date=SIGNAL,
        outcome_dates=dates,
        bars_by_code={},
        risk_flags=(),
        holding_codes=frozenset(),
    )

    assert not cohort.complete
    assert cohort.winners == ()


def test_point_in_time_holding_and_veto_exclude_winners() -> None:
    dates = _outcome_dates()
    outcome = tuple(
        _bar(value, high="10.60", close="10.50")
        for value in dates
    )
    bars = {
        "600001": (*_history(), *outcome),
        "600002": (*_history(), *outcome),
    }

    cohort = find_daily_actionable_winners(
        signal_date=SIGNAL,
        outcome_dates=dates,
        bars_by_code=bars,
        risk_flags=(
            RiskFlag("600002", "ST", "VETO", SIGNAL, None, "fixture"),
        ),
        holding_codes=frozenset({"600001"}),
    )

    assert cohort.winners == ()


def test_next_five_dates_are_bounded_and_sorted() -> None:
    dates = tuple(SIGNAL + timedelta(days=index) for index in (3, 1, 6, 2, 5, 4))

    result = next_five_trading_dates(
        SIGNAL,
        dates,
        SIGNAL + timedelta(days=6),
    )

    assert result == tuple(SIGNAL + timedelta(days=index) for index in range(1, 6))


def test_daily_attribution_requires_the_same_signal_date() -> None:
    """Catches a Monday candidate being credited to a Tuesday winner."""
    winner_date = SIGNAL + timedelta(days=1)
    winner = DailyRecallWinner(
        "600001",
        winner_date,
        winner_date + timedelta(days=5),
        winner_date + timedelta(days=1),
        Decimal("10.00"),
        Decimal("0.06"),
        winner_date + timedelta(days=3),
    )
    replay = CaseSignalReplay(
        traces={
            (SIGNAL, "600001"): GateTrace(
                "600001",
                SIGNAL,
                ("INDEX_AND_BREADTH_WEAK",),
                ("LATEST_BAR",),
                {},
            ),
            (winner_date, "600001"): GateTrace(
                "600001",
                winner_date,
                ("NO_BUY_POINT_SETUP",),
                ("LATEST_BAR", "MARKET", "BASE"),
                {},
            ),
        },
        incomplete_dates=(),
        near_misses=(_candidate(SIGNAL),),
    )

    attributed = attribute_daily_recall_winners((winner,), replay)

    assert attributed[0].captured_tiers == ()
    assert attributed[0].first_rejection == "NO_BUY_POINT_SETUP"


def test_market_freeze_diagnostic_is_zero_share_and_does_not_add_candidates() -> None:
    """Catches research diagnosis bypassing the frozen market gate."""
    winner = DailyRecallWinner(
        "600001",
        SIGNAL,
        SIGNAL + timedelta(days=5),
        SIGNAL + timedelta(days=1),
        Decimal("10.00"),
        Decimal("0.06"),
        SIGNAL + timedelta(days=3),
        first_rejection="INDEX_AND_BREADTH_WEAK",
    )
    replay = CaseSignalReplay({}, (), (), ())

    rows = diagnose_market_freeze_winners(
        (winner,),
        bars_by_code={"600001": _platform_history()},
        risk_flags=(),
        holding_codes_by_date={SIGNAL: frozenset()},
    )

    assert len(rows) == 1
    assert rows[0].market_reason == "INDEX_AND_BREADTH_WEAK"
    assert rows[0].base_passed
    assert rows[0].setup_types == ("PRE_BREAKOUT",)
    assert rows[0].executable_shares == 0
    assert replay.strict_shadow == ()
    assert replay.near_misses == ()
