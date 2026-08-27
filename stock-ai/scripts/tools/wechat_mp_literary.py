"""Validated literary/classics long-form drafts and rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

LITERARY_SLOT_KEYS = frozenset(
    {
        "literary",
        "literary_next",
        "literary_queue",
        "literary_queue_2",
        "literary_queue_3",
    }
)


@dataclass(frozen=True)
class LiteraryDraft:
    title: str
    digest: str
    body: str
    topic: str
    research_urls: tuple[str, ...]
    original_thesis: str
    slot_key: str = "literary"
    topic_slug: str = ""


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"文学草稿字段 {key} 必须是非空字符串")
    return value.strip()


def _distinct_domains(urls: tuple[str, ...]) -> set[str]:
    return {
        (urlparse(url).hostname or "").lower()
        for url in urls
        if (urlparse(url).hostname or "").strip()
    }


def validate_literary_draft(draft: LiteraryDraft) -> LiteraryDraft:
    clean_chars = len("".join(draft.body.split()))
    if clean_chars < 1400 or clean_chars > 3200:
        raise ValueError(f"文学草稿正文需为 1400—3200 字，当前 {clean_chars}")
    if len(_distinct_domains(draft.research_urls)) < 3:
        raise ValueError("文学草稿至少需要 3 个不同来源域")
    if len(draft.original_thesis) < 20:
        raise ValueError("文学草稿 original_thesis 不得少于 20 字")
    if draft.slot_key not in LITERARY_SLOT_KEYS:
        raise ValueError(
            "文学草稿 slot_key 必须为 literary、literary_next、literary_queue、literary_queue_2 或 literary_queue_3"
        )
    return draft


def load_literary_draft_data(data: dict[str, Any]) -> LiteraryDraft:
    if not isinstance(data, dict):
        raise ValueError("文学草稿顶层必须是 JSON 对象")
    raw_urls = data.get("research_urls")
    if not isinstance(raw_urls, list) or any(
        not isinstance(url, str) or not url.strip() for url in raw_urls
    ):
        raise ValueError("文学草稿 research_urls 必须是非空字符串数组")
    draft = LiteraryDraft(
        title=_required_text(data, "title")[:32],
        digest=_required_text(data, "digest"),
        body=_required_text(data, "body"),
        topic=_required_text(data, "topic"),
        research_urls=tuple(url.strip() for url in raw_urls),
        original_thesis=_required_text(data, "original_thesis"),
        slot_key=str(data.get("slot_key") or "literary").strip(),
        topic_slug=str(data.get("topic_slug") or "").strip(),
    )
    return validate_literary_draft(draft)


def load_literary_draft(path: Path) -> LiteraryDraft:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"文学草稿 JSON 无效: {exc.msg}") from exc
    return load_literary_draft_data(data)


def build_literary_article(
    draft: LiteraryDraft, *, upload_figures: bool = True
) -> dict[str, Any]:
    from scripts.tools.wechat_mp_content import _article_shell
    from scripts.tools.wechat_mp_seo import attach_publish_hints

    validate_literary_draft(draft)
    article = attach_publish_hints(
        _article_shell(
            title=draft.title,
            digest=draft.digest,
            body_text=draft.body,
            kind="literary",
            upload_figures=upload_figures,
        ),
        "literary",
        theme=draft.topic,
    )
    article["slot_key"] = draft.slot_key
    article["research_urls"] = list(draft.research_urls)
    article["original_thesis"] = draft.original_thesis
    article["topic_slug"] = draft.topic_slug
    return article
