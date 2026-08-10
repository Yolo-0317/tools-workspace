"""影视标题：参考真人剧评套路。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_tv_title import (
    TV_TITLE_FORBIDDEN_RE,
    build_tv_title_candidates,
    pick_tv_review_title,
)


def test_tv_title_no_forbidden_phrases() -> None:
    topic = {
        "title_zh": "凤囚凰",
        "from_trend": True,
        "trend_title": "凤囚凰 古偶烂片史上难以逾越的高峰",
        "platform": "湖南卫视 / 爱奇艺",
        "type": "series",
        "heat_score": 72,
        "ratings": {"douban": {"score": 3.8}},
    }
    title = pick_tv_review_title(topic, now=datetime(2026, 7, 31, tzinfo=ZoneInfo("Asia/Shanghai")))
    assert not TV_TITLE_FORBIDDEN_RE.search(title)
    assert "又上热搜" not in title
    assert len(title) <= 32


def test_spider_man_title_uses_douban_pattern() -> None:
    topic = {
        "title_zh": "蜘蛛侠：崭新之日",
        "type": "film",
        "platform": "院线 / 漫威",
        "trend_title": "《蜘蛛侠：崭新之日》好看吗",
        "heat_score": 71,
        "ratings": {"douban": {"score": 7.8}},
    }
    cands = build_tv_title_candidates(topic)
    assert any("豆瓣7.8" in c for c in cands)
    title = pick_tv_review_title(topic)
    assert len(title) <= 32
    assert "热搜" not in title
