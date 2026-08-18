"""公众号银发方向的研究、结构化写稿与文章构建。"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from scripts.tools.deepseek_client import call_wechat_mp_llm
from scripts.tools.wechat_mp_codex_silver import (
    CodexSilverDraft,
    distinct_source_domain_count,
    load_codex_silver_draft_data,
    validate_silver_draft,
)
from scripts.tools.wechat_mp_content import _article_shell
from scripts.tools.wechat_mp_codex_images import prepare_hotspot_topic_images
from scripts.tools.wechat_mp_discussion_figures import (
    discussion_body_figure_target,
    ensure_discussion_cover,
    inject_discussion_figures,
)
from scripts.tools.wechat_mp_seo import attach_publish_hints, format_publish_reminder
from scripts.tools.wechat_mp_silver_topics import SilverTopic, pick_silver_topic
from scripts.tools.wechat_mp_role_card import account_role_prompt_block

_LANE_MARKERS = {
    "relation": ("夫妻", "伴侣", "子女", "家庭", "朋友", "独处", "带孙", "相处"),
    "health": ("健康", "睡眠", "饮食", "运动", "体检", "跌倒", "血压", "习惯"),
    "money": ("养老金", "消费", "防骗", "诈骗", "理财", "借钱", "旅游", "直播购物", "钱"),
}
_SAFETY_RULES = {
    "relation": "不得制造年龄焦虑、代际对立或用个体故事概括所有退休家庭。",
    "health": "不得诊断、解读个人检查结果或推荐药物、保健品和治疗方案。",
    "money": "不得推荐金融产品、预测收益或提供个性化投资建议。",
}
_LAST_SELECTED_TOPIC: SilverTopic | None = None
_LAST_BUILT_SILVER_TOPIC: dict[str, object] | None = None
_HASHTAGS_BY_LANE = {
    "relation": ["退休生活", "家庭关系", "夫妻相处"],
    "health": ["退休生活", "健康生活", "生活习惯"],
    "money": ["退休生活", "养老防骗", "理性消费"],
}


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("银发写稿模型未返回有效 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("银发写稿模型必须返回单个 JSON 对象")
    return payload


def infer_silver_lane(topic_hint: str) -> str:
    text = (topic_hint or "").strip()
    scores = {
        lane: sum(1 for marker in markers if marker in text)
        for lane, markers in _LANE_MARKERS.items()
    }
    best = max(scores.values(), default=0)
    winners = [lane for lane, score in scores.items() if score == best and score > 0]
    if len(winners) != 1:
        raise ValueError("手动银发选题无法唯一判断方向，请同时指定 --silver-lane")
    return winners[0]


def resolve_silver_topic(*, lane: str | None = None, topic_hint: str = "") -> SilverTopic:
    hint = (topic_hint or "").strip()
    if not hint:
        return pick_silver_topic(lane=lane)
    resolved_lane = lane or infer_silver_lane(hint)
    return SilverTopic(
        topic_id="manual",
        lane=resolved_lane,
        title=hint,
        reader_problem=f"围绕“{hint}”，读者最需要解决的具体生活问题是什么？",
        search_terms=(hint,),
        scene_prompt="从一个可感知、不过度戏剧化的真实生活场景开篇",
        risk_notes=("手动选题仍须遵守来源和安全边界",),
    )


def research_silver_topic(topic: SilverTopic) -> list[dict[str, str]]:
    from scripts.tools.wechat_mp_discussion_research import fetch_discussion_research

    topic_dict = {
        "trend_title": topic.title,
        "title_zh": topic.title,
        "cover_slug": topic.topic_id,
        "from_trend": False,
        "research_urls": [],
        "search_terms": list(topic.search_terms),
    }
    hits = fetch_discussion_research(topic_dict)
    return [
        {
            "title": hit.title,
            "snippet": hit.snippet,
            "source": hit.source,
            "url": hit.url,
            "published": hit.published,
        }
        for hit in hits
        if str(hit.url).startswith(("http://", "https://"))
    ]


def generate_silver_draft(
    *, lane: str | None = None, topic_hint: str = ""
) -> CodexSilverDraft:
    global _LAST_SELECTED_TOPIC
    topic = resolve_silver_topic(lane=lane, topic_hint=topic_hint)
    _LAST_SELECTED_TOPIC = topic
    sources = research_silver_topic(topic)
    allowed_urls = list(dict.fromkeys(row["url"] for row in sources if row.get("url")))
    schema = {
        "title": "32字内自然标题，不加栏目名前缀",
        "digest": "面向读者问题的简短摘要",
        "body": "1600至2600个非空白字符，含3至5个以>开头的小标题",
        "topic": topic.title,
        "lane": topic.lane,
        "research_urls": allowed_urls,
        "original_thesis": "不少于20字的原创核心判断",
        "reader_problem": topic.reader_problem,
        "facts": [{"claim": "可核验事实", "source_url": "必须来自 research_urls"}],
        "practical_steps": ["普通读者可执行的小步骤"],
        "cautions": ["适用边界或需要专业帮助的情形"],
        "rejected_claims": ["研究中无法核验且未写入公开稿的说法"],
        "slot_key": "silver",
    }
    prompt = f"""{account_role_prompt_block()}

