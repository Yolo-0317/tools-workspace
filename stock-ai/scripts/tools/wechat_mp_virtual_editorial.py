"""栀夏观点型贴图的选题卡、文案与内容比例门禁。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")
CONTENT_TYPES = ("A", "B", "A+C", "C")
CONTENT_LANES = (
    "popular_film",
    "classic_single",
    "classic_list",
    "ai_film",
    "nonfilm_hotspot",
    "zhixia_daily",
    "ai_human",
    "system_log",
)
LANE_TARGETS = {
    "popular_film": 2,
    "classic_single": 1,
    "classic_list": 1,
    "ai_film": 1,
    "nonfilm_hotspot": 2,
    "zhixia_daily": 1,
    "ai_human": 1,
    "system_log": 1,
}
LANE_CONTENT_TYPES = {
    "popular_film": "A",
    "classic_single": "B",
    "classic_list": "B",
    "ai_film": "A+C",
    "nonfilm_hotspot": "A",
    "zhixia_daily": "B",
    "ai_human": "A+C",
    "system_log": "C",
}
FILM_LANES = {"popular_film", "classic_single", "classic_list", "ai_film"}
TIME_SENSITIVE_LANES = {"popular_film", "nonfilm_hotspot"}
CHARACTER_POLICIES = ("default_one", "optional_one", "story_multiple")
SCORE_FIELDS = (
    "timing",
    "worker_relevance",
    "zhixia_observation",
    "visuals",
    "persona_fit",
)
REQUIRED_FIELDS = (
    "topic",
    "observed_at",
    "discovery_platform",
    "content_type",
    "content_lane",
    "fact_sources",
    "contrast",
    "zhixia_observation",
    "click_reason",
    "image_plan",
    "risks",
    "scores",
    "character_image_policy",
)
ROUND_TARGETS = {"A": 4, "B": 3, "A+C": 2, "C": 1}
MIN_SCORE = 70
MIN_OBSERVATION_SCORE = 15
HOTSPOT_MAX_AGE_SECONDS = 6 * 60 * 60
COPY_RANGE = (400, 900)


def load_topic_card(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"栀夏选题卡无效: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("栀夏选题卡必须是 JSON 对象")
    return payload


def _required_text(card: Mapping[str, Any], field: str) -> str:
    value = str(card.get(field) or "").strip()
    if not value:
        raise ValueError(f"栀夏选题卡缺少字段: {field}")
    return value


def validate_topic_card(
    card: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    for field in REQUIRED_FIELDS:
        if field not in card:
            raise ValueError(f"栀夏选题卡缺少字段: {field}")

    normalized = dict(card)
    for field in (
        "topic",
        "observed_at",
        "discovery_platform",
        "contrast",
        "zhixia_observation",
        "click_reason",
    ):
        normalized[field] = _required_text(card, field)

    content_type = _required_text(card, "content_type")
    if content_type not in CONTENT_TYPES:
        raise ValueError("栀夏内容类型须为 A / B / A+C / C")
    normalized["content_type"] = content_type

    content_lane = _required_text(card, "content_lane")
    if content_lane not in CONTENT_LANES:
        raise ValueError("栀夏内容通道无效")
    expected_type = LANE_CONTENT_TYPES[content_lane]
    if content_type != expected_type:
        raise ValueError(f"{content_lane} 内容类型应为 {expected_type}")
    normalized["content_lane"] = content_lane

    character_policy = _required_text(card, "character_image_policy")
    if character_policy not in CHARACTER_POLICIES:
        raise ValueError(
            "栀夏角色图片策略须为 default_one / optional_one / story_multiple"
        )
    if character_policy == "optional_one" and content_lane not in FILM_LANES:
        raise ValueError("optional_one 角色图片策略只适用于影视内容")
    normalized["character_image_policy"] = character_policy

    image_plan = card.get("image_plan")
    if not isinstance(image_plan, list) or not any(str(item).strip() for item in image_plan):
        raise ValueError("栀夏选题卡须包含非空 image_plan")
    risks = card.get("risks")
    if not isinstance(risks, list):
        raise ValueError("栀夏选题卡 risks 须为数组")

    scores = card.get("scores")
    if not isinstance(scores, Mapping):
        raise ValueError("栀夏选题卡 scores 须为对象")
    normalized_scores: dict[str, int] = {}
    for field in SCORE_FIELDS:
        try:
            value = int(scores[field])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"栀夏选题卡缺少有效评分: {field}") from exc
        if not 0 <= value <= 25:
            raise ValueError(f"栀夏选题卡评分超出 0-25: {field}")
        normalized_scores[field] = value
    score_total = sum(normalized_scores.values())
    if score_total < MIN_SCORE:
        raise ValueError(f"栀夏选题总分须至少 {MIN_SCORE}，当前 {score_total}")
    if normalized_scores["zhixia_observation"] < MIN_OBSERVATION_SCORE:
        raise ValueError(
            f"栀夏观察评分须至少 {MIN_OBSERVATION_SCORE}，"
            f"当前 {normalized_scores['zhixia_observation']}"
        )
    normalized["scores"] = normalized_scores
    normalized["score_total"] = score_total

    try:
        observed_at = datetime.fromisoformat(normalized["observed_at"])
    except ValueError as exc:
        raise ValueError("栀夏选题卡 observed_at 须为 ISO 8601 时间") from exc
    if observed_at.tzinfo is None:
        raise ValueError("栀夏选题卡 observed_at 须包含时区")
    current = now or datetime.now(TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=TZ)
    fact_sources = card.get("fact_sources")
    if content_lane in TIME_SENSITIVE_LANES:
        age_seconds = (current - observed_at).total_seconds()
        if age_seconds > HOTSPOT_MAX_AGE_SECONDS:
            raise ValueError("栀夏热点选题超过 6 小时，须重新核验")
    if content_lane in FILM_LANES | TIME_SENSITIVE_LANES:
        if not isinstance(fact_sources, list) or not any(
            isinstance(item, Mapping)
            and str(item.get("url") or "").startswith("https://")
            and str(item.get("title") or "").strip()
            for item in fact_sources
        ):
            raise ValueError("影视或热点选题须至少包含一个可追溯事实来源")
    elif not isinstance(fact_sources, list):
        raise ValueError("栀夏选题卡 fact_sources 须为数组")

    normalized["observed_at"] = observed_at.isoformat()
    normalized["visual_exception"] = str(card.get("visual_exception") or "").strip()
    if character_policy == "story_multiple" and not normalized["visual_exception"]:
        raise ValueError("多张栀夏角色图须填写 visual_exception")
    return normalized


def validate_opinion_copy(
    content: str,
    *,
    has_report_images: bool,
    ai_disclosure_mode: str = "body",
) -> str:
    normalized = content.strip()
    if ai_disclosure_mode not in {"body", "platform_publish"}:
        raise ValueError("栀夏 AI 声明模式须为 body / platform_publish")
    minimum, maximum = COPY_RANGE
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"观点型栀夏贴图正文须为 {minimum}-{maximum} 字")
    if ai_disclosure_mode == "body" and (
        "AI 虚拟角色" not in normalized or "AI 生成示意图" not in normalized
    ):
        raise ValueError("栀夏贴图正文须披露 AI 虚拟角色与 AI 生成示意图")
    if has_report_images and "报道图来源见文中" not in normalized:
        raise ValueError("混用报道图时正文须标注“报道图来源见文中”")
    return normalized


def _current_round_posts(
    posts: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    valid = [post for post in posts if str(post.get("status") or "") == "published"]
    return valid[(len(valid) // 10) * 10 :]


def content_mix_counts(posts: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {content_type: 0 for content_type in CONTENT_TYPES}
    for post in _current_round_posts(posts):
        content_type = str(post.get("content_type") or "")
        if content_type in counts:
            counts[content_type] += 1
    return counts


def content_lane_counts(posts: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {content_lane: 0 for content_lane in CONTENT_LANES}
    for post in _current_round_posts(posts):
        content_lane = str(post.get("content_lane") or "")
        if content_lane in counts:
            counts[content_lane] += 1
    return counts


def available_content_lanes(posts: Iterable[Mapping[str, Any]]) -> list[str]:
    counts = content_lane_counts(posts)
    return [
        content_lane
        for content_lane in CONTENT_LANES
        if counts[content_lane] < LANE_TARGETS[content_lane]
    ]


def next_content_type(posts: Iterable[Mapping[str, Any]]) -> str:
    counts = content_mix_counts(posts)
    for content_type in CONTENT_TYPES:
        if counts[content_type] < ROUND_TARGETS[content_type]:
            return content_type
    return "A"
