"""读取 Codex 准备好的公众号热点长图文 JSON。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexHotspotDraft:
    """Codex 与公众号长图文发布链路之间的稳定交接对象。"""

    title: str
    digest: str
    body: str
    topic: str
    research_urls: tuple[str, ...] = ()
    slot_key: str = ""

    def as_discussion_topic(self) -> dict[str, object]:
        slug = re.sub(r"[^\w\-]+", "-", self.topic[:28]).strip("-").lower()
        return {
            "title_zh": self.topic,
            "trend_title": self.topic,
            "cover_slug": slug or "hotspot",
            "from_trend": True,
            "research_urls": list(self.research_urls),
        }


def _required_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Codex 热点草稿字段 {field} 必须是非空字符串")
    return value.strip()


def load_codex_hotspot_draft(path: Path) -> CodexHotspotDraft:
    """读取并校验 UTF-8 JSON，不执行任何联网或发布动作。"""

    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Codex 热点草稿 JSON 无效: {source}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("Codex 热点草稿顶层必须是 JSON 对象")

    raw_urls = data.get("research_urls", [])
    if not isinstance(raw_urls, list) or any(
        not isinstance(url, str) or not url.strip() for url in raw_urls
    ):
        raise ValueError("Codex 热点草稿字段 research_urls 必须是非空字符串数组")

    raw_slot = data.get("slot_key", "")
    if not isinstance(raw_slot, str):
        raise ValueError("Codex 热点草稿字段 slot_key 必须是字符串")

    return CodexHotspotDraft(
        title=_required_text(data, "title"),
        digest=_required_text(data, "digest"),
        body=_required_text(data, "body"),
        topic=_required_text(data, "topic"),
        research_urls=tuple(url.strip() for url in raw_urls),
        slot_key=raw_slot.strip(),
    )
