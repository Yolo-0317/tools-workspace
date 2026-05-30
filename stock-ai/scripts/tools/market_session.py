#!/usr/bin/env python3
"""A 股交易时段与行情时效判断。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

WEEKDAY_CN = "一二三四五六日"


@dataclass(frozen=True)
class MarketSession:
    now: datetime
    quote_trade_date: date | None
    quote_trade_time: time | None

    @property
    def today(self) -> date:
        return self.now.date()

    @property
    def is_calendar_trading_day(self) -> bool:
        return self.today.weekday() < 5

    @property
    def is_quote_from_today(self) -> bool:
        return self.quote_trade_date == self.today

    @property
    def is_a_share_session_active(self) -> bool:
        if not self.is_calendar_trading_day:
            return False
        t = self.now.time()
        return time(9, 30) <= t <= time(15, 0)

    @property
    def is_stale_a_share_quote(self) -> bool:
        """大盘/个股 A 股行情并非「当前交易日实时」。"""
        if self.quote_trade_date is None:
            return not self.is_calendar_trading_day
        if self.quote_trade_date < self.today:
            return True
        if not self.is_a_share_session_active and self.is_quote_from_today:
            # 交易日盘前/盘后：仍用今日收盘或昨收，需标注
            return self.now.time() >= time(15, 0) or self.now.time() < time(9, 30)
        return False

    def format_trade_date(self, d: date | None = None) -> str:
        d = d or self.quote_trade_date
        if d is None:
            return "未知日期"
        return f"{d.month}月{d.day}日（周{WEEKDAY_CN[d.weekday()]}）"

    def header_note(self) -> str:
        if not self.is_stale_a_share_quote and self.is_a_share_session_active:
            return "A股交易中，大盘与持仓为实时/准实时行情"
        if self.quote_trade_date is None:
            if not self.is_calendar_trading_day:
                return "今日非A股交易日，大盘与持仓暂无当日行情"
            return "大盘与持仓行情时效待确认"
        if self.quote_trade_date < self.today or not self.is_calendar_trading_day:
            return (
                f"今日非A股交易日（{self.format_trade_date(self.today)}），"
                f"大盘与持仓均为上一交易日 {self.format_trade_date()} 收盘数据"
            )
        if self.now.time() >= time(15, 0):
            return f"A股已收盘，大盘与持仓为今日 {self.format_trade_date()} 收盘数据"
        if self.now.time() < time(9, 30):
            return f"A股未开盘，大盘与持仓为上一交易日 {self.format_trade_date()} 收盘数据"
        return f"大盘与持仓截至 {self.format_trade_date()} 最新行情"

    def market_section_title(self) -> str:
        if self.is_stale_a_share_quote and self.quote_trade_date:
            return f"一、大盘（{self.format_trade_date()} 收盘）"
        return "一、大盘（最新）"

    def holdings_section_title(self) -> str:
        if self.is_stale_a_share_quote and self.quote_trade_date:
            return f"五、持仓个股（{self.format_trade_date()} 收盘）"
        return "五、持仓个股（最新）"

    def ai_session_hint(self, slot: str) -> str:
        base = self.header_note()
        if not self.is_calendar_trading_day:
            return (
                f"{base}。勿使用「今日大盘」「盘中」「收盘战报」等暗示 A 股当日交易的表述；"
                "应明确写「上一交易日收盘」或「休市期间」。东财7×24 快讯仍为实时。"
            )
        if self.is_stale_a_share_quote and self.quote_trade_date and self.quote_trade_date < self.today:
            return f"{base}。表述时使用「上一交易日（{self.format_trade_date()}）」而非「今日」。"
        if self.now.time() >= time(15, 0) and self.is_quote_from_today:
            return f"{base}。可称「今日 A 股已收盘」。"
        if self.now.time() < time(9, 30):
            return f"{base}。A 股尚未开盘，勿称「今日盘中」。"
        return base

    def slot_title(self, slot: str) -> str:
        titles = {
            "09:00": "盘中战报",
            "12:00": "午间战报",
            "15:00": "收盘战报",
            "20:00": "晚间战报",
        }
        if not self.is_calendar_trading_day:
            weekend = {
                "09:00": "休市早报",
                "12:00": "休市午间简报",
                "15:00": "休市简报",
                "20:00": "休市晚间简报",
            }
            return weekend.get(slot, "休市简报")
        if slot == "15:00" and self.is_stale_a_share_quote and not self.is_quote_from_today:
            return "休市简报"
        return titles.get(slot, "每日战报")


def parse_tencent_quote_timestamp(content: str, code: str = "sh000001") -> tuple[date | None, time | None]:
    match = re.search(rf'v_{re.escape(code)}="([^"]*)"', content)
    if not match:
        return None, None
    parts = match.group(1).split("~")
    if len(parts) <= 30:
        return None, None
    raw = parts[30].strip()
    if len(raw) < 8 or not raw[:8].isdigit():
        return None, None
    try:
        d = datetime.strptime(raw[:8], "%Y%m%d").date()
        t = None
        if len(raw) >= 14 and raw[8:14].isdigit():
            t = datetime.strptime(raw[8:14], "%H%M%S").time()
        return d, t
    except ValueError:
        return None, None


def detect_market_session(*, index_quote_content: str | None = None, now: datetime | None = None) -> MarketSession:
    now = now or datetime.now(TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    else:
        now = now.astimezone(TZ)

    quote_date = quote_time = None
    if index_quote_content:
        quote_date, quote_time = parse_tencent_quote_timestamp(index_quote_content)
    return MarketSession(now=now, quote_trade_date=quote_date, quote_trade_time=quote_time)
