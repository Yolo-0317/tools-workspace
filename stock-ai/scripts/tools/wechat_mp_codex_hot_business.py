"""读取并校验 Codex 准备的公众号热点商业长图文 JSON。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from scripts.tools.wechat_mp_codex_hotspot import CodexHotspotDraft
from scripts.tools.wechat_mp_originality import (
    OriginalityReport,
    evaluate_hotspot_longform,
    require_originality,
)

HOT_BUSINESS_SLOT_KEY = "hot_business"


@dataclass(frozen=True)
class HotBusinessFact:
    claim: str
    source_url: str


@dataclass(frozen=True)
class CodexHotBusinessDraft:
    title: str
    digest: str
    body: str
    topic: str
    research_urls: tuple[str, ...]
    original_thesis: str
    business_question: str
    facts: tuple[HotBusinessFact, ...]
    inferences: tuple[str, ...]
    rejected_claims: tuple[str, ...]
    slot_key: str = HOT_BUSINESS_SLOT_KEY

    def as_hotspot_draft(self) -> CodexHotspotDraft:
        return CodexHotspotDraft(
            title=self.title,
            digest=self.digest,
            body=self.body,
            topic=self.topic,
            research_urls=self.research_urls,
            slot_key=HOT_BUSINESS_SLOT_KEY,
            original_thesis=self.original_thesis,
        )


def _required_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"热点商业草稿字段 {field} 必须是非空字符串")
    return value.strip()


def _required_text_list(data: dict[str, Any], field: str) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"热点商业草稿字段 {field} 必须是字符串数组")
    return tuple(item.strip() for item in value)


def _source_domain(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = (parsed.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def distinct_source_domain_count(urls: Iterable[str]) -> int:
    return len({domain for url in urls if (domain := _source_domain(str(url).strip()))})


def _normalized_claim(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def validate_hot_business_draft(draft: CodexHotBusinessDraft) -> CodexHotBusinessDraft:
    if draft.slot_key != HOT_BUSINESS_SLOT_KEY:
        raise ValueError("热点商业草稿 slot_key 必须是 hot_business")
    if distinct_source_domain_count(draft.research_urls) < 3:
        raise ValueError("热点商业草稿至少需要 3 个不同来源域")
    if len(draft.original_thesis.strip()) < 20:
        raise ValueError("热点商业草稿 original_thesis 不少于 20 字")
    body_chars = len(re.sub(r"\s+", "", draft.body))
    if body_chars < 1920:
        raise ValueError(f"热点商业草稿正文去空白后不少于 1920 字（当前 {body_chars}）")
    if not draft.facts:
        raise ValueError("热点商业草稿 facts 至少需要 1 条事实")
    allowed_urls = set(draft.research_urls)
    for fact in draft.facts:
        if not fact.claim.strip() or fact.source_url not in allowed_urls:
            raise ValueError("热点商业草稿 facts 的 source_url 必须位于 research_urls")
    public_blob = _normalized_claim("\n".join((draft.title, draft.digest, draft.body)))
    for claim in draft.rejected_claims:
        normalized = _normalized_claim(claim)
        if normalized and normalized in public_blob:
            raise ValueError("热点商业草稿 rejected_claims 不得写回标题、摘要或正文")
    return draft


def load_codex_hot_business_draft_data(data: Any) -> CodexHotBusinessDraft:
    if not isinstance(data, dict):
        raise ValueError("热点商业草稿顶层必须是 JSON 对象")
    research_urls = _required_text_list(data, "research_urls")
    facts_raw = data.get("facts")
    if not isinstance(facts_raw, list):
        raise ValueError("热点商业草稿字段 facts 必须是对象数组")
    facts: list[HotBusinessFact] = []
    for row in facts_raw:
        if not isinstance(row, dict):
            raise ValueError("热点商业草稿字段 facts 必须是对象数组")
        facts.append(
            HotBusinessFact(
                claim=_required_text(row, "claim"),
                source_url=_required_text(row, "source_url"),
            )
        )
    raw_slot = data.get("slot_key", HOT_BUSINESS_SLOT_KEY)
    if not isinstance(raw_slot, str):
        raise ValueError("热点商业草稿字段 slot_key 必须是字符串")
    draft = CodexHotBusinessDraft(
        title=_required_text(data, "title"),
        digest=_required_text(data, "digest"),
        body=_required_text(data, "body"),
        topic=_required_text(data, "topic"),
        research_urls=research_urls,
        original_thesis=_required_text(data, "original_thesis"),
        business_question=_required_text(data, "business_question"),
        facts=tuple(facts),
        inferences=_required_text_list(data, "inferences"),
        rejected_claims=_required_text_list(data, "rejected_claims"),
        slot_key=raw_slot.strip(),
    )
    return validate_hot_business_draft(draft)


def load_codex_hot_business_draft(path: Path) -> CodexHotBusinessDraft:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"热点商业草稿 JSON 无效: {source}: {exc.msg}") from exc
    return load_codex_hot_business_draft_data(data)


def validate_codex_hot_business_originality(
    draft: CodexHotBusinessDraft,
    *,
    history_posts: list[dict[str, Any]],
) -> OriginalityReport:
    validate_hot_business_draft(draft)
    return require_originality(
        evaluate_hotspot_longform(
            title=draft.title,
            body=draft.body,
            research_urls=draft.research_urls,
            thesis=draft.original_thesis,
            history_posts=history_posts,
        )
    )
