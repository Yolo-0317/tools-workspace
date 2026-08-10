"""HTTP API for external MCP server to search/play on connected devices."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from server.config import settings
from server.device_registry import status as registry_status
from server.quark_mcp_tools import (
    play_quark_on_active_device,
    resolve_stream_preview,
    search_quark_audio,
)

log = logging.getLogger(__name__)


async def api_mcp_status(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "ok": True,
            "gateway": f"http://{settings.lan_ip}:{settings.http_port}",
            "devices": registry_status(),
            "use_mcp_tools": settings.use_mcp_tools,
        }
    )


async def api_mcp_search(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = str(body.get("query") or body.get("text") or "").strip()
    media_hint = str(body.get("media_hint") or "story_audio")
    limit = int(body.get("limit") or 10)
    result = search_quark_audio(query, media_hint=media_hint, limit=limit)
    return web.json_response(result, status=200)


async def api_mcp_play(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = str(body.get("query") or body.get("text") or "").strip()
    if not query:
        return web.json_response(
            {
                "success": False,
                "error": "missing query",
                "speak_hint": "你想听哪个故事呀？跟我说名字就好。",
                "instruction": "Speak speak_hint now. Do not stay silent.",
            },
            status=200,
        )
    user_text = str(body.get("user_text") or query).strip()
    media_hint = str(body.get("media_hint") or "story_audio")
    result = await play_quark_on_active_device(
        query,
        user_text=user_text,
        media_hint=media_hint,
        http_app=request.app,
    )
    if not result.get("success"):
        result.setdefault(
            "speak_hint",
            "抱歉，这个故事现在播不了，换一个名字试试好不好？",
        )
        result.setdefault(
            "instruction",
            "Speak speak_hint now. Do not stay silent.",
        )
    return web.json_response(result, status=200)


async def api_mcp_volume(request: web.Request) -> web.Response:
    """Set speaker volume on the active device (0-100)."""
    from server.device_control import set_device_volume
    from server.device_registry import get_active_session

    try:
        body = await request.json()
    except Exception:
        body = {}
    session = get_active_session()
    if session is None:
        return web.json_response(
            {"success": False, "error": "no connected device"}, status=409
        )
    vol = int(body.get("volume") if body.get("volume") is not None else settings.device_default_volume)
    vol = max(0, min(100, vol))
    session.device_volume = vol  # type: ignore[attr-defined]
    await set_device_volume(session, vol)
    return web.json_response({"success": True, "volume": vol})


async def api_mcp_speak(request: web.Request) -> web.Response:
    """Force a short TTS phrase to the active device (audio path probe)."""
    from server.device_control import set_device_volume
    from server.device_registry import get_active_session
    from server.speech_downlink import emit_speech

    try:
        body = await request.json()
    except Exception:
        body = {}
    session = get_active_session()
    if session is None:
        return web.json_response(
            {"success": False, "error": "no connected device"}, status=409
        )
    text = str(body.get("text") or "音量测试，一二三。").strip()
    if body.get("volume") is not None:
        vol = max(0, min(100, int(body["volume"])))
        session.device_volume = vol  # type: ignore[attr-defined]
        await set_device_volume(session, vol)
    busy = bool(getattr(session, "_busy", False) or getattr(session, "_playback_active", False))
    if busy:
        return web.json_response(
            {"success": False, "error": "device busy", "hint": "wait or abort playback"},
            status=409,
        )
    session._busy = True  # type: ignore[attr-defined]
    try:
        await emit_speech(
            send_json=session.send_json,  # type: ignore[attr-defined]
            send_binary=session.send_binary,  # type: ignore[attr-defined]
            session_id=session.session_id,
            reply=text,
            include_stt=False,
            emotion="happy",
        )
    except Exception as exc:
        log.exception("MCP speak failed")
        return web.json_response({"success": False, "error": str(exc)}, status=500)
    finally:
        session._busy = False  # type: ignore[attr-defined]
    return web.json_response({"success": True, "text": text, "volume": getattr(session, "device_volume", None)})


async def api_mcp_resolve(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = str(body.get("query") or "").strip()
    media_hint = str(body.get("media_hint") or "story_audio")
    result = resolve_stream_preview(
        query,
        media_hint=media_hint,
        lan_ip=settings.lan_ip,
        http_port=settings.http_port,
    )
    if not result.get("success"):
        result.setdefault(
            "speak_hint",
            "抱歉，这个故事现在播不了，换一个名字试试好不好？",
        )
        result.setdefault(
            "instruction",
            "Speak speak_hint now. Do not call play_url. Do not stay silent.",
        )
    # Business miss must stay HTTP 200 so cloud agents speak instead of freezing.
    return web.json_response(result, status=200)


def register_mcp_routes(app: web.Application) -> None:
    app.router.add_get("/api/mcp/status", api_mcp_status)
    app.router.add_post("/api/mcp/search", api_mcp_search)
    app.router.add_post("/api/mcp/play", api_mcp_play)
    app.router.add_post("/api/mcp/resolve", api_mcp_resolve)
    app.router.add_post("/api/mcp/volume", api_mcp_volume)
    app.router.add_post("/api/mcp/speak", api_mcp_speak)
