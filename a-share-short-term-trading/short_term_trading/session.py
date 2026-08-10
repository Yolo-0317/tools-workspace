"""Pure A-share trading-session classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Protocol
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")


class TradingSession(str, Enum):
    PRE_MARKET = "PRE_MARKET"
    INTRADAY = "INTRADAY"
    MIDDAY_BREAK = "MIDDAY_BREAK"
    POST_MARKET = "POST_MARKET"
    NON_TRADING_DAY = "NON_TRADING_DAY"


class TradingCalendar(Protocol):
    def status(self, value: date) -> bool | None:
        raise NotImplementedError

    def latest_on_or_before(self, value: date) -> date | None:
        raise NotImplementedError

    def next_on_or_after(self, value: date) -> date | None:
        raise NotImplementedError


@dataclass(frozen=True)
class TradingSessionContext:
    session: TradingSession
    now_utc: datetime
    local_now: datetime
    calendar_confirmed: bool
    diagnosis_trade_date: date | None
    next_trade_date: date | None
    reason: str


def _session_for_clock(clock: time) -> TradingSession:
    if clock < time(9, 30):
        return TradingSession.PRE_MARKET
    if time(9, 30) <= clock < time(11, 30):
        return TradingSession.INTRADAY
    if time(11, 30) <= clock < time(13, 0):
        return TradingSession.MIDDAY_BREAK
    if time(13, 0) <= clock < time(15, 0):
        return TradingSession.INTRADAY
    return TradingSession.POST_MARKET


def classify_trading_session(
    now: datetime,
    calendar: TradingCalendar,
) -> TradingSessionContext:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    local_now = now.astimezone(SHANGHAI)
    now_utc = now.astimezone(timezone.utc)
    today = local_now.date()
    status = calendar.status(today)
    if status is None:
        return TradingSessionContext(
            session=TradingSession.NON_TRADING_DAY,
            now_utc=now_utc,
            local_now=local_now,
            calendar_confirmed=False,
            diagnosis_trade_date=None,
            next_trade_date=None,
            reason="SSE 交易日历无法确认，已安全降级为不可交易诊断",
        )
    if not status:
        return TradingSessionContext(
            session=TradingSession.NON_TRADING_DAY,
            now_utc=now_utc,
            local_now=local_now,
            calendar_confirmed=True,
            diagnosis_trade_date=calendar.latest_on_or_before(today),
            next_trade_date=calendar.next_on_or_after(today),
            reason="SSE 交易日历标记今日休市",
        )

    session = _session_for_clock(local_now.time().replace(tzinfo=None))
    if session is TradingSession.PRE_MARKET:
        diagnosis_date = calendar.latest_on_or_before(today - timedelta(days=1))
        next_date = today
        reason = "交易日盘前，使用上一已完成交易日数据"
    elif session is TradingSession.POST_MARKET:
        diagnosis_date = today
        next_date = calendar.next_on_or_after(today + timedelta(days=1))
        reason = "交易日盘后，使用今日已完成收盘数据"
    elif session is TradingSession.MIDDAY_BREAK:
        diagnosis_date = today
        next_date = today
        reason = "交易日午间休市，买入放行暂停"
    else:
        diagnosis_date = today
        next_date = today
        reason = "交易日连续竞价时段"

    return TradingSessionContext(
        session=session,
        now_utc=now_utc,
        local_now=local_now,
        calendar_confirmed=True,
        diagnosis_trade_date=diagnosis_date,
        next_trade_date=next_date,
        reason=reason,
    )
