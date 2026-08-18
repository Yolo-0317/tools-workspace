"""Codex 单剧推广稿的结构化交接格式。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.tools.wechat_mp_short_drama_research import DramaFact, DramaSource


@dataclass(frozen=True)
class FeatureParagraph:
    text: str
    fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class CodexShortDramaDraft:
    drama_id: str
    drama_name: str
    title: str
    digest: str
    title_fact_ids: tuple[str, ...]
    digest_fact_ids: tuple[str, ...]
    paragraphs: tuple[FeatureParagraph, ...]
    sources: tuple[DramaSource, ...]
    facts: tuple[DramaFact, ...]
    rejected_claims: tuple[str, ...]
    slot_key: str


def _required_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Codex 单剧稿字段 {field} 必须是非空字符串")
    return value.strip()


def _text_tuple(data: dict[str, Any], field: str) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"Codex 单剧稿字段 {field} 必须是非空字符串数组")
    return tuple(item.strip() for item in value)


def load_codex_short_drama_draft_data(data: dict[str, Any]) -> CodexShortDramaDraft:
    if not isinstance(data, dict):
        raise ValueError("Codex 单剧稿必须是 JSON 对象")
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("Codex 单剧稿 sources 必须是对象数组")
    sources: list[DramaSource] = []
    for row in raw_sources:
        if not isinstance(row, dict):
            raise ValueError("Codex 单剧稿 sources 必须是对象数组")
        source_id = _required_text(row, "source_id")
        if source_id == "platform":
            raise ValueError("platform 来源由系统注入，Codex 稿件不得提供")
        official = row.get("official", False)
        if not isinstance(official, bool):
            raise ValueError("Codex 单剧稿来源 official 必须是布尔值")
        sources.append(
            DramaSource(
                source_id=source_id,
                url=_required_text(row, "url"),
                title=_required_text(row, "title"),
                source_name=_required_text(row, "source_name"),
                source_type=_required_text(row, "source_type"),
                official=official,
                excerpt=_required_text(row, "excerpt"),
            )
        )

    raw_facts = data.get("facts")
    if not isinstance(raw_facts, list):
        raise ValueError("Codex 单剧稿 facts 必须是对象数组")
    facts: list[DramaFact] = []
    for row in raw_facts:
        if not isinstance(row, dict):
            raise ValueError("Codex 单剧稿 facts 必须是对象数组")
        facts.append(
            DramaFact(
                fact_id=_required_text(row, "fact_id"),
                fact_type=_required_text(row, "fact_type"),
                claim=_required_text(row, "claim"),
                source_ids=_text_tuple(row, "source_ids"),
            )
        )

    raw_paragraphs = data.get("paragraphs")
    if not isinstance(raw_paragraphs, list):
        raise ValueError("Codex 单剧稿 paragraphs 必须是对象数组")
    paragraphs: list[FeatureParagraph] = []
    for row in raw_paragraphs:
        if not isinstance(row, dict):
            raise ValueError("Codex 单剧稿 paragraphs 必须是对象数组")
        paragraphs.append(
            FeatureParagraph(
                text=_required_text(row, "text"),
                fact_ids=_text_tuple(row, "fact_ids"),
            )
        )

    rejected = data.get("rejected_claims")
    if not isinstance(rejected, list) or any(not isinstance(item, str) for item in rejected):
        raise ValueError("Codex 单剧稿 rejected_claims 必须是字符串数组")
    slot_key = _required_text(data, "slot_key")
    if slot_key != "short_drama_feature":
        raise ValueError("Codex 单剧稿 slot_key 必须为 short_drama_feature")
    return CodexShortDramaDraft(
        drama_id=_required_text(data, "drama_id"),
        drama_name=_required_text(data, "drama_name"),
        title=_required_text(data, "title"),
        digest=_required_text(data, "digest"),
        title_fact_ids=_text_tuple(data, "title_fact_ids"),
        digest_fact_ids=_text_tuple(data, "digest_fact_ids"),
        paragraphs=tuple(paragraphs),
        sources=tuple(sources),
        facts=tuple(facts),
        rejected_claims=tuple(item.strip() for item in rejected if item.strip()),
        slot_key=slot_key,
    )


def load_codex_short_drama_draft(path: Path) -> CodexShortDramaDraft:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Codex 单剧稿不是有效 JSON") from exc
    return load_codex_short_drama_draft_data(data)
