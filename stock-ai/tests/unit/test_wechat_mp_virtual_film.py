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
ANCHOR_EVIDENCE = (
    "把最后一碗热汤端上桌，两个人终于坐下来谈话。\n\n"
    "把歪掉的桌椅重新摆正，搭档转身挂起营业牌。"
)


def plot_anchors() -> list[dict[str, str]]:
    return [
        {
            "scene": "餐馆打烊前",
            "character": "主厨",
            "action": "把最后一碗热汤端上桌",
            "counterpart_or_pressure": "迟到的客人没有开口",
            "consequence": "两个人终于坐下来谈话",
            "source_url": "https://example.com/scene-one",
            "stage": "opening",
        },
        {
            "scene": "第二天重新开门",
            "character": "主厨",
            "action": "把歪掉的桌椅重新摆正",
            "counterpart_or_pressure": "搭档仍在犹豫是否留下",
            "consequence": "搭档转身挂起营业牌",
            "source_url": "https://example.com/scene-two",
            "stage": "turning_point",
        },
    ]


def film_card(**overrides: object) -> dict[str, object]:
    card: dict[str, object] = {
        "content_lane": "popular_film",
        "film_titles": ["一部电影"],
        "spoiler_level": "S0",
        "release_status": "released",
        "film_writing_mode": "scene_focus",
        "plot_anchors": plot_anchors(),
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
    body = f"{prefix}{ANCHOR_EVIDENCE}"
    padding = target_length - len(body) - len(DISCLOSURE) - 2
    assert padding > 0
    return f"{body}{'甲' * padding}\n\n{DISCLOSURE}"


def anchored_plain_copy(target_length: int, *, prefix: str = "") -> str:
    body = f"{prefix}{ANCHOR_EVIDENCE}"
    padding = target_length - len(body)
    assert padding >= 0
    return f"{body}{'甲' * padding}"


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


def test_popular_film_character_arc_accepts_s2() -> None:
    normalized = validate_film_topic_card(
        film_card(film_writing_mode="character_arc", spoiler_level="S2")
    )

    assert normalized["spoiler_level"] == "S2"


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


@pytest.mark.parametrize(
    ("image_count", "copy_length"),
    [
        (4, 180),
        (4, 320),
        (4, 400),
        (4, 550),
        (5, 550),
        (6, 750),
    ],
)
def test_popular_film_accepts_brief_and_feature_length_bands(
    image_count: int,
    copy_length: int,
) -> None:
    content = anchored_plain_copy(copy_length)

    assert (
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=content,
            card=film_card(ai_disclosure_mode="platform_publish"),
            image_count=image_count,
            has_original_images=False,
        )
        == content
    )


@pytest.mark.parametrize(
    ("image_count", "copy_length"),
    [
        (4, 321),
        (4, 399),
        (4, 551),
        (5, 549),
        (6, 751),
    ],
)
def test_popular_film_rejects_lengths_between_or_beyond_bands(
    image_count: int,
    copy_length: int,
) -> None:
    with pytest.raises(ValueError, match="popular_film 正文须为"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=anchored_plain_copy(copy_length),
            card=film_card(ai_disclosure_mode="platform_publish"),
            image_count=image_count,
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


def test_platform_publish_mode_allows_copy_without_body_disclosure() -> None:
    content = anchored_plain_copy(220)

    assert (
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=content,
            card=film_card(ai_disclosure_mode="platform_publish"),
            image_count=4,
            has_original_images=False,
        )
        == content
    )


def test_default_mode_still_requires_body_disclosure() -> None:
    with pytest.raises(ValueError, match="影视正文须披露"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=anchored_plain_copy(220),
            card=film_card(),
            image_count=4,
            has_original_images=False,
        )


def test_invalid_ai_disclosure_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="AI 声明模式"):
        validate_film_topic_card(film_card(ai_disclosure_mode="silent"))


