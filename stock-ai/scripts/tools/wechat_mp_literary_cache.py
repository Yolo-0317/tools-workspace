"""Independent cache for literary and classics articles."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_client import ROOT
from scripts.tools.wechat_mp_literary import LiteraryDraft

CACHE_DIR = ROOT / "data" / "wechat_mp_literary_body_cache"
TZ = ZoneInfo("Asia/Shanghai")


def _slug(value: str) -> str:
    clean = re.sub(r"[^\w\-]+", "_", (value or "literary").strip()).strip("_").lower()
    return clean or "literary"


def save_literary_body_cache(draft: LiteraryDraft) -> Path:
    topic_slug = _slug(draft.topic_slug or draft.topic)
    payload = asdict(draft)
    payload["research_urls"] = list(draft.research_urls)
    payload["body_core"] = payload.pop("body")
    payload["topic_slug"] = topic_slug
    payload["saved_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    path = CACHE_DIR / f"{topic_slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_literary_body_cache(topic_slug: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{_slug(topic_slug)}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not str(data.get("body_core") or "").strip():
        return None
    return data
