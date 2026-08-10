#!/usr/bin/env python3
"""热点深评正文缓存：换图/改标题重推时不重跑 Composer。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "wechat_mp_hotspot_body_cache"
LEGACY_CACHE_PATH = ROOT / "data" / "wechat_mp_hotspot_manual_cache.json"
TZ = ZoneInfo("Asia/Shanghai")


def _topic_key(topic: dict[str, Any]) -> str:
    slug = str(topic.get("cover_slug") or "").strip()
    if slug:
        return slug
    zh = str(topic.get("title_zh") or topic.get("trend_title") or "").strip()
    return zh or "hotspot"


def _cache_slug(topic_key: str) -> str:
    safe = re.sub(r"[^\w\-]+", "_", (topic_key or "hotspot").strip()).strip("_").lower()
    return safe or "hotspot"


def _cache_path(topic_key: str) -> Path:
    return CACHE_DIR / f"{_cache_slug(topic_key)}.json"


def save_hotspot_body_cache(
    topic: dict[str, Any],
    *,
    body_core: str,
    title: str,
    digest: str,
    slot_key: str = "",
) -> None:
    """body_core = finalize 后、inject 配图前的正文。"""
    key = _topic_key(topic)
    payload: dict[str, Any] = {
        "topic_key": key,
        "cover_slug": str(topic.get("cover_slug") or key).strip(),
        "title_zh": str(topic.get("title_zh") or "").strip(),
        "trend_title": str(topic.get("trend_title") or "").strip(),
        "title": title,
        "digest": digest,
        "body_core": body_core,
        "saved_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    if slot_key:
        payload["slot_key"] = slot_key.strip()
    research_urls = topic.get("research_urls")
    if isinstance(research_urls, str) and research_urls.strip():
        payload["research_urls"] = [research_urls.strip()]
    elif isinstance(research_urls, list):
        payload["research_urls"] = [str(u).strip() for u in research_urls if str(u).strip()]
    path = _cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LEGACY_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_cache_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not str(data.get("body_core") or "").strip():
        return None
    return data


def _match_cache(data: dict[str, Any], *, topic_key: str) -> bool:
    key = (topic_key or "").strip().lower()
    if not key:
        return False
    for field in ("topic_key", "cover_slug", "title_zh", "trend_title", "title"):
        val = str(data.get(field) or "").strip().lower()
        if val and (val == key or key in val or val in key):
            return True
    return False


def load_hotspot_body_cache(
    *,
    topic_key: str | None = None,
    slot_key: str | None = None,
) -> dict[str, Any] | None:
    if topic_key:
        data = _load_cache_file(_cache_path(topic_key))
        if data and _match_cache(data, topic_key=topic_key):
            return data
        if LEGACY_CACHE_PATH.is_file():
            data = _load_cache_file(LEGACY_CACHE_PATH)
            if data and _match_cache(data, topic_key=topic_key):
                return data
        if CACHE_DIR.is_dir():
            for path in sorted(CACHE_DIR.glob("*.json"), reverse=True):
                data = _load_cache_file(path)
                if data and _match_cache(data, topic_key=topic_key):
                    return data
        return None

    if slot_key and CACHE_DIR.is_dir():
        for path in sorted(CACHE_DIR.glob("*.json"), reverse=True):
            data = _load_cache_file(path)
            if data and str(data.get("slot_key") or "").strip() == slot_key.strip():
                return data

    return _load_cache_file(LEGACY_CACHE_PATH)


def topic_from_cache(cache: dict[str, Any]) -> dict[str, Any]:
    slug = str(cache.get("cover_slug") or cache.get("topic_key") or "").strip()
    return {
        "title_zh": str(cache.get("title_zh") or cache.get("title") or "").strip(),
        "trend_title": str(cache.get("trend_title") or cache.get("title") or "").strip(),
        "cover_slug": slug,
        "from_trend": True,
        "research_urls": cache.get("research_urls") or [],
    }
