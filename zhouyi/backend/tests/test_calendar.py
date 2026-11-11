from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from zhouyi.calendar import normalize_cast_time


def test_normalizes_explicit_time_to_beijing_and_returns_known_ganzhi():
    snapshot = normalize_cast_time("2024-02-10T02:00:00+00:00")

    assert snapshot["beijing_time"] == "2024-02-10T10:00:00+08:00"
    assert snapshot["timezone"] == "Asia/Shanghai"
    assert snapshot["year_ganzhi"] == "甲辰"
    assert snapshot["month_ganzhi"] == "丙寅"
    assert snapshot["day_ganzhi"] == "甲辰"
    assert snapshot["hour_ganzhi"] == "己巳"
    assert snapshot["day_stem"] == "甲"
    assert snapshot["day_branch"] == "辰"
    assert snapshot["month_branch"] == "寅"
    assert snapshot["xunkong"] == ["寅", "卯"]
    assert snapshot["version"] == "beijing-midnight-v1"


def test_defaults_to_supplied_current_instant():
    now = datetime(2024, 2, 10, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    snapshot = normalize_cast_time(None, now=now)

    assert snapshot["input_time"] is None
    assert snapshot["beijing_time"] == "2024-02-10T10:00:00+08:00"


def test_rejects_time_without_timezone():
    with pytest.raises(ValueError, match="时区"):
        normalize_cast_time("2024-02-10T10:00:00")
