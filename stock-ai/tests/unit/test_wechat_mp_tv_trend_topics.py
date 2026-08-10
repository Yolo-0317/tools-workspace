"""影视热搜选题：双榜过滤与片名抽取。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_tv_trend_topics import (
    extract_show_title,
    is_tv_trend,
    merge_tv_trends,
    trend_item_to_topic,
)
from scripts.tools.wechat_mp_hot_trends import TrendRow


def test_is_tv_trend() -> None:
    assert is_tv_trend("凤囚凰 古偶烂片史上难以逾越的高峰")
    assert is_tv_trend("陈伟霆九门老九门出场对比")
    assert not is_tv_trend("显卡全面封仓")


def test_extract_show_title() -> None:
    assert extract_show_title("凤囚凰 古偶烂片史上难以逾越的高峰") == "凤囚凰"
    assert extract_show_title("陈伟霆九门老九门出场对比") == "九门"


def test_merge_tv_trends_scores_feng_qiu_huang() -> None:
    weibo = [
        TrendRow(title="凤囚凰 古偶烂片史上难以逾越的高峰", source="weibo", rank=17),
    ]
    merged = merge_tv_trends(weibo, [], limit=5)
    assert merged
    assert merged[0]["show_title"] == "凤囚凰"
    topic = trend_item_to_topic(merged[0])
    assert topic["title_zh"] == "凤囚凰"
    assert topic.get("from_trend") is True
    assert topic.get("douban_subject_id") == "26928226"
