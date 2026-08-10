"""HTTP APIs for cloud-HTTP design: resolve / next / resume → device.mp3 URLs."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from server.config import settings
from server.content_catalog import resolve_play_request, speak_hint_not_in_catalog
from server.http_stream import cache_stream_source, device_mp3_path
from server.media_index import index_available, pick_best_file
from server.playback_memory import PlaybackStore, find_next_episode_source
from server.quark_client import QuarkClient

log = logging.getLogger(__name__)

# Shared key when no device session (cloud MCP path).
_MEDIA_DEVICE_KEY = "cloud-media"


def _stream_urls(fid: str, *, from_ms: int = 0) -> dict[str, str]:
    base = f"http://{settings.lan_ip}:{settings.http_port}"
    path = device_mp3_path(fid)
    if from_ms > 0:
        path = f"{path}?from_ms={int(from_ms)}"
    return {
        "stream_url": f"{base}{path}",
        "raw_proxy_url": f"{base}/stream/quark/{fid}",
        "from_ms": from_ms,
    }


def _payload_from_source(
    source,
    *,
    query: str,
    catalog_key: str | None,
    media_hint: str,
    from_ms: int = 0,
) -> dict[str, Any]:
    urls = _stream_urls(source.fid, from_ms=from_ms)
    return {
        "success": True,
        "query": query,
        "catalog_key": catalog_key,
        "media_hint": media_hint,
        "fid": source.fid,
        "filename": source.filename,
        "title": source.filename.rsplit(".", 1)[0],
        **urls,
        "instruction": (
            "Call device MCP self.audio.play_url with stream_url; "
            "do not narrate the story via TTS."
        ),
    }


def resolve_media_for_query(
    query: str,
    *,
    user_text: str = "",
    media_hint: str = "story_audio",
    device_key: str = _MEDIA_DEVICE_KEY,
    http_app: web.Application | None = None,
) -> dict[str, Any]:
    """Pick episode from configured catalog + local index only (no Quark search)."""
    key = (query or "").strip()
    if not key:
        return {
            "success": False,
            "error": "query is required",
            "speak_hint": "你想听哪个故事呀？跟我说名字就好。",
            "instruction": "Speak speak_hint now. Do not stay silent.",
        }

    client = QuarkClient.from_env()
    if client is None:
        return {
            "success": False,
            "error": "Quark not configured",
            "speak_hint": "播放服务还没准备好，请爸爸妈妈检查一下后再试。",
            "instruction": "Speak speak_hint now. Do not stay silent.",
        }

    utterance = (user_text or key).strip()
    search_key, hint, entry = resolve_play_request(
        key, user_text=utterance, media_hint=media_hint
    )
    catalog_key = entry.key if entry else None
    episode = entry.episode if entry else None

    # Play path: only curated 玥玥 catalog. Never Quark live-search (slow + silent risk).
    if catalog_key is None:
        log.info("media resolve: not in catalog query=%r", key)
        return {
            "success": False,
            "error": "not in configured catalog",
            "query": key,
            "catalog_key": None,
            "speak_hint": speak_hint_not_in_catalog(),
            "instruction": (
                "Speak speak_hint to the child now. "
                "Do NOT call play_url. Do NOT search. Do NOT stay silent."
            ),
        }

    if not index_available():
        return {
            "success": False,
            "error": "media index unavailable",
            "query": key,
            "catalog_key": catalog_key,
            "speak_hint": "播放目录还没准备好，请爸爸妈妈稍后再试。",
            "instruction": "Speak speak_hint now. Do not stay silent.",
        }

    def _token_error(exc: BaseException) -> bool:
        msg = str(exc)
        return (
            "11017" in msg
            or "宽限期" in msg
            or "Access Token" in msg
            or "access_token" in msg.lower()
        )

    store = PlaybackStore(device_key)
    from_ms = 0
    # Bare series name (no explicit episode): resume unfinished episode in this catalog.
    resume_rec = None
    if episode is None and catalog_key:
        resume_rec = store.incomplete_for_catalog(catalog_key)

    picked = None
    if resume_rec is not None:
        from server.media_index import find_file_by_fid

        picked = find_file_by_fid(resume_rec.fid)
        if picked is None:
            from server.media_index import IndexedFile
            from server.playback_memory import episode_sort_key

            picked = IndexedFile(
                fid=resume_rec.fid,
                filename=resume_rec.filename,
                size=0,
                catalog_key=catalog_key or "",
                sort_key=episode_sort_key(resume_rec.filename),
            )
        from_ms = int(resume_rec.position_ms or 0)
        log.info(
            "media resolve: resume incomplete catalog=%s file=%s from_ms=%s",
            catalog_key,
            resume_rec.filename,
            from_ms,
        )
    else:
        picked = pick_best_file(
            catalog_key,
            keyword=search_key or key,
            episode=episode,
            user_text=utterance,
        )
    if picked is None:
        log.warning(
            "media resolve: catalog hit but no file query=%r catalog=%s",
            key,
            catalog_key,
        )
        return {
            "success": False,
            "error": "no playable file in catalog",
            "query": key,
            "catalog_key": catalog_key,
            "speak_hint": "抱歉，这个故事现在播不了，换一个名字试试好不好？",
            "instruction": (
                "Speak speak_hint to the child now. "
                "Do NOT call play_url. Do NOT retry the same query. Do NOT stay silent."
            ),
        }

    source = None
    index_token_failed = False
    try:
        source = client.resolve_stream_source(
            picked.fid,
            filename_hint=picked.filename,
            size_hint=picked.size,
        )
    except Exception as exc:
        log.warning("index resolve failed %s: %s", picked.filename, exc)
        if _token_error(exc):
            try:
                source = client.resolve_stream_source(
                    picked.fid,
                    filename_hint=picked.filename,
                    size_hint=picked.size,
                )
            except Exception as exc2:
                log.warning(
                    "index resolve retry failed %s: %s",
                    picked.filename,
                    exc2,
                )
                index_token_failed = True
        else:
            index_token_failed = False
            return {
                "success": False,
                "error": str(exc)[:300],
                "query": key,
                "catalog_key": catalog_key,
                "speak_hint": "抱歉，播放出了点小问题，稍后再试一次好不好？",
                "instruction": "Speak speak_hint now. Do not stay silent.",
            }

    if source is not None and getattr(picked, "audio_map", None):
        from dataclasses import replace

        source = replace(source, audio_map=picked.audio_map)

    if source is None:
        log.warning(
            "media resolve: no playable file query=%r catalog=%s token_fail=%s",
            key,
            catalog_key,
            index_token_failed,
        )
        speak = (
            "网络有点慢，我没找到可播的故事，再说一次或者换一个好不好？"
            if index_token_failed
            else "抱歉，这个故事现在播不了，换一个名字试试好不好？"
        )
        return {
            "success": False,
            "error": "token expired" if index_token_failed else "no playable file",
            "query": key,
            "catalog_key": catalog_key,
            "speak_hint": speak,
            "instruction": (
                "Speak speak_hint to the child now. "
                "Do NOT call play_url. Do NOT retry the same query. Do NOT stay silent."
            ),
        }

    if http_app is not None:
        cache_stream_source(http_app, source)

    store.begin(
        source,
        query=utterance or key,
        media_hint=hint,
        catalog_key=catalog_key,
        start_offset_ms=from_ms,
    )
    return _payload_from_source(
        source,
        query=utterance or key,
        catalog_key=catalog_key,
        media_hint=hint,
        from_ms=from_ms,
    )


def next_media(
    *,
    device_key: str = _MEDIA_DEVICE_KEY,
    http_app: web.Application | None = None,
) -> dict[str, Any]:
    client = QuarkClient.from_env()
    if client is None:
        return {
            "success": False,
            "error": "Quark not configured",
            "speak_hint": "播放服务还没准备好，请爸爸妈妈检查一下后再试。",
        }
    store = PlaybackStore(device_key)
    record = store.last_played()
    if record is None:
        return {
            "success": False,
            "error": "no playback history",
            "speak_hint": "还没开始播故事呢，想听什么跟我说呀。",
        }
    source = find_next_episode_source(client, record)
    if source is None:
        return {
            "success": False,
            "error": "no next episode",
            "filename": record.filename,
            "speak_hint": "这一集播完啦，没有下一集了，换个故事好不好？",
        }
    if http_app is not None:
        cache_stream_source(http_app, source)
    store.begin(
        source,
        query=record.query or record.filename,
        media_hint=record.media_hint,
        catalog_key=record.catalog_key,
    )
    return _payload_from_source(
        source,
        query=record.query or "",
        catalog_key=record.catalog_key,
        media_hint=record.media_hint,
    )


def resume_media(
    *,
    device_key: str = _MEDIA_DEVICE_KEY,
    http_app: web.Application | None = None,
) -> dict[str, Any]:
    """Resume current unfinished episode from saved position (device.mp3?from_ms=)."""
    client = QuarkClient.from_env()
    if client is None:
        return {
            "success": False,
            "error": "Quark not configured",
            "speak_hint": "播放服务还没准备好，请爸爸妈妈检查一下后再试。",
        }
    store = PlaybackStore(device_key)
    record = store.resume_target() or store.last_played()
    if record is None or not record.fid:
        return {
            "success": False,
            "error": "nothing to resume",
            "speak_hint": "现在没有可以继续播的故事，想听什么跟我说呀。",
        }
    from_ms = 0 if record.completed else max(0, int(record.position_ms or 0))
    try:
        source = client.resolve_stream_source(
            record.fid,
            filename_hint=record.filename,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "speak_hint": "抱歉，播放出了点小问题，稍后再试一次好不好？",
        }
    if http_app is not None:
        cache_stream_source(http_app, source)
    store.begin(
        source,
        query=record.query or record.filename,
        media_hint=record.media_hint,
        catalog_key=record.catalog_key,
        start_offset_ms=from_ms,
    )
    out = _payload_from_source(
        source,
        query=record.query or "",
        catalog_key=record.catalog_key,
        media_hint=record.media_hint,
        from_ms=from_ms,
    )
    out["note"] = (
        f"resuming from {from_ms}ms"
        if from_ms > 0
        else "resuming from start of current file"
    )
    return out


async def api_media_resolve(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        result = resolve_media_for_query(
            str(body.get("query") or body.get("text") or ""),
            user_text=str(body.get("user_text") or ""),
            media_hint=str(body.get("media_hint") or "story_audio"),
            device_key=str(body.get("device_key") or _MEDIA_DEVICE_KEY),
            http_app=request.app,
        )
    except Exception as exc:
        log.exception("api_media_resolve crashed")
        result = {
            "success": False,
            "error": str(exc)[:300],
            "speak_hint": "抱歉，播放出了点小问题，稍后再试一次好不好？",
            "instruction": "Speak speak_hint now. Do not stay silent.",
        }
    # Always HTTP 200 for business outcomes so MCP/cloud agents don't treat
    # "not found" as a transport failure and go silent or retry forever.
    return web.json_response(result, status=200)


async def api_media_next(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = next_media(
        device_key=str(body.get("device_key") or _MEDIA_DEVICE_KEY),
        http_app=request.app,
    )
    if not result.get("success"):
        result.setdefault(
            "speak_hint",
            "这一集播完啦，没有下一集了，换个故事好不好？",
        )
        result.setdefault(
            "instruction",
            "Speak speak_hint. Do not call play_url.",
        )
    return web.json_response(result, status=200)


async def api_media_resume(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = resume_media(
        device_key=str(body.get("device_key") or _MEDIA_DEVICE_KEY),
        http_app=request.app,
    )
    if not result.get("success"):
        result.setdefault(
            "speak_hint",
            "现在没有可以继续播的故事，想听什么跟我说呀。",
        )
        result.setdefault(
            "instruction",
            "Speak speak_hint. Do not call play_url.",
        )
    return web.json_response(result, status=200)


async def api_media_status(_: web.Request) -> web.Response:
    store = PlaybackStore(_MEDIA_DEVICE_KEY)
    cur = store.current
    return web.json_response(
        {
            "ok": True,
            "media_only": settings.media_only,
            "current": cur.to_dict() if cur else None,
            "device_mp3_example": (
                f"http://{settings.lan_ip}:{settings.http_port}"
                "/stream/quark/{{fid}}/device.mp3"
            ),
        }
    )


async def api_stories_list(_: web.Request) -> web.Response:
    from server.local_stories import list_story_titles

    return web.json_response({"success": True, "stories": list_story_titles()})


async def api_stories_resolve(request: web.Request) -> web.Response:
    from server.local_stories import resolve_local_story

    try:
        body = await request.json()
    except Exception:
        body = {}
    query = str(body.get("query") or body.get("user_text") or "").strip()
    return web.json_response(resolve_local_story(query))


def register_media_routes(app: web.Application) -> None:
    app.router.add_get("/api/media/status", api_media_status)
    app.router.add_post("/api/media/resolve", api_media_resolve)
    app.router.add_post("/api/media/next", api_media_next)
    app.router.add_post("/api/media/resume", api_media_resume)
    app.router.add_get("/api/stories/list", api_stories_list)
    app.router.add_post("/api/stories/resolve", api_stories_resolve)
