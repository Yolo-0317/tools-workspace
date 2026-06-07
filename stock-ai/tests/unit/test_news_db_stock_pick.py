"""周末要闻：个股信号识别与优先入榜。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.news_db import news_item_has_stock_signal, pick_top_news_by_attention


def test_news_item_has_stock_signal_code() -> None:
    assert news_item_has_stock_signal({"title": "600519 股价异动", "summary": ""})
    assert news_item_has_stock_signal({"title": "某公司涨停", "summary": "新能源板块"})


def test_news_item_has_stock_signal_macro_only() -> None:
    assert not news_item_has_stock_signal(
        {"title": "美联储维持利率不变", "summary": "美元指数走强"}
    )


def test_pick_top_news_prefer_stock_orders_stock_first() -> None:
    pool = [
        {"href": "https://a.com/1", "title": "美联储降息预期升温", "summary": "宏观"},
        {"href": "https://a.com/2", "title": "某某股份涨停", "summary": "600001"},
        {"href": "https://a.com/3", "title": "中东局势", "summary": "原油"},
        {"href": "https://a.com/4", "title": "龙头公司业绩预增", "summary": "净利润"},
    ]
    # monkeypatch pool loader
    import scripts.tools.news_db as ndb

    orig = ndb.load_news_pool_for_attention
    ndb.load_news_pool_for_attention = lambda **kw: list(pool)  # type: ignore[assignment]
    try:
        out = pick_top_news_by_attention(
            limit=3,
            hours=72,
            pool_limit=10,
            engagement=None,
            prefer_stock=True,
        )
    finally:
        ndb.load_news_pool_for_attention = orig  # type: ignore[assignment]

    assert len(out) == 3
    assert sum(1 for x in out if x["has_stock_signal"]) >= 2
    assert news_item_has_stock_signal(out[0])
    assert not news_item_has_stock_signal(out[-1])
