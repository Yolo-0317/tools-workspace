"""栀夏影视贴图的选题卡与成稿门禁。"""

from __future__ import annotations

from typing import Any, Mapping


FILM_LANES = ("popular_film", "classic_single", "classic_list", "ai_film")
FILM_RULES = {
    "popular_film": {"images": (4, 6), "copy": (180, 320), "titles": (1, 1)},
    "classic_single": {"images": (5, 7), "copy": (250, 450), "titles": (1, 1)},
    "classic_list": {"images": (6, 9), "copy": (300, 600), "titles": (3, 5)},
    "ai_film": {"images": (4, 6), "copy": (180, 320), "titles": (1, 1)},
}
SPOILER_LEVELS = ("S0", "S1", "S2")
RELEASE_STATUSES = (
    "announced",
    "presale",
    "released",
    "reputation",
    "evergreen",
)
PROCESS_OR_FAKE_VIEWING_PHRASES = (
    "作为 AI",
    "作为AI",
    "经过资料检索",
    "根据内容规则",
    "根据写作规则",
    "刚从电影院出来",
    "刚看完",
    "我刚看完",
    "昨晚二刷",
    "今天二刷",
)
HYPE_PHRASES = (
    "一生必看",
    "封神",
    "全网泪崩",
    "后劲太大",
    "看懂的人都沉默了",
)


def _required_text(card: Mapping[str, Any], field: str) -> str:
    value = str(card.get(field) or "").strip()
    if not value:
        raise ValueError(f"影视选题卡缺少字段: {field}")
    return value


def validate_film_topic_card(card: Mapping[str, Any]) -> dict[str, Any]:
    """校验并规范化影视专用选题字段。"""

    normalized = dict(card)
    content_lane = _required_text(card, "content_lane")
    if content_lane not in FILM_LANES:
        raise ValueError("影视内容通道无效")
    normalized["content_lane"] = content_lane

    film_titles = card.get("film_titles")
    if not isinstance(film_titles, list):
        raise ValueError("影视选题卡 film_titles 须为数组")
    normalized_titles = [str(title).strip() for title in film_titles if str(title).strip()]
    minimum_titles, maximum_titles = FILM_RULES[content_lane]["titles"]
    if not minimum_titles <= len(normalized_titles) <= maximum_titles:
        raise ValueError(
            f"{content_lane} 须包含 {minimum_titles}-{maximum_titles} 个片名"
        )
    normalized["film_titles"] = normalized_titles

    spoiler_level = _required_text(card, "spoiler_level")
    if spoiler_level not in SPOILER_LEVELS:
        raise ValueError("影视剧透等级须为 S0 / S1 / S2")
    if content_lane in {"popular_film", "classic_list"} and spoiler_level != "S0":
        raise ValueError(f"{content_lane} 影视内容须使用 S0")
    normalized["spoiler_level"] = spoiler_level

    release_status = _required_text(card, "release_status")
    if release_status not in RELEASE_STATUSES:
        raise ValueError("影视上映状态无效")
    if content_lane == "popular_film" and release_status == "evergreen":
        raise ValueError("热门电影须填写当前上映或口碑阶段")
    if content_lane in {"classic_single", "classic_list"} and release_status != "evergreen":
        raise ValueError("经典电影内容须使用 evergreen")
    normalized["release_status"] = release_status

    image_rights_status = card.get("image_rights_status")
    if not isinstance(image_rights_status, list) or not image_rights_status:
        raise ValueError("影视选题卡须包含图片权属来源")
    normalized_sources: list[dict[str, str]] = []
    for source in image_rights_status:
        if not isinstance(source, Mapping):
            raise ValueError("影视图片权属来源格式无效")
        film_title = str(source.get("film_title") or "").strip()
        source_name = str(source.get("source_name") or "").strip()
        page_url = str(source.get("page_url") or "").strip()
        if not film_title or not source_name or not page_url.startswith("https://"):
            raise ValueError("影视图片权属来源须包含片名、来源名与 HTTPS 页面")
        normalized_sources.append(
            {
                "film_title": film_title,
                "source_name": source_name,
                "page_url": page_url,
            }
        )
    normalized["image_rights_status"] = normalized_sources
    return normalized


def validate_film_copy(
    *,
    title: str,
    content: str,
    card: Mapping[str, Any],
    image_count: int,
    has_original_images: bool,
) -> str:
    """校验影视标题、正文、剧透提示和成稿配图数量。"""

    normalized_card = validate_film_topic_card(card)
    content_lane = normalized_card["content_lane"]
    rules = FILM_RULES[content_lane]

    minimum_images, maximum_images = rules["images"]
    if not minimum_images <= image_count <= maximum_images:
        raise ValueError(
            f"{content_lane} 须使用 {minimum_images}-{maximum_images} 张图片"
        )

    normalized_title = title.strip()
    normalized_content = content.strip()
    minimum_copy, maximum_copy = rules["copy"]
    if not minimum_copy <= len(normalized_content) <= maximum_copy:
        raise ValueError(
            f"{content_lane} 正文须为 {minimum_copy}-{maximum_copy} 字"
        )

    if any(phrase in normalized_title or phrase in normalized_content for phrase in HYPE_PHRASES):
        raise ValueError("影视标题和正文不得使用夸张诱导表达")
    if any(phrase in normalized_content for phrase in PROCESS_OR_FAKE_VIEWING_PHRASES):
        raise ValueError("影视正文不得暴露生成过程或虚构真人观影经历")

    film_titles = normalized_card["film_titles"]
    if content_lane != "classic_list" and film_titles[0] not in normalized_title:
        raise ValueError("单片影视标题须包含片名")
    if content_lane == "classic_list":
        count_markers = {
            3: ("3", "三"),
            4: ("4", "四"),
            5: ("5", "五"),
        }
        if not any(marker in normalized_title for marker in count_markers[len(film_titles)]):
            raise ValueError("经典片单标题须标明影片数量")

    if "栀夏是 AI 虚拟角色" not in normalized_content or "不对应真人观影经历" not in normalized_content:
        raise ValueError("影视正文须披露栀夏为 AI 虚拟角色且不对应真人经历")
    if has_original_images and "AI 生成示意图" not in normalized_content:
        raise ValueError("使用原创影视视觉时须标注“AI 生成示意图”")

    if normalized_card["spoiler_level"] == "S2":
        first_line = next(
            (line.strip() for line in normalized_content.splitlines() if line.strip()),
            "",
        )
        if "含结局讨论" not in first_line:
            raise ValueError("S2 正文首行须标注“含结局讨论”")
    return normalized_content
