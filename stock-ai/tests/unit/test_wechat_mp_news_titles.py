"""news 头条标题池：按日轮换 + 合规。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_content import _news_title
from scripts.tools.wechat_mp_news_titles import build_hot_stock_news_title_options
from scripts.tools.wechat_mp_public import audit_recommendation_safety, sanitize_public_title


def _items() -> list[dict]:
    return [
        {"matched_stock_name": "洛阳钼业", "hot_stock_anchor_label": "收盘", "title": "铜价上行引发关注"},
        {"matched_stock_name": "铜冠铜箔", "hot_stock_anchor_label": "收盘"},
        {"title": "宏观"},
    ]


def test_hot_stock_news_title_rotates_by_day(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_HOT_STOCK_NEWS", "1")
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "evening")
    items = _items()
    t1 = _news_title(
        items,
        now=datetime(2026, 6, 16, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        peer_title=None,
    )
    t2 = _news_title(
        items,
        now=datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        peer_title=None,
    )
    assert t1 != t2
    assert "洛阳钼业" in t1[:18]
    assert "A股人气" not in t1


def test_hot_stock_news_title_passes_platform_audit(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_HOT_STOCK_NEWS", "1")
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "evening")
    title = _news_title(
        _items(),
        now=datetime(2026, 6, 11, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        peer_title=None,
    )
    safe = sanitize_public_title(title, kind="news")
    assert audit_recommendation_safety(title=safe, body="", digest="") == []
    for bad in ("必读", "怎么玩", "还在榜", "领衔", "明日盯", "盯啥"):
        assert bad not in safe


def test_title_options_rotate_seed() -> None:
    items = _items()
    now_a = datetime(2026, 6, 10, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    now_b = datetime(2026, 6, 11, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    a = build_hot_stock_news_title_options(items, now=now_a, n_label="10", weekend=False)[0][0]
    b = build_hot_stock_news_title_options(items, now=now_b, n_label="10", weekend=False)[0][0]
    assert a != b


def test_hot_stock_news_title_rejects_rank_meta_as_event(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_HOT_STOCK_NEWS", "1")
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "evening")
    items = [
        {
            "matched_stock_name": "中际旭创",
            "hot_stock_anchor_label": "收盘",
            "title": "中际旭创人气榜首，涨2.1%待验证",
        },
        {"matched_stock_name": "太极实业", "hot_stock_anchor_label": "收盘"},
    ]
    title = _news_title(
        items,
        now=datetime(2026, 7, 28, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        peer_title=None,
    )
    assert "背景下" not in title
    assert title.count("中际旭创") <= 1
    assert "中际旭创" in title[:18]


def test_hot_stock_news_title_single_lead_no_pair_echo(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_HOT_STOCK_NEWS", "1")
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "evening")
    items = [
        {"matched_stock_name": "中际旭创", "hot_stock_anchor_label": "收盘", "title": "光模块需求"},
    ]
    title = _news_title(
        items,
        now=datetime(2026, 7, 28, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        peer_title=None,
    )
    assert "与中际旭创" not in title
    assert "人气标的与人气标的" not in title
