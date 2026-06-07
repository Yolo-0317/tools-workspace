"""ensure_daily_bars 期望交易日与就绪判断。"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools import ensure_daily_bars as edb

TZ = ZoneInfo("Asia/Shanghai")


def test_expected_latest_trade_date_weekday_before_17():
    now = datetime(2026, 6, 4, 16, 0, tzinfo=TZ)  # Thu
    assert edb.expected_latest_trade_date(now, tushare_ready_hour=17) == date(2026, 6, 3)


def test_expected_latest_trade_date_weekday_after_17():
    now = datetime(2026, 6, 4, 18, 0, tzinfo=TZ)
    assert edb.expected_latest_trade_date(now, tushare_ready_hour=17) == date(2026, 6, 4)


def test_expected_latest_trade_date_saturday():
    now = datetime(2026, 6, 6, 12, 0, tzinfo=TZ)  # Sat
    assert edb.expected_latest_trade_date(now, tushare_ready_hour=17) == date(2026, 6, 5)


def test_check_daily_bars_ready_when_max_and_count_ok():
    expected = date(2026, 6, 4)
    with (
        patch.object(edb, "expected_latest_trade_date", return_value=expected),
        patch.object(edb, "get_db_max_trade_date", return_value=expected),
        patch.object(edb, "get_trade_date_bar_count", return_value=4000),
        patch.object(edb, "min_expected_bar_count", return_value=3500),
    ):
        ready, info = edb.check_daily_bars_ready()
    assert ready is True
    assert info["bar_count"] == 4000


def test_check_daily_bars_ready_when_count_low():
    expected = date(2026, 6, 4)
    with (
        patch.object(edb, "expected_latest_trade_date", return_value=expected),
        patch.object(edb, "get_db_max_trade_date", return_value=expected),
        patch.object(edb, "get_trade_date_bar_count", return_value=100),
        patch.object(edb, "min_expected_bar_count", return_value=3500),
    ):
        ready, _ = edb.check_daily_bars_ready()
    assert ready is False
