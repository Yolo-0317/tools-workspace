"""news 头条开篇与转群文案。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_news_lede import (
    build_hot_stock_news_intro,
    extract_news_intro_from_body,
    format_group_share_copy,
)
from scripts.tools.wechat_mp_public import audit_recommendation_safety, sanitize_public_title


def _items() -> list[dict]:
    return [
        {
            "matched_stock_name": "洛阳钼业",
            "hot_stock_anchor_label": "6月16日收盘",
            "title": "铜价上行引发关注",
        },
        {"matched_stock_name": "铜冠铜箔", "hot_stock_anchor_label": "6月16日收盘"},
    ]


def test_hot_stock_intro_has_hook_and_digit() -> None:
    now = datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    intro = build_hot_stock_news_intro(_items(), now=now, hours=36)
    assert "洛阳钼业" in intro
    assert any(x in intro for x in ("先扫", "先读", "验证", "第1条"))
    assert re_digit(intro)


def test_hot_stock_intro_rotates_by_day() -> None:
    a = build_hot_stock_news_intro(
        _items(),
        now=datetime(2026, 6, 16, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=36,
    )
    b = build_hot_stock_news_intro(
        _items(),
        now=datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=36,
    )
    assert a != b


def test_intro_passes_platform_audit() -> None:
    intro = build_hot_stock_news_intro(
        _items(),
        now=datetime(2026, 6, 16, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=36,
    )
    assert audit_recommendation_safety(title="", body=intro, digest="") == []


def test_extract_intro_from_body() -> None:
    body = "> 要闻精选\n今天人气线落在洛阳钼业——铜价上行。\n\n1. [中性] 测试"
    assert "洛阳钼业" in extract_news_intro_from_body(body)


def test_group_share_copy() -> None:
    intro = "今天人气线落在洛阳钼业——铜价上行。下面10条只写验证。"
    out = format_group_share_copy(title="A股快讯｜洛阳钼业对照", intro=intro)
    assert "洛阳钼业" in out
    assert "A股快讯" in out


def re_digit(s: str) -> bool:
    import re

    return bool(re.search(r"\d", s))
