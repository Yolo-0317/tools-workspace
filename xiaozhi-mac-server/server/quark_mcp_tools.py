"""Quark audio MCP tools (search + play) backed by quark-drive skill."""

from __future__ import annotations

import logging
from typing import Any

from server.intent_router import RoutedIntent
from server.quark_client import QuarkClient, QuarkFile
from server.config import settings

log = logging.getLogger(__name__)

_VALID_HINTS = {"story_audio", "movie", "music", "any"}


def _normalize_hint(media_hint: str) -> str:
    hint = (media_hint or "any").strip().lower()
    return hint if hint in _VALID_HINTS else "any"


def _candidate_row(item: QuarkFile, index: int) -> dict[str, Any]:
    size_mb = round(item.size / (1024 * 1024), 1) if item.size else 0
    return {
        "index": index,
        "fid": item.fid,
        "name": item.filename,
        "ext": item.ext,
        "size_mb": size_mb,
    }


_SPEAK_SEARCH_EMPTY = "抱歉，这个故事现在播不了，换一个名字试试好不好？"
_SPEAK_SEARCH_DOWN = "播放服务好像没开，请爸爸妈妈检查一下后再试。"


def search_quark_audio(
    query: str,
    *,
    media_hint: str = "story_audio",
    limit: int = 10,
) -> dict[str, Any]:
    """Search Quark cloud for audio/story files."""
    key = (query or "").strip()
    if not key:
        return {
            "success": False,
            "error": "query is required",
            "candidates": [],
            "count": 0,
            "speak_hint": "你想听哪个故事呀？跟我说名字就好。",
            "instruction": "Speak speak_hint now. Do not stay silent.",
        }

    client = QuarkClient.from_env()
    if client is None:
        return {
            "success": False,
            "error": "Quark skill not configured or not logged in",
            "candidates": [],
            "count": 0,
            "speak_hint": _SPEAK_SEARCH_DOWN,
            "instruction": "Speak speak_hint now. Do not stay silent.",
        }

    hint = _normalize_hint(media_hint)
    try:
        ranked = _rank_for_query(client, key, user_text=key, media_hint=hint)
    except Exception as exc:
        log.exception("Quark MCP search failed")
        return {
            "success": False,
            "error": str(exc),
            "candidates": [],
            "count": 0,
            "speak_hint": _SPEAK_SEARCH_EMPTY,
            "instruction": "Speak speak_hint now. Do not stay silent.",
        }

    rows = [_candidate_row(item, i) for i, item in enumerate(ranked[: max(1, limit)])]
    if not rows:
        # Empty list must not look like a soft success — agents stay silent otherwise.
        return {
            "success": False,
            "error": "no candidates",
            "query": key,
            "media_hint": hint,
            "count": 0,
            "candidates": [],
            "speak_hint": _SPEAK_SEARCH_EMPTY,
            "instruction": (
                "Speak speak_hint now if the user asked to play. "
                "Do not stay silent. Prefer resolve_quark_stream_url next time."
            ),
        }
    return {
        "success": True,
        "query": key,
        "media_hint": hint,
        "count": len(rows),
        "candidates": rows,
    }


def _rank_for_query(
    client: QuarkClient,
    keyword: str,
    *,
    user_text: str,
    media_hint: str,
) -> list[QuarkFile]:
    from server.content_catalog import catalog_filename_bonus, resolve_play_request

    hint = _normalize_hint(media_hint)
    search_key, hint, catalog_entry = resolve_play_request(
        keyword, user_text=user_text or keyword, media_hint=hint
    )
    keyword = search_key or keyword
    if catalog_entry and catalog_entry.search_queries:
        search_keys = list(catalog_entry.search_queries)
    elif hint == "story_audio":
        search_keys = [f"{keyword} 故事", f"{keyword} 有声书", f"{keyword} mp3", keyword]
    elif hint == "movie":
        search_keys = [f"{keyword} 电影", f"{keyword} mp4", keyword]
    elif hint == "music":
        search_keys = [f"{keyword} 儿歌", f"{keyword} mp3", keyword]
    else:
        search_keys = [f"{keyword} 故事", f"{keyword} mp3", f"{keyword} 音频", keyword]

    prefer_audio = hint != "movie"
    pick_limit = max(20, settings.quark_pick_top)
    ranked: list[QuarkFile] = []
    seen: set[str] = set()
    catalog_bonus = (
        (lambda f: catalog_filename_bonus(catalog_entry, f.filename))
        if catalog_entry
        else None
    )
    for q in search_keys:
        try:
            files = client.search_media(q, limit=pick_limit)
        except Exception as exc:
            log.warning("Quark search failed for %r: %s", q, exc)
            continue
        for item in client.rank_matches(
            keyword,
            files,
            prefer_audio=prefer_audio,
            bonus_for=catalog_bonus,
        ):
            if item.fid in seen:
                continue
            seen.add(item.fid)
            ranked.append(item)

    if catalog_entry and ranked:
        boosted = [
            f for f in ranked if catalog_filename_bonus(catalog_entry, f.filename) > 0
        ]
        if boosted:
            ranked = boosted

    return ranked


async def play_quark_on_session(
    session,
    query: str,
    *,
    user_text: str = "",
    media_hint: str = "story_audio",
    external: bool = False,
    mode: str = "search",
) -> dict[str, Any]:
    return await session.play_quark_from_mcp(
        query,
        user_text=user_text or query,
        media_hint=media_hint,
        external=external,
        mode=mode,
    )


async def play_quark_on_active_device(
    query: str,
    *,
    user_text: str = "",
    media_hint: str = "story_audio",
    http_app,
) -> dict[str, Any]:
    from server.device_registry import get_active_session

    session = get_active_session()
    if session is None:
        return {
            "success": False,
            "error": "没有已连接的小智设备。请先让 AtomS3R 连上本地网关 WebSocket。",
        }
    return await play_quark_on_session(
        session,
        query,
        user_text=user_text,
        media_hint=media_hint,
        external=True,
    )


def resolve_stream_preview(
    query: str,
    *,
    media_hint: str = "story_audio",
    lan_ip: str,
    http_port: int,
) -> dict[str, Any]:
    """Resolve configured catalog only (same as /api/media/resolve; no Quark search)."""
    from server.media_api import resolve_media_for_query

    result = resolve_media_for_query(query, media_hint=media_hint, user_text=query)
    if not result.get("success"):
        return result
    # Preserve legacy preview field names where useful.
    return {
        "success": True,
        "filename": result.get("filename"),
        "fid": result.get("fid"),
        "stream_url": result.get("stream_url")
        or f"http://{lan_ip}:{http_port}/stream/quark/{result.get('fid')}",
        "catalog_key": result.get("catalog_key"),
        "needs_audio_extract": False,
        "instruction": result.get("instruction"),
    }