## 稿型任务：银发生活
你为公众号“栀夏未完成”撰写一篇面向 50—65 岁、临近或刚退休读者的文章。

方向：{topic.lane}
选题：{topic.title}
读者问题：{topic.reader_problem}
开篇场景：{topic.scene_prompt}
风险提示：{json.dumps(topic.risk_notes, ensure_ascii=False)}
允许引用的 URL：{json.dumps(allowed_urls, ensure_ascii=False)}
完整研究材料：{json.dumps(sources, ensure_ascii=False)}

写作要求：直接、平等地和读者说话，不使用“老人家”等居高临下称呼，不制造衰老焦虑。
正文用短段落，设置 3 至 5 个自然小标题，小标题单独一行并以“> ”开头；先写具体生活场景，
再解释原因，最后给出可以从今天开始的小步骤和一个自然互动问题。不要出现栏目名、写作提示、
选题评分、编审元数据、emoji 或 Markdown 的 # 标题。每条 facts 必须绑定允许 URL，无法核验的
说法放入 rejected_claims 且不得出现在标题、摘要和正文。正文去空白后须为 1600 至 2600 字。
安全硬规则：{_SAFETY_RULES[topic.lane]}

只输出一个严格 JSON 对象，字段和值遵循此结构：
{json.dumps(schema, ensure_ascii=False)}"""
    raw = call_wechat_mp_llm(
        [
            {"role": "system", "content": "你是严谨、平等、克制的中文生活媒体主笔，只输出严格 JSON。"},
            {"role": "user", "content": prompt},
        ],
        max_tokens=7000,
    )
    return load_codex_silver_draft_data(_parse_json_object(raw))


def get_last_built_silver_topic() -> dict[str, object] | None:
    return _LAST_BUILT_SILVER_TOPIC


def _prepare_silver_body_with_figures(draft: CodexSilverDraft) -> str:
    global _LAST_BUILT_SILVER_TOPIC
    _LAST_BUILT_SILVER_TOPIC = None
    topic_dict = draft.as_discussion_topic()
    target = discussion_body_figure_target()
    prepare_hotspot_topic_images(topic_dict, body_count=target)
    body = inject_discussion_figures(
        draft.body,
        topic_dict,
        preserve_headings=True,
    )
    if body.count("[[fig:") < target:
        raise RuntimeError(f"银发正文配图不足 {target} 张可用公开报道图")
    ensure_discussion_cover(topic_dict)
    _LAST_BUILT_SILVER_TOPIC = topic_dict
    return body


def _authority_source_count(draft: CodexSilverDraft) -> int:
    if draft.lane == "relation":
        return 0
    suffixes = (
        ("nhc.gov.cn", "chinacdc.cn")
        if draft.lane == "health"
        else ("gov.cn", "mohrss.gov.cn", "mps.gov.cn", "nfra.gov.cn", "samr.gov.cn", "court.gov.cn")
    )
    count = 0
    for url in draft.research_urls:
        domain = (urlparse(url).hostname or "").lower()
        if any(domain == suffix or domain.endswith(f".{suffix}") for suffix in suffixes):
            count += 1
    return count


def build_silver_article(
    *,
    lane: str | None = None,
    topic_hint: str = "",
    codex_draft: CodexSilverDraft | None = None,
    upload_figures: bool = True,
) -> dict[str, Any]:
    global _LAST_SELECTED_TOPIC
    if codex_draft is not None:
        _LAST_SELECTED_TOPIC = None
    draft = codex_draft or generate_silver_draft(lane=lane, topic_hint=topic_hint)
    validate_silver_draft(draft)
    if lane is not None and draft.lane != lane:
        raise ValueError(f"银发草稿 lane={draft.lane} 与请求 lane={lane} 不一致")
    body_text = _prepare_silver_body_with_figures(draft)
    article = _article_shell(
        title=draft.title,
        digest=draft.digest,
        body_text=body_text,
        upload_figures=upload_figures,
        kind="silver",
        engagement_kind="discussion",
        masthead_kind="silver",
    )
    article["slot_key"] = "silver"
    article["silver_lane"] = draft.lane
    topic_id = _LAST_SELECTED_TOPIC.topic_id if _LAST_SELECTED_TOPIC else "manual"
    article["silver_topic_id"] = topic_id
    article["silver_report"] = {
        "lane": draft.lane,
        "topic": draft.topic,
        "topic_id": topic_id,
        "source_domains": distinct_source_domain_count(draft.research_urls),
        "fact_count": len(draft.facts),
        "authority_source_count": _authority_source_count(draft),
    }
    if not upload_figures:
        article["recommended_hashtags"] = list(_HASHTAGS_BY_LANE[draft.lane])
        article["publish_reminder"] = format_publish_reminder(kind="silver")
        return article
    return attach_publish_hints(
        article,
        "silver",
        hashtag_override=_HASHTAGS_BY_LANE[draft.lane],
        engagement_kind="discussion",
    )
