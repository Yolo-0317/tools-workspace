"""A 股交易日历。"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.trading_calendar import (
    is_a_share_trading_day,
    is_off_market_day,
    latest_confirmed_a_share_trade_date,
    next_confirmed_a_share_trade_date,
    trading_day_status,
)


@pytest.fixture
def trade_cal_cache(tmp_path, monkeypatch):
    cache_file = tmp_path / "a_share_trade_cal.json"
    monkeypatch.setattr("stock_ai.trading_calendar._CACHE_PATH", cache_file)
    return cache_file


def test_weekend_not_trading(trade_cal_cache) -> None:
    sat = date(2026, 6, 6)
    assert is_a_share_trading_day(sat) is False
    assert is_off_market_day(sat) is True


def test_weekday_open_from_cache(trade_cal_cache) -> None:
    trade_cal_cache.write_text(
        json.dumps({"days": {"2026-06-03": 1}}, ensure_ascii=False),
        encoding="utf-8",
    )
    wed = date(2026, 6, 3)
    assert is_a_share_trading_day(wed) is True
    assert is_off_market_day(wed) is False


def test_weekday_holiday_from_cache(trade_cal_cache) -> None:
    trade_cal_cache.write_text(
        json.dumps({"days": {"2026-01-02": 0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    holiday = date(2026, 1, 2)  # 周五假定为休市
    assert holiday.weekday() < 5
    assert is_a_share_trading_day(holiday) is False
    assert is_off_market_day(holiday) is True


def test_strict_status_distinguishes_cached_days_from_an_unknown_weekday(
    trade_cal_cache, monkeypatch
) -> None:
    trade_cal_cache.write_text(
        json.dumps({"days": {"2026-08-07": 1, "2026-08-10": 0}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "stock_ai.trading_calendar.refresh_trade_cal_cache", lambda *args: 0
    )

    assert trading_day_status(date(2026, 8, 7)) is True
    assert trading_day_status(date(2026, 8, 10)) is False
    assert trading_day_status(date(2026, 8, 11)) is None


def test_confirmed_dates_cross_known_closed_days(trade_cal_cache, monkeypatch) -> None:
    trade_cal_cache.write_text(
        json.dumps(
            {
                "days": {
                    "2026-08-07": 1,
                    "2026-08-10": 0,
                    "2026-08-11": 1,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "stock_ai.trading_calendar.refresh_trade_cal_cache", lambda *args: 0
    )

    assert latest_confirmed_a_share_trade_date(date(2026, 8, 10)) == date(2026, 8, 7)
    assert next_confirmed_a_share_trade_date(date(2026, 8, 8)) == date(2026, 8, 11)


def test_confirmed_date_stops_when_an_intervening_weekday_is_unknown(
    trade_cal_cache, monkeypatch
) -> None:
    trade_cal_cache.write_text(
        json.dumps({"days": {"2026-08-07": 1}}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "stock_ai.trading_calendar.refresh_trade_cal_cache", lambda *args: 0
    )

    assert latest_confirmed_a_share_trade_date(date(2026, 8, 10)) is None
    assert next_confirmed_a_share_trade_date(date(2026, 8, 10)) is None


def test_resolve_batch_holiday_weekday(trade_cal_cache, monkeypatch) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from scripts._bootstrap import ensure_repo_root_on_path
    from scripts.tools.wechat_mp_draft_batch import resolve_scheduled_batch
    import scripts.tools.wechat_mp_tv_review_article

    monkeypatch.setattr(scripts.tools.wechat_mp_tv_review_article, "tv_trial_active", lambda **kwargs: False)

    ensure_repo_root_on_path()
    trade_cal_cache.write_text(
        json.dumps({"days": {"2026-01-02": 0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    dt = datetime(2026, 1, 2, 19, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert resolve_scheduled_batch(now=dt) == "weekend"
