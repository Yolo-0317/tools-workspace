"""A-share session classification in Asia/Shanghai."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from .models import SessionContext


SHANGHAI = ZoneInfo("Asia/Shanghai")


class TradingCalendar(Protocol):
    def status(self, value): ...
    def latest_on_or_before(self, value): ...
    def next_on_or_after(self, value): ...


def _clock_session(value: time) -> str:
    if value < time(9, 30):
        return "PRE_MARKET"
    if value < time(11, 30):
        return "INTRADAY"
    if value < time(13, 0):
        return "MIDDAY_BREAK"
    if value < time(15, 0):
        return "INTRADAY"
    return "POST_MARKET"


def classify_session(now: datetime, calendar: TradingCalendar) -> SessionContext:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("诊断时间必须包含时区")
    local_now = now.astimezone(SHANGHAI)
    today = local_now.date()
    status = calendar.status(today)
    if status is None:
        return SessionContext(
            session="NON_TRADING_DAY",
            local_now=local_now,
            calendar_confirmed=False,
            diagnosis_trade_date=None,
            next_trade_date=None,
            reason="SSE 交易日历未覆盖当前日期",
        )
    if not status:
        return SessionContext(
            session="NON_TRADING_DAY",
            local_now=local_now,
            calendar_confirmed=True,
            diagnosis_trade_date=calendar.latest_on_or_before(today),
            next_trade_date=calendar.next_on_or_after(today),
            reason="SSE 交易日历确认今日休市",
        )

    session = _clock_session(local_now.time().replace(tzinfo=None))
    if session == "PRE_MARKET":
        diagnosis_date = calendar.latest_on_or_before(today - timedelta(days=1))
        next_date = today
        reason = "交易日盘前，使用上一完整交易日数据"
    elif session == "POST_MARKET":
        diagnosis_date = today
        next_date = calendar.next_on_or_after(today + timedelta(days=1))
        reason = "交易日盘后，使用今日完整收盘数据"
    else:
        diagnosis_date = today
        next_date = today
        reason = "交易日盘中，指标仍以最近完整日线为准"
    return SessionContext(
        session=session,
        local_now=local_now,
        calendar_confirmed=True,
        diagnosis_trade_date=diagnosis_date,
        next_trade_date=next_date,
        reason=reason,
    )
