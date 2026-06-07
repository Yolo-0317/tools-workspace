"""market 分时段快讯融入（不改三节模板）。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_content import _market_title
from scripts.tools.wechat_mp_market_edition import (
    filter_news_for_edition,
    format_news_context_blob,
    normalize_market_edition,
)

TZ = ZoneInfo("Asia/Shanghai")


def test_normalize_edition_aliases() -> None:
    assert normalize_market_edition("pre") == "pre"
    assert normalize_market_edition("盘前") == "pre"
    assert normalize_market_edition("midday") == "midday"
    assert normalize_market_edition("close") == "close"


def test_filter_news_midday_excludes_early_morning() -> None:
    now = datetime(2026, 6, 2, 12, 5, tzinfo=TZ)
    items = [
        {"title": "凌晨快讯", "news_time": "06:30", "summary": "a"},
        {"title": "上午快讯", "news_time": "10:15", "summary": "b"},
    ]
    out = filter_news_for_edition(items, edition="midday", now=now)
    titles = [x["title"] for x in out]
    assert "上午快讯" in titles
    assert "凌晨快讯" not in titles


def test_news_context_not_numbered_list() -> None:
    blob = format_news_context_blob(
        [{"title": "油价波动", "summary": "中东局势", "news_time": "09:00", "sentiment": "bearish"}]
    )
    assert "仅供写作融合" in blob
    assert "素材1" in blob
    assert "1." not in blob.split("素材1")[0]


def test_market_title_by_edition() -> None:
    ai = "半导体走强，油价波动，指数震荡。"
    morning = datetime(2026, 6, 2, 9, 15, tzinfo=TZ)
    peer = "收盘复盘：油价+半导体牵动哪些线？"
    pre = _market_title(ai, now=morning, edition="pre", peer_title=peer)
    mid = _market_title(ai, now=morning, edition="midday")
    close = _market_title(ai, now=morning, edition="close")
    assert "牵动哪些线" not in pre
    assert "盘前" in pre or "开市" in pre or "开盘" in pre
