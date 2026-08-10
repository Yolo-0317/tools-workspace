"""稳市要闻 attention 加分。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.news_db import (
    _attention_score,
    is_market_rescue_news,
    market_rescue_attention_boost,
    pick_top_news_by_attention,
)


def test_is_market_rescue_news_strong() -> None:
    item = {
        "title": "央企密集增持、监管座谈护航！A股稳市机制托底市场",
        "summary": "中国国新已使用超500亿元维护市场稳定",
    }
    assert is_market_rescue_news(item)
    assert market_rescue_attention_boost(item) >= 120.0


def test_rescue_beats_geo_in_attention_score() -> None:
    rescue = {
        "title": "中国国新和中国诚通宣布继续增持",
        "summary": "使用股票回购增持专项再贷款及配套资金超500亿元维护市场稳定",
        "published_at": "2026-07-22 10:00:00",
        "last_seen_at": "2026-07-22 10:00:00",
    }
    geo = {
        "title": "美国务卿：美国仍愿意通过外交途径解决伊朗问题",
        "summary": "中东局势持续",
        "published_at": "2026-07-22 10:00:00",
        "last_seen_at": "2026-07-22 10:00:00",
    }
    assert _attention_score(rescue, None) > _attention_score(geo, None)


def test_500yi_not_match_inside_3500yi() -> None:
    from scripts.tools.news_db import is_market_rescue_news

    item = {
        "title": "上海海洋产业增加值不低于3500亿元",
        "summary": "",
    }
    assert not is_market_rescue_news(item)
    assert _attention_score(item, None) < 10


def test_session_theme_boost_zero_for_other_day() -> None:
    from scripts.tools.news_db import session_theme_attention_boost

    item = {
        "title": "科技股早盘上演V型反转 跌停潮后半导体领涨反弹",
        "summary": "",
        "published_at": "2026-07-21 11:13:00",
        "last_seen_at": "2026-07-21 11:13:00",
    }
    assert session_theme_attention_boost(item) == 0.0


def test_pick_top_news_rescue_ranks_first() -> None:
    pool = [
        {
            "href": "https://a.com/geo",
            "title": "美军称完成连续第九晚对伊朗袭击",
            "summary": "中东 伊朗",
        },
        {
            "href": "https://a.com/rescue",
            "title": "央企密集增持、监管座谈护航！A股稳市机制托底市场",
            "summary": "中国国新500亿元维护市场稳定 证监会座谈会",
        },
        {
            "href": "https://a.com/tech",
            "title": "我国智能算力规模达2185EFLOPS",
            "summary": "算力",
        },
    ]
    import scripts.tools.news_db as ndb

    orig = ndb.load_news_pool_for_attention
    ndb.load_news_pool_for_attention = lambda **kw: list(pool)  # type: ignore[assignment]
    try:
        out = pick_top_news_by_attention(limit=1, hours=72, pool_limit=10, engagement=None)
    finally:
        ndb.load_news_pool_for_attention = orig  # type: ignore[assignment]

    assert out[0]["title"].startswith("央企密集增持")
