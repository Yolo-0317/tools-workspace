#!/usr/bin/env python3
"""影视稿正文缓存：按 topic 分文件，避免新片 DeepSeek 覆盖已改定稿。"""

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
CACHE_DIR = ROOT / "data" / "wechat_mp_tv_body_cache"
LEGACY_CACHE_PATH = ROOT / "data" / "wechat_mp_tv_body_cache.json"
TZ = ZoneInfo("Asia/Shanghai")


def _topic_key(topic: dict[str, Any]) -> str:
    en = str(topic.get("title_en") or "").strip()
    return en or str(topic.get("cover_slug") or "tv")


def _cache_slug(topic_key: str) -> str:
    safe = re.sub(r"[^\w\-]+", "_", (topic_key or "tv").strip()).strip("_").lower()
    return safe or "tv"


def _cache_path(topic_key: str) -> Path:
    return CACHE_DIR / f"{_cache_slug(topic_key)}.json"


def save_tv_body_cache(
    topic: dict[str, Any],
    *,
    body_core: str,
    title: str,
    digest: str,
    title_override: str = "",
) -> None:
    """body_core = generate 后 + normalize，尚未 inject 评分/剧照。"""
    key = _topic_key(topic)
    payload: dict[str, Any] = {
        "topic_key": key,
        "title_en": str(topic.get("title_en") or ""),
        "title_override": title_override or str(topic.get("title_override") or ""),
        "title": title,
        "digest": digest,
        "body_core": body_core,
        "saved_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    if str(topic.get("content_mode") or "").strip().lower() == "discussion":
        payload["content_mode"] = "discussion"
        payload["cover_slug"] = str(topic.get("cover_slug") or key).strip()
        payload["title_zh"] = str(topic.get("title_zh") or "").strip()
        payload["trend_title"] = str(topic.get("trend_title") or "").strip()
        research_urls = topic.get("research_urls")
        if isinstance(research_urls, str) and research_urls.strip():
            payload["research_urls"] = [research_urls.strip()]
        elif isinstance(research_urls, list):
            payload["research_urls"] = [str(u).strip() for u in research_urls if str(u).strip()]
    path = _cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # 兼容旧工具：同步写 legacy 单文件（最新一篇）
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


def load_tv_body_cache(*, topic_key: str | None = None) -> dict[str, Any] | None:
    if topic_key:
        data = _load_cache_file(_cache_path(topic_key))
        if data and str(data.get("topic_key") or "") == topic_key:
            return data
        if LEGACY_CACHE_PATH.is_file():
            data = _load_cache_file(LEGACY_CACHE_PATH)
            if data and str(data.get("topic_key") or "") == topic_key:
                return data
        return None

    # 未指定 topic：legacy 单文件
    return _load_cache_file(LEGACY_CACHE_PATH)