def test_scene_focus_requires_two_plot_anchors() -> None:
    with pytest.raises(ValueError, match="scene_focus 须包含至少 2 个剧情锚点"):
        validate_film_topic_card(film_card(plot_anchors=plot_anchors()[:1]))


def test_scene_focus_requires_two_distinct_plot_anchors() -> None:
    anchors = plot_anchors()
    anchors[1] = dict(anchors[0])

    with pytest.raises(ValueError, match="不同剧情锚点"):
        validate_film_topic_card(film_card(plot_anchors=anchors))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("action", "", "缺少字段: action"),
        ("consequence", "", "缺少字段: consequence"),
        ("source_url", "http://example.com/scene", "HTTPS 来源"),
    ],
)
def test_plot_anchor_requires_action_consequence_and_https_source(
    field: str,
    value: str,
    message: str,
) -> None:
    anchors = plot_anchors()
    anchors[0][field] = value

    with pytest.raises(ValueError, match=message):
        validate_film_topic_card(film_card(plot_anchors=anchors))


def test_character_arc_requires_distinct_stages() -> None:
    anchors = plot_anchors()
    anchors[1]["stage"] = anchors[0]["stage"]

    with pytest.raises(ValueError, match="不同阶段"):
        validate_film_topic_card(
            film_card(film_writing_mode="character_arc", plot_anchors=anchors)
        )


def test_announced_film_requires_trailer_observation() -> None:
    with pytest.raises(ValueError, match="须使用 trailer_observation"):
        validate_film_topic_card(film_card(release_status="announced"))


def test_classic_list_does_not_require_single_film_anchors() -> None:
    card = film_card(
        content_lane="classic_list",
        film_titles=["甲片", "乙片", "丙片"],
        release_status="evergreen",
    )
    card.pop("film_writing_mode")
    card.pop("plot_anchors")

    normalized = validate_film_topic_card(card)

    assert "film_writing_mode" not in normalized
    assert "plot_anchors" not in normalized


def test_scene_focus_copy_requires_two_anchor_evidence_hits() -> None:
    content = "这部电影谈的是善意、选择和普通人的坚持。" + "甲" * 200

    with pytest.raises(ValueError, match="剧情锚点证据不足"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=content,
            card=film_card(ai_disclosure_mode="platform_publish"),
            image_count=4,
            has_original_images=False,
        )


def test_first_anchor_must_appear_in_first_two_paragraphs() -> None:
    opening = f"{'甲' * 55}\n\n{'乙' * 55}\n\n"
    content = anchored_plain_copy(220, prefix=opening)

    with pytest.raises(ValueError, match="前两个自然段"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=content,
            card=film_card(ai_disclosure_mode="platform_publish"),
            image_count=4,
            has_original_images=False,
        )


def test_anchor_in_second_multiline_paragraph_is_still_early_enough() -> None:
    opening = "第一段第一行。\n第一段第二行。\n\n"
    content = anchored_plain_copy(220, prefix=opening)

    assert (
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=content,
            card=film_card(ai_disclosure_mode="platform_publish"),
            image_count=4,
            has_original_images=False,
        )
        == content
    )


def test_trailer_observation_rejects_result_language() -> None:
    anchors = plot_anchors()[:1]
    content = anchored_plain_copy(220, prefix="预告观察：这个人物最终明白了答案。")

    with pytest.raises(ValueError, match="结果性观影口吻"):
        validate_film_copy(
            title="《一部电影》预告里的热汤",
            content=content,
            card=film_card(
                release_status="announced",
                film_writing_mode="trailer_observation",
                plot_anchors=anchors,
                ai_disclosure_mode="platform_publish",
            ),
            image_count=4,
            has_original_images=False,
        )


def test_copy_with_two_plot_anchors_passes() -> None:
    content = anchored_plain_copy(220)

    assert (
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=content,
            card=film_card(ai_disclosure_mode="platform_publish"),
            image_count=4,
            has_original_images=False,
        )
        == content
    )
