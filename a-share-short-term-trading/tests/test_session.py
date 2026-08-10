from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from short_term_trading.session import (
    TradingSession,
    classify_trading_session,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


class FixedCalendar:
    def __init__(
        self,
        status: bool | None,
        *,
        latest: date | None = date(2026, 8, 7),
        next_date: date | None = date(2026, 8, 11),
    ) -> None:
        self._status = status
        self._latest = latest
        self._next = next_date

    def status(self, value: date) -> bool | None:
        return self._status

    def latest_on_or_before(self, value: date) -> date | None:
        return self._latest

    def next_on_or_after(self, value: date) -> date | None:
        return self._next


def shanghai_datetime(clock: time) -> datetime:
    return datetime.combine(date(2026, 8, 10), clock, tzinfo=SHANGHAI)


@pytest.mark.parametrize(
    ("clock", "expected"),
    [
        (time(9, 29, 59), TradingSession.PRE_MARKET),
        (time(9, 30), TradingSession.INTRADAY),
        (time(11, 29, 59), TradingSession.INTRADAY),
        (time(11, 30), TradingSession.MIDDAY_BREAK),
        (time(12, 59, 59), TradingSession.MIDDAY_BREAK),
        (time(13, 0), TradingSession.INTRADAY),
        (time(14, 59, 59), TradingSession.INTRADAY),
        (time(15, 0), TradingSession.POST_MARKET),
    ],
)
def test_trading_session_boundaries(clock: time, expected: TradingSession) -> None:
    context = classify_trading_session(shanghai_datetime(clock), FixedCalendar(True))

    assert context.session is expected
    assert context.calendar_confirmed is True


def test_pre_market_uses_the_previous_confirmed_trade_date() -> None:
    context = classify_trading_session(
        shanghai_datetime(time(9, 0)), FixedCalendar(True)
    )

    assert context.diagnosis_trade_date == date(2026, 8, 7)
    assert context.next_trade_date == date(2026, 8, 10)


def test_closed_day_uses_confirmed_previous_and_next_dates() -> None:
    context = classify_trading_session(
        shanghai_datetime(time(10, 0)), FixedCalendar(False)
    )

    assert context.session is TradingSession.NON_TRADING_DAY
    assert context.calendar_confirmed is True
    assert context.diagnosis_trade_date == date(2026, 8, 7)
    assert context.next_trade_date == date(2026, 8, 11)


def test_unknown_calendar_safely_degrades_without_confirmed_dates() -> None:
    context = classify_trading_session(
        shanghai_datetime(time(10, 0)), FixedCalendar(None, latest=None, next_date=None)
    )

    assert context.session is TradingSession.NON_TRADING_DAY
    assert context.calendar_confirmed is False
    assert context.diagnosis_trade_date is None
    assert context.next_trade_date is None
    assert "无法确认" in context.reason


def test_naive_time_is_rejected_instead_of_assuming_a_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        classify_trading_session(datetime(2026, 8, 10, 10, 0), FixedCalendar(True))
