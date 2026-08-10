"""11:00 话题讨论选题。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_tv_morning_discussion import (
    _discussion_bonus,
    discussion_item_to_topic,
    fetch_discussion_candidates,
)


def test_discussion_bonus_penalizes_gossip() -> None:
    gossip = _discussion_bonus("某明星红毯造型耳环路透")
    social = _discussion_bonus("公司拖欠打工人三个月工资")
    assert social > gossip


def test_fetch_discussion_candidates_excludes_stock() -> None:
    items = fetch_discussion_candidates(limit=30)
    titles = [str(x.get("title") or "") for x in items]
    assert not any("存储芯片" in t for t in titles)


def test_discussion_item_to_topic_mode() -> None:
    topic = discussion_item_to_topic(
        {
            "title": "曾舜晞说孟子义拍戏动过真感情",
            "sources": ["weibo"],
            "ranks": {"weibo": 14},
            "attention_score": 1050.0,
            "discussion_score": 1185.0,
        }
    )
    assert topic["content_mode"] == "discussion"
    assert topic.get("from_discussion_trend") is True


def test_tv_topic_uses_brand_cover() -> None:
    from scripts.tools.wechat_mp_tv_cover import tv_topic_uses_brand_cover

    assert tv_topic_uses_brand_cover({"content_mode": "discussion", "platform": "话题"})
    assert not tv_topic_uses_brand_cover({"title_zh": "铁拳教育", "platform": "Netflix"})


def test_pick_tv_draft_thumb_discussion_no_stock_fallback(monkeypatch) -> None:
    from scripts.tools.wechat_mp_tv_cover import pick_tv_draft_thumb

    topic = {
        "content_mode": "discussion",
        "platform": "话题",
        "cover_slug": "test-discussion-cover",
        "trend_title": "测试话题",
    }

    def boom(_topic: dict) -> Path:
        raise FileNotFoundError("缺事件配图")

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_figures.ensure_discussion_cover",
        boom,
    )
    kind, mid, err = pick_tv_draft_thumb(topic)
    assert mid is None
    assert err is not None
    assert kind == "discussion"
    assert "dragons" not in str(err.get("errmsg") or "")


def test_pick_tv_draft_thumb_discussion_uses_event_cover(monkeypatch) -> None:
    from scripts.tools.wechat_mp_tv_cover import pick_tv_draft_thumb

    topic = {
        "content_mode": "discussion",
        "platform": "话题",
        "cover_slug": "test-discussion-cover",
        "trend_title": "测试话题",
    }
    cover_path = Path(__file__).resolve().parents[2] / "assets" / "wechat_mp" / "inline-discussion" / "test-discussion-cover" / "cover.jpg"

    def fake_ensure(_topic: dict) -> Path:
        return cover_path

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_discussion_figures.ensure_discussion_cover",
        fake_ensure,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_tv_cover.pick_discussion_draft_thumb",
        lambda t, force_reupload=False: ("media_test_cover", None),
    )
    kind, mid, err = pick_tv_draft_thumb(topic)
    assert err is None
    assert kind == "discussion"
    assert mid == "media_test_cover"
