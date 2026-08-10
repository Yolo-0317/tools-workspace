"""A 股交易日历（上交所 SSE）；用于定时草稿批次等。"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
_CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "a_share_trade_cal.json"


def _read_cache() -> dict[str, Any]:
    if not _CACHE_PATH.is_file():
        return {"days": {}}
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"days": {}}
    if not isinstance(data.get("days"), dict):
        data["days"] = {}
    return data


def _write_cache(data: dict[str, Any]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(TZ).isoformat()
    _CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_trade_cal_range(start: date, end: date) -> dict[str, int]:
    """从 Tushare trade_cal 拉取 SSE 日历；无 token 时返回空 dict。"""
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        return {}
    try:
        import tushare as ts
    except ImportError:
        return {}

    ts.set_token(token)
    pro = ts.pro_api()
    df = pro.trade_cal(
        exchange="SSE",
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    if df is None or df.empty:
        return {}
    out: dict[str, int] = {}
    for _, row in df.iterrows():
        cal = str(row.get("cal_date") or "")
        if len(cal) == 8:
            iso = f"{cal[:4]}-{cal[4:6]}-{cal[6:8]}"
            out[iso] = int(row.get("is_open") or 0)
    return out


def refresh_trade_cal_cache(
    start: date | None = None,
    end: date | None = None,
) -> int:
    """刷新本地交易日缓存；返回写入天数。"""
    today = datetime.now(TZ).date()
    start = start or date(today.year - 1, 1, 1)
    end = end or date(today.year + 1, 12, 31)
    fetched = _fetch_trade_cal_range(start, end)
    if not fetched:
        return 0
    data = _read_cache()
    days: dict[str, int] = dict(data.get("days") or {})
    days.update(fetched)
    data["days"] = days
    _write_cache(data)
    return len(fetched)


def _lookup_cached(d: date) -> int | None:
    days = _read_cache().get("days") or {}
    key = d.isoformat()
    if key not in days:
        return None
    return int(days[key])


def _ensure_date_cached(d: date) -> None:
    if _lookup_cached(d) is not None:
        return
    refresh_trade_cal_cache(date(d.year, 1, 1), date(d.year, 12, 31))


def trading_day_status(d: date, *, refresh: bool = True) -> bool | None:
    """严格返回交易日状态；无法确认的工作日返回 None。"""

    if d.weekday() >= 5:
        return False
    flag = _lookup_cached(d)
    if flag is None and refresh:
        refresh_trade_cal_cache(date(d.year, 1, 1), date(d.year, 12, 31))
        flag = _lookup_cached(d)
    return None if flag is None else flag == 1


def is_a_share_trading_day(d: date | None = None) -> bool:
    """是否 A 股交易日。周末恒为 False；工作日查 SSE 日历（无缓存且无 token 时工作日暂按开市）。"""
    d = d or datetime.now(TZ).date()
    if d.weekday() >= 5:
        return False
    _ensure_date_cached(d)
    flag = _lookup_cached(d)
    if flag is None:
        return True
    return flag == 1


def latest_confirmed_a_share_trade_date(
    on_or_before: date,
) -> date | None:
    """返回不晚于指定日期的已确认交易日；遇到未知工作日即停止。"""

    current = on_or_before
    for _ in range(366):
        status = trading_day_status(current)
        if status is None:
            return None
        if status:
            return current
        current -= timedelta(days=1)
    return None


def next_confirmed_a_share_trade_date(
    on_or_after: date,
) -> date | None:
    """返回不早于指定日期的已确认交易日；遇到未知工作日即停止。"""

    current = on_or_after
    for _ in range(366):
        status = trading_day_status(current)
        if status is None:
            return None
        if status:
            return current
        current += timedelta(days=1)
    return None


def is_off_market_day(d: date | None = None) -> bool:
    """周末或法定节假日等非交易日（定时只推 news）。"""
    return not is_a_share_trading_day(d)


def latest_a_share_trade_date(*, on_or_before: date | None = None) -> date:
    """不晚于 on_or_before 的最近一个 A 股交易日（休市周末取周五等）。"""
    d = on_or_before or datetime.now(TZ).date()
    for _ in range(366):
        if is_a_share_trading_day(d):
            return d
        d -= timedelta(days=1)
    return on_or_before or datetime.now(TZ).date()


def next_a_share_trade_date(*, on_or_after: date | None = None) -> date:
    """不早于 on_or_after 的下一个 A 股交易日（周五后跳至下周一等）。"""
    d = on_or_after or datetime.now(TZ).date()
    for _ in range(366):
        if is_a_share_trading_day(d):
            return d
        d += timedelta(days=1)
    return on_or_after or datetime.now(TZ).date()
