from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from scripts.tools.wechat_mp_virtual_editorial import (
    available_content_lanes,
    content_lane_counts,
    content_mix_counts,
    next_content_type,
    validate_opinion_copy,
    validate_topic_card,
)


TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 10, 17, 30, tzinfo=TZ)


def _valid_card(**overrides: object) -> dict[str, object]:
    card: dict[str, object] = {
        "topic": "这些中国风热词上新了",
        "observed_at": "2026-08-10T17:10:00+08:00",
        "discovery_platform": "百度热搜",
        "content_type": "A",
        "content_lane": "nonfilm_hotspot",
        "fact_sources": [
            {
                "url": "https://example.com/report",
                "title": "相关报道",
            }
        ],
        "contrast": "普通日常在另一个视角里成了新鲜生活方式",
        "zhixia_observation": "被重新命名的不是习惯，而是我们看待日常的距离",
        "click_reason": "喝热水获得了一个陌生的新名字",
        "image_plan": ["主题标题图", "保温杯静物", "栀夏作者卡"],
        "risks": [],
        "scores": {
            "timing": 22,
            "worker_relevance": 18,
            "zhixia_observation": 20,
            "visuals": 14,
            "persona_fit": 9,
        },
        "character_image_policy": "default_one",
        "visual_exception": "",
    }
    card.update(overrides)
    return card


def test_validate_topic_card_rejects_low_total_score() -> None:
    card = _valid_card(
        scores={
            "timing": 10,
            "worker_relevance": 15,
            "zhixia_observation": 14,
            "visuals": 15,
            "persona_fit": 10,
        }
    )

    with pytest.raises(ValueError, match="70"):
        validate_topic_card(card, now=NOW)


def test_validate_topic_card_rejects_weak_zhixia_observation_score() -> None:
    card = _valid_card(
        scores={
            "timing": 25,
            "worker_relevance": 20,
            "zhixia_observation": 14,
            "visuals": 15,
            "persona_fit": 10,
        }
    )

    with pytest.raises(ValueError, match="栀夏观察"):
        validate_topic_card(card, now=NOW)


def test_validate_topic_card_rejects_stale_hotspot() -> None:
    card = _valid_card(observed_at=(NOW - timedelta(hours=7)).isoformat())

    with pytest.raises(ValueError, match="6 小时"):
        validate_topic_card(card, now=NOW)


def test_validate_topic_card_allows_system_log_without_fact_source() -> None:
    card = _valid_card(
        content_type="C",
        content_lane="system_log",
        observed_at=(NOW - timedelta(days=1)).isoformat(),
        fact_sources=[],
        topic="删除过于完美的工位照",
    )

    normalized = validate_topic_card(card, now=NOW)

    assert normalized["content_type"] == "C"
    assert normalized["score_total"] == 83


def test_validate_opinion_copy_requires_mixed_image_disclosure() -> None:
    content = (
        "栀夏是 AI 虚拟角色；图片为 AI 生成示意图，不对应真人经历。"
        + "甲" * 170
    )

    with pytest.raises(ValueError, match="报道图来源见文中"):
        validate_opinion_copy(content, has_report_images=True)


def test_validate_opinion_copy_accepts_original_post_between_180_and_320_chars() -> None:
    content = (
        "栀夏是 AI 虚拟角色；图片为 AI 生成示意图，不对应真人经历。"
        + "甲" * 170
    )

    assert validate_opinion_copy(content, has_report_images=False) == content


def test_next_content_type_summarizes_four_three_two_one_round() -> None:
    posts = [
        *[{"content_type": "A", "status": "published"} for _ in range(4)],
        *[{"content_type": "B", "status": "published"} for _ in range(3)],
        *[{"content_type": "A+C", "status": "published"} for _ in range(2)],
    ]

    assert next_content_type(posts) == "C"


def test_mix_ignores_invalid_posts_and_previous_complete_round() -> None:
    posts = [
        *[{"content_type": "A", "status": "published"} for _ in range(4)],
        *[{"content_type": "B", "status": "published"} for _ in range(3)],
        *[{"content_type": "A+C", "status": "published"} for _ in range(2)],
        {"content_type": "C", "status": "published"},
        {"content_type": "C", "status": "invalid"},
        {"content_type": "A", "status": "published"},
    ]

    assert content_mix_counts(posts) == {"A": 1, "B": 0, "A+C": 0, "C": 0}
    assert next_content_type(posts) == "A"


def test_available_content_lanes_accepts_any_unfilled_lane() -> None:
    posts = [{"content_lane": "popular_film", "status": "published"}]

    available = available_content_lanes(posts)

    assert "popular_film" in available
    assert "classic_single" in available
    assert "system_log" in available


def test_filled_lane_is_removed_without_forcing_post_order() -> None:
    posts = [
        {"content_lane": "popular_film", "status": "published"},
        {"content_lane": "popular_film", "status": "published"},
    ]

    assert "popular_film" not in available_content_lanes(posts)
    assert "classic_list" in available_content_lanes(posts)


def test_lane_counts_ignore_invalid_and_previous_complete_round() -> None:
    first_round = [
        *[
            {"content_lane": "popular_film", "status": "published"}
            for _ in range(2)
        ],
        {"content_lane": "classic_single", "status": "published"},
        {"content_lane": "classic_list", "status": "published"},
        {"content_lane": "ai_film", "status": "published"},
        *[
            {"content_lane": "nonfilm_hotspot", "status": "published"}
            for _ in range(2)
        ],
        {"content_lane": "zhixia_daily", "status": "published"},
        {"content_lane": "ai_human", "status": "published"},
        {"content_lane": "system_log", "status": "published"},
    ]
    posts = [
        *first_round,
        {"content_lane": "popular_film", "status": "invalid"},
        {"content_lane": "classic_single", "status": "published"},
    ]

    assert content_lane_counts(posts)["classic_single"] == 1
    assert content_lane_counts(posts)["popular_film"] == 0


def test_validate_topic_card_rejects_lane_type_mismatch() -> None:
    card = _valid_card(content_type="B", content_lane="popular_film")

    with pytest.raises(ValueError, match="内容类型应为 A"):
        validate_topic_card(card, now=NOW)


def test_validate_topic_card_allows_stale_classic_single() -> None:
    card = _valid_card(
        content_type="B",
        content_lane="classic_single",
        observed_at=(NOW - timedelta(days=30)).isoformat(),
        character_image_policy="optional_one",
    )

    normalized = validate_topic_card(card, now=NOW)

    assert normalized["content_lane"] == "classic_single"
