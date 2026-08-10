"""HTTP 补源快讯抓取。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.fetch_eastmoney_macro_news import MacroNewsItem
from scripts.tools.fetch_supplemental_macro_news import (
    fetch_eastmoney_np_column_news,
    merge_macro_news_items,
)


def test_fetch_eastmoney_np_column_news_parses() -> None:
    payload = {
        "code": 1,
        "data": {
            "list": [
                {
                    "title": "央企密集增持、监管座谈护航！A股稳市机制托底市场",
                    "url": "http://stock.eastmoney.com/news/11791,202607203812645894.html",
                    "showTime": "2026-07-20 10:45:00",
                    "digest": "中国国新500亿元维护市场稳定",
                }
            ]
        },
    }

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    with patch(
        "scripts.tools.fetch_supplemental_macro_news.requests.get",
        return_value=FakeResp(),
    ):
        rows = fetch_eastmoney_np_column_news(column="350", biz="web_724", source="np_724")
    assert len(rows) == 1
    assert "稳市机制" in rows[0]["title"]
    assert rows[0]["time"] == "10:45"


def test_merge_macro_news_items_dedupes_by_href() -> None:
    a = MacroNewsItem(
        title="短摘要",
        summary="",
        time="10:00",
        href="https://x.com/1",
        source="kuaixun",
    )
    b = MacroNewsItem(
        title="短摘要",
        summary="中国国新500亿元维护市场稳定",
        time="10:00",
        href="https://x.com/1",
        source="np_724",
    )
    merged = merge_macro_news_items([a], [b])
    assert len(merged) == 1
    assert "500亿元" in merged[0].summary
