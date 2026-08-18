"""公众号「热点商业」：从每日热点中选择可验证的商业议题。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Any

from scripts.tools.deepseek_client import call_wechat_mp_llm
from scripts.tools.wechat_mp_codex_hot_business import distinct_source_domain_count
from scripts.tools.wechat_mp_hotspot_article import (
    HotspotTopic,
    attach_hotspot_research,
    pick_hotspot_candidates,
)

HOT_BUSINESS_MIN_SCORE = 70
HOT_BUSINESS_CANDIDATE_LIMIT = 5

_HARD_RISK_MARKERS = (
    "遇难",
    "死亡",
    "伤亡",
    "坠毁",
    "地震",
    "洪灾",
    "刑拘",
    "涉嫌犯罪",
    "强奸",
    "猥亵",
)
_GOSSIP_MARKERS = ("恋情", "分手", "离婚", "绯闻", "出轨", "前任")
_COMMERCIAL_ENTITY_MARKERS = (
    "公司",
    "集团",
    "平台",
    "品牌",
    "门店",
    "产品",
    "会员",
    "价格",
    "涨价",
    "降价",
    "收入",
    "融资",
    "上市",
)


@dataclass(frozen=True)
class HotBusinessAssessment:
    index: int
    heat: int
    business_space: int
    verifiability: int
    reader_relevance: int
    reason: str

    @property
    def total(self) -> int:
        return self.heat + self.business_space + self.verifiability + self.reader_relevance


@dataclass(frozen=True)
class SelectedHotBusinessTopic:
    topic: HotspotTopic
    assessment: HotBusinessAssessment | None
    research_urls: tuple[str, ...]


def _is_unsuitable(topic: HotspotTopic) -> bool:
    text = " ".join(
        str(topic.item.get(key) or "") for key in ("title", "summary", "description")
    )
    if any(marker in text for marker in _HARD_RISK_MARKERS):
        return True
    if any(marker in text for marker in _GOSSIP_MARKERS) and not any(
        marker in text for marker in _COMMERCIAL_ENTITY_MARKERS
    ):
        return True
    return False


def _research_urls(item: dict[str, Any]) -> tuple[str, ...]:
    urls: list[str] = []
    for row in item.get("web_research") or []:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        if url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
    return tuple(urls)


def _json_payload(raw: str) -> Any:
    text = (raw or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("热点商业评分未返回有效 JSON") from exc


def _clamp(value: Any, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    return max(0, min(parsed, maximum))


def _assessment_from_row(row: dict[str, Any]) -> HotBusinessAssessment:
    return HotBusinessAssessment(
        index=int(row.get("index", -1)),
        heat=_clamp(row.get("heat"), 40),
        business_space=_clamp(row.get("business_space"), 30),
        verifiability=_clamp(row.get("verifiability"), 20),
        reader_relevance=_clamp(row.get("reader_relevance"), 10),
        reason=str(row.get("reason") or "").strip(),
    )


def _request_assessments(rows: list[dict[str, Any]]) -> list[HotBusinessAssessment]:
    prompt_rows = []
    for index, row in enumerate(rows):
        research = row.get("web_research") or []
        sources = [
            {
                "title": str(hit.get("title") or "")[:100],
                "source": str(hit.get("source") or "")[:40],
                "url": str(hit.get("url") or ""),
            }
            for hit in research
            if isinstance(hit, dict)
        ]
        prompt_rows.append(
            {
                "index": index,
                "title": str(row.get("title") or ""),
                "summary": str(row.get("summary") or "")[:260],
                "attention_score": row.get("attention_score"),
                "sources": sources,
            }
        )
    prompt = f"""你是商业媒体主编。请为以下每日热点逐项评分：
- heat：热点强度，0-40
- business_space：能否解释收入、成本、竞争、渠道或商业模式，0-30
- verifiability：是否有足够公开证据支撑，0-20
- reader_relevance：是否影响普通人的钱、工作或消费，0-10

只输出 JSON 数组，每项字段必须是 index、heat、business_space、verifiability、reader_relevance、reason。
index 使用输入中的数字，不得新增候选。

输入：
{json.dumps(prompt_rows, ensure_ascii=False)}"""
    raw = call_wechat_mp_llm(
        [
            {"role": "system", "content": "只输出严格 JSON，不要 Markdown。"},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1200,
    )
    payload = _json_payload(raw)
    if isinstance(payload, dict):
        payload = payload.get("assessments")
    if not isinstance(payload, list):
        raise RuntimeError("热点商业评分 JSON 必须是数组")
    return [_assessment_from_row(row) for row in payload if isinstance(row, dict)]


def _researched_topic(topic: HotspotTopic) -> tuple[HotspotTopic, tuple[str, ...]]:
    item = attach_hotspot_research(topic.item)
    enriched = replace(topic, item=item)
    return enriched, _research_urls(item)


def _manual_topic(topic_hint: str) -> HotspotTopic:
    title = topic_hint.strip()
    return HotspotTopic(
        item={
            "title": title,
            "summary": f"指定热点商业选题：{title}",
            "href": f"trend://manual/{title}",
            "attention_score": 800.0,
            "sentiment": "neutral",
            "sources": ["指定选题"],
        },
        bucket="other",
        score=800.0,
        section_title=title[:16],
    )


def pick_hot_business_topic(
    items: list[dict[str, Any]] | None = None,
    *,
    topic_hint: str = "",
) -> SelectedHotBusinessTopic:
    """选择热点商业题；手动题跳过评分，但不跳过多来源研究门槛。"""
    if topic_hint.strip():
        topic, urls = _researched_topic(_manual_topic(topic_hint))
        if distinct_source_domain_count(urls) < 3:
            raise RuntimeError("热点商业选题至少需要 3 个不同来源域")
        return SelectedHotBusinessTopic(topic=topic, assessment=None, research_urls=urls)

    candidates = [
        topic for topic in pick_hotspot_candidates(items) if not _is_unsuitable(topic)
    ][:HOT_BUSINESS_CANDIDATE_LIMIT]
    researched: list[tuple[HotspotTopic, tuple[str, ...]]] = [
        _researched_topic(topic) for topic in candidates
    ]
    if not researched:
        raise RuntimeError("每日热点中没有适合热点商业分析的候选")

    assessments = _request_assessments([topic.item for topic, _ in researched])
    by_index: dict[int, HotBusinessAssessment] = {}
    for raw in assessments:
        if not 0 <= raw.index < len(researched):
            continue
        topic, urls = researched[raw.index]
        normalized = HotBusinessAssessment(
            index=raw.index,
            heat=_clamp(raw.heat, 40),
            business_space=_clamp(raw.business_space, 30),
            verifiability=(
                _clamp(raw.verifiability, 20)
                if distinct_source_domain_count(urls) >= 3
                else 0
            ),
            reader_relevance=_clamp(raw.reader_relevance, 10),
            reason=raw.reason,
        )
        by_index[raw.index] = normalized

    qualified = [assessment for assessment in by_index.values() if assessment.total >= HOT_BUSINESS_MIN_SCORE]
    if not qualified:
        raise RuntimeError("每日热点候选没有达到 70 分，热点商业本次不成稿")
    selected = max(qualified, key=lambda assessment: assessment.total)
    topic, urls = researched[selected.index]
    return SelectedHotBusinessTopic(topic=topic, assessment=selected, research_urls=urls)
