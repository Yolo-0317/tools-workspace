"""Versioned Beijing-time calendar snapshot for Najia charts."""

from datetime import datetime
from zoneinfo import ZoneInfo

from lunar_python import Solar


BEIJING = ZoneInfo("Asia/Shanghai")
CALENDAR_VERSION = "beijing-midnight-v1"


def normalize_cast_time(value: str | None, *, now: datetime | None = None) -> dict:
    if value is None:
        moment = now or datetime.now(BEIJING)
        input_time = None
    else:
        input_time = value
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise ValueError("起卦时间格式无效") from None
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("起卦时间必须包含时区")
    beijing = moment.astimezone(BEIJING).replace(microsecond=0)
    lunar = Solar.fromYmdHms(
        beijing.year,
        beijing.month,
        beijing.day,
        beijing.hour,
        beijing.minute,
        beijing.second,
    ).getLunar()
    eight = lunar.getEightChar()
    return {
        "input_time": input_time,
        "beijing_time": beijing.isoformat(),
        "timezone": "Asia/Shanghai",
        "year_ganzhi": eight.getYear(),
        "month_ganzhi": eight.getMonth(),
        "day_ganzhi": eight.getDay(),
        "hour_ganzhi": eight.getTime(),
        "day_stem": eight.getDayGan(),
        "day_branch": eight.getDayZhi(),
        "month_branch": eight.getMonthZhi(),
        "xunkong": list(eight.getDayXunKong()),
        "version": CALENDAR_VERSION,
    }
