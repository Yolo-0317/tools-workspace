"""增长模型：大行情判定、通知块、news 标题池。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_content import _news_title
from scripts.tools.wechat_mp_growth import (
    evaluate_market_day,
    format_growth_notify_block,
    load_growth_focus,
)


def test_evaluate_market_day_recommends_on_signals() -> None:
    bundle = {
        "header": {
            "limit_up_count": 50,
            "limit_down_count": 5,
            "max_board_height": 5,
            "phase": "高潮",
            "theme_count": 1,
            "main_theme": "机器人",
            "explode_rate_pct": 40,
        }
    }
    ev = evaluate_market_day(bundle=bundle)
    assert ev.recommend_market
    assert len(ev.signals) >= 2


def test_evaluate_market_day_skip_quiet_day() -> None:
    bundle = {
        "header": {
            "limit_up_count": 15,
            "limit_down_count": 10,
            "max_board_height": 2,
            "phase": "启动",
            "theme_count": 5,
            "main_theme": "杂糅",
        }
    }
    ev = evaluate_market_day(bundle=bundle)
    assert not ev.recommend_market


def test_growth_notify_block_evening() -> None:
    text = format_growth_notify_block(batch="evening")
    assert "增长模型" in text
    assert "KPI" in text


def test_hot_stock_news_title_leads_with_stock_names(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_HOT_STOCK_NEWS", "1")
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "evening")
    items = [
        {"matched_stock_name": "京东方A", "hot_stock_anchor_label": "收盘"},
        {"matched_stock_name": "亨通光电", "hot_stock_anchor_label": "收盘"},
        {"title": "某宏观"},
    ]
    now = datetime(2026, 6, 11, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    title = _news_title(items, now=now, peer_title=None)
    assert "京东方" in title[:20]
    assert "必读" not in title
    assert "怎么读" not in title


def test_load_growth_focus_file() -> None:
    path = ROOT / "data" / "wechat_mp_growth_focus.json"
    assert path.is_file()
    focus = load_growth_focus(path=path)
    assert focus.evening_kinds == ("news", "hotspot")
    assert focus.read_target >= 80
    assert focus.stock_ai_cta_enabled is True
    assert 0 in focus.distribution_weekdays


def test_is_distribution_day_daily() -> None:
    from scripts.tools.wechat_mp_growth import is_distribution_day

    tue = datetime(2026, 6, 9, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    wed = datetime(2026, 6, 10, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert is_distribution_day(when=tue) is True
    assert is_distribution_day(when=wed) is True
