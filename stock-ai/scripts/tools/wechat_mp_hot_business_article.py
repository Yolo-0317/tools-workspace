"""公众号「热点商业」结构化写稿与长图文构建。"""

from __future__ import annotations

import json
import re
from typing import Any

from scripts.tools.deepseek_client import call_wechat_mp_llm
from scripts.tools.wechat_mp_codex_hot_business import (
    CodexHotBusinessDraft,
    distinct_source_domain_count,
    load_codex_hot_business_draft_data,
    validate_hot_business_draft,
)
from scripts.tools.wechat_mp_content import build_hotspot_article
from scripts.tools.wechat_mp_hot_business import pick_hot_business_topic
from scripts.tools.wechat_mp_role_card import account_role_prompt_block

_LAST_SELECTION_REPORT: dict[str, Any] | None = None


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("热点商业写稿模型未返回有效 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("热点商业写稿模型必须返回单个 JSON 对象")
    return payload


def _research_material(item: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for hit in item.get("web_research") or []:
        if not isinstance(hit, dict):
            continue
        rows.append(
            {
                "title": str(hit.get("title") or ""),
                "snippet": str(hit.get("snippet") or ""),
                "source": str(hit.get("source") or ""),
                "url": str(hit.get("url") or ""),
                "published": str(hit.get("published") or ""),
            }
        )
    return rows


def generate_hot_business_draft(*, topic_hint: str = "") -> CodexHotBusinessDraft:
    """选择每日热点、完成研究，并要求模型产出可机器校验的商业深稿。"""
    global _LAST_SELECTION_REPORT
    selected = pick_hot_business_topic(topic_hint=topic_hint)
    _LAST_SELECTION_REPORT = {
        "candidate_score": (
            selected.assessment.total if selected.assessment is not None else None
        ),
        "candidate_reason": (
            selected.assessment.reason if selected.assessment is not None else "手动指定"
        ),
    }
    item = selected.topic.item
    title = str(item.get("title") or selected.topic.section_title).strip()
    score_reason = selected.assessment.reason if selected.assessment else "用户手动指定"
    sources = _research_material(item)
    allowed_urls = list(selected.research_urls)
    schema = {
        "title": "32字内公众号标题",
        "digest": "摘要",
        "body": "不少于1920个非空白字符的完整正文",
        "topic": title,
        "research_urls": allowed_urls,
        "original_thesis": "不少于20字的原创核心判断",
        "business_question": "本文回答的单一商业问题",
        "facts": [{"claim": "可验证事实", "source_url": "必须来自 research_urls"}],
        "inferences": ["基于事实推导、明确使用可能/意味着等边界词"],
        "rejected_claims": ["研究中无法核验且没有写入公开稿的说法"],
        "slot_key": "hot_business",
    }
    prompt = f"""{account_role_prompt_block()}

## 稿型任务：热点商业
你为公众号“栀夏未完成”撰写一篇热点商业深稿。

热点：{title}
选题理由：{score_reason}
允许引用的 URL：{json.dumps(allowed_urls, ensure_ascii=False)}
研究材料：{json.dumps(sources, ensure_ascii=False)}

文章必须围绕一个清晰商业问题，依次完成七部分，但不要显示编号、Markdown 标题或编审元数据：
1. 热点到底发生了什么；2. 谁在赚钱、谁在付钱；3. 收入与成本如何流动；
4. 渠道、竞争和供需如何变化；5. 这件事为什么现在发生；
6. 对普通人的消费、工作或经营意味着什么；7. 哪些指标可以继续验证。

完读约束：首段前 80 字交代事件、变化和读者利益点；前 300 字完成事实、悬念和核心商业问题；
每 300 至 500 字至少加入一个新的信息增量或节奏钩子；全文至少两个可转述的数字、反差或判断；
段落多数控制在 1 至 3 行；文末只留一个具体互动问题。

先在内部区分事实、推断和拒绝采用的说法，再写公开正文。每条 facts 必须绑定一个允许 URL；
inferences 必须保留推断边界；rejected_claims 中的内容不得出现在标题、摘要或正文。
禁止编造排名、销量、稳定收益、公司内部动机；禁止投资建议、emoji、Markdown 标题、
“资料显示但无来源”以及可见的选题评分或写作提示。正文不少于 1920 个去空白字符。
前 80 字交代具体主体、事件和核心商业问题；前 300 字给出至少一条可核验事实并说明读者为何值得继续看。
每 300 至 500 字推进一个新问题或新证据，全文至少两个可转述、能被读者记住的具体判断。

只输出一个严格 JSON 对象，字段和值遵循此结构：
{json.dumps(schema, ensure_ascii=False)}"""
    raw = call_wechat_mp_llm(
        [
            {
                "role": "system",
                "content": "你是严谨的中文商业媒体主笔，只输出严格 JSON。",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=7000,
    )
    return load_codex_hot_business_draft_data(_parse_json_object(raw))


def build_hot_business_article(
    *,
    topic_hint: str = "",
    codex_draft: CodexHotBusinessDraft | None = None,
    upload_figures: bool = True,
) -> dict[str, Any]:
    global _LAST_SELECTION_REPORT
    if codex_draft is not None:
        _LAST_SELECTION_REPORT = None
    draft = codex_draft or generate_hot_business_draft(topic_hint=topic_hint)
    validate_hot_business_draft(draft)
    article = build_hotspot_article(
        codex_draft=draft.as_hotspot_draft(),
        article_kind="hot_business",
        upload_figures=upload_figures,
    )
    article["slot_key"] = "hot_business"
    article["hot_business_report"] = {
        "business_question": draft.business_question,
        "source_domains": distinct_source_domain_count(draft.research_urls),
        "fact_count": len(draft.facts),
        "inference_count": len(draft.inferences),
    }
    if _LAST_SELECTION_REPORT:
        article["hot_business_report"].update(_LAST_SELECTION_REPORT)
    return article
