from __future__ import annotations

import pytest

from scripts.tools.wechat_mp_virtual_film import (
    validate_film_copy,
    validate_film_topic_card,
)


DISCLOSURE = (
    "栀夏是 AI 虚拟角色；本文为基于影片公开资料形成的原创内容，"
    "不对应真人观影经历。"
)


def film_card(**overrides: object) -> dict[str, object]:
    card: dict[str, object] = {
        "content_lane": "popular_film",
        "film_titles": ["一部电影"],
        "spoiler_level": "S0",
        "release_status": "released",
        "image_rights_status": [
            {
                "film_title": "一部电影",
                "source_name": "影片官方",
                "page_url": "https://example.com/official",
            }
        ],
    }
    card.update(overrides)
    return card


def valid_copy(target_length: int, *, prefix: str = "") -> str:
    padding = target_length - len(prefix) - len(DISCLOSURE) - 2
    assert padding > 0
    return f"{prefix}{'甲' * padding}\n\n{DISCLOSURE}"


def test_classic_list_requires_three_to_five_film_titles() -> None:
    card = film_card(
        content_lane="classic_list",
        film_titles=["一", "二"],
        release_status="evergreen",
    )

    with pytest.raises(ValueError, match="3-5"):
        validate_film_topic_card(card)


def test_popular_film_requires_s0() -> None:
    card = film_card(spoiler_level="S1")

    with pytest.raises(ValueError, match="S0"):
        validate_film_topic_card(card)


def test_classic_single_accepts_evergreen_s2() -> None:
    card = film_card(
        content_lane="classic_single",
        film_titles=["一部旧电影"],
        release_status="evergreen",
        spoiler_level="S2",
    )

    assert validate_film_topic_card(card)["spoiler_level"] == "S2"


def test_popular_film_requires_four_to_six_images() -> None:
    with pytest.raises(ValueError, match="4-6"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=valid_copy(220),
            card=film_card(),
            image_count=3,
            has_original_images=False,
        )


def test_classic_single_accepts_five_images_and_300_chars() -> None:
    card = film_card(
        content_lane="classic_single",
        film_titles=["一部旧电影"],
        release_status="evergreen",
        spoiler_level="S1",
    )
    content = valid_copy(300)

    assert (
        validate_film_copy(
            title="《一部旧电影》最难的不是告别",
            content=content,
            card=card,
            image_count=5,
            has_original_images=False,
        )
        == content
    )


@pytest.mark.parametrize(
    "phrase",
    [
        "作为 AI，我分析了",
        "经过资料检索",
        "根据内容规则",
        "刚从电影院出来",
        "昨晚二刷",
    ],
)
def test_copy_rejects_process_language_and_fake_viewing(phrase: str) -> None:
    with pytest.raises(ValueError, match="正文不得"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=valid_copy(220, prefix=phrase),
            card=film_card(),
            image_count=4,
            has_original_images=False,
        )


def test_s2_requires_spoiler_notice_at_start() -> None:
    card = film_card(
        content_lane="classic_single",
        film_titles=["一部旧电影"],
        release_status="evergreen",
        spoiler_level="S2",
    )

    with pytest.raises(ValueError, match="含结局讨论"):
        validate_film_copy(
            title="《一部旧电影》最难的不是告别",
            content=valid_copy(300),
            card=card,
            image_count=5,
            has_original_images=False,
        )


def test_single_film_title_must_appear_in_post_title() -> None:
    with pytest.raises(ValueError, match="标题须包含片名"):
        validate_film_copy(
            title="最安静的不是结尾",
            content=valid_copy(220),
            card=film_card(),
            image_count=4,
            has_original_images=False,
        )


def test_classic_list_title_requires_three_to_five_marker() -> None:
    card = film_card(
        content_lane="classic_list",
        film_titles=["甲片", "乙片", "丙片"],
        release_status="evergreen",
    )

    with pytest.raises(ValueError, match="数量"):
        validate_film_copy(
            title="适合关掉消息以后慢慢看的老片",
            content=valid_copy(400),
            card=card,
            image_count=6,
            has_original_images=False,
        )


def test_original_film_visual_requires_ai_generated_disclosure() -> None:
    with pytest.raises(ValueError, match="AI 生成示意图"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=valid_copy(220),
            card=film_card(),
            image_count=4,
            has_original_images=True,
        )
