"""Web demo API: text command -> Quark search -> HTTP stream playback."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiohttp import web

from server.config import settings
from server.http_stream import cache_stream_source, cache_tts_audio, ffmpeg_available, playback_stream_path
from server.intent_router import analyze_user_intent
from server.llm import record_chat_turn
from server.quark_client import QuarkClient, QuarkFile
from server.voice_text import normalize_transcript

log = logging.getLogger(__name__)


def _keyword_from_text(text: str) -> str:
    return normalize_transcript(text) or text.strip()


def _file_json(item: QuarkFile) -> dict[str, Any]:
    return {
        "fid": item.fid,
        "filename": item.filename,
        "size": item.size,
        "format_type": item.format_type,
    }


def _quark_error_reply(keyword: str, exc: Exception) -> tuple[str, str]:
    message = str(exc)
    if "download file size limit" in message:
        reply = (
            f"找到了与「{keyword}」相关的文件，但夸克流式播放暂不支持超过约 52MB 的文件。"
            "你可以换个更小的音频，或者说具体书名。"
        )
    elif "53000" in message or "服务器内部异常" in message:
        reply = "夸克网盘搜索暂时异常，请稍后再试。"
    elif "文件找不到" in message:
        reply = f"网盘里没找到可播放的「{keyword}」，换个关键词试试。"
    elif "missing accessToken" in message or "not logged in" in message.lower():
        reply = "夸克网盘未登录或授权已过期，请重新完成 skill 授权。"
    else:
        reply = f"播放准备失败：{message}"
    return message, reply


async def _tts_stream_url(app: web.Application, text: str) -> str | None:
    from server.pipeline import synthesize_mp3_bytes

    reply = (text or "").strip()
    if not reply:
        return None
    mp3 = await synthesize_mp3_bytes(reply)
    if not mp3:
        return None
    return cache_tts_audio(app, mp3)


async def api_status(_: web.Request) -> web.Response:
    client = QuarkClient.from_env()
    from server.tencent_asr import tencent_asr_configured

    return web.json_response(
        {
            "quark": client is not None,
            "ffmpeg": ffmpeg_available(),
            "http_port": settings.http_port,
            "lan_ip": settings.lan_ip,
            "asr_backend": settings.asr_backend,
            "tencent_asr": tencent_asr_configured(),
            "asr_fallback_local": settings.asr_fallback_local,
        }
    )


async def api_search(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    text = str(body.get("text") or body.get("query") or "").strip()
    if not text:
        raise web.HTTPBadRequest(text="missing text")

    client = QuarkClient.from_env()
    if client is None:
        raise web.HTTPServiceUnavailable(
            text="Quark skill not configured or not logged in"
        )

    keyword = _keyword_from_text(text)
    try:
        files = await asyncio.to_thread(client.search_audio, keyword)
    except Exception as exc:
        log.exception("Quark search failed")
        message, reply = _quark_error_reply(keyword, exc)
        return web.json_response(
            {"ok": False, "keyword": keyword, "message": message, "reply": reply},
            status=502,
        )

    return web.json_response(
        {
            "input": text,
            "keyword": keyword,
            "count": len(files),
            "files": [_file_json(f) for f in files],
        }
    )


async def api_prepare(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    fid = str(body.get("fid") or "").strip()
    if not fid:
        raise web.HTTPBadRequest(text="missing fid")

    client = QuarkClient.from_env()
    if client is None:
        raise web.HTTPServiceUnavailable(text="Quark unavailable")

    try:
        source = await asyncio.to_thread(client.resolve_stream_source, fid)
    except Exception as exc:
        log.exception("Quark resolve failed fid=%s", fid)
        message, reply = _quark_error_reply("", exc)
        return web.json_response(
            {"ok": False, "message": message, "reply": reply},
            status=502,
        )

    cache_stream_source(request.app, source)
    proxy_url = f"http://{settings.lan_ip}:{settings.http_port}{playback_stream_path(source)}"
    return web.json_response(
        {
            "fid": source.fid,
            "filename": source.filename,
            "size": source.size,
            "proxy_url": proxy_url,
            "stream_url": playback_stream_path(source),
            "playback_mode": "audio_extract" if source.needs_audio_extract else "direct",
        }
    )


async def _play_from_text(
    request: web.Request,
    text: str,
    *,
    keyword: str | None = None,
    media_hint: str = "any",
    ack_override: str = "",
) -> web.Response:
    client = QuarkClient.from_env()
    if client is None:
        raise web.HTTPServiceUnavailable(text="Quark unavailable")

    search_key = keyword or _keyword_from_text(text)
    try:
        source = await asyncio.to_thread(
            client.find_stream_source,
            search_key,
            user_text=text,
            media_hint=media_hint,
        )
    except Exception as exc:
        log.exception("Quark find_stream_source failed")
        message, reply = _quark_error_reply(search_key, exc)
        return web.json_response(
            {
                "ok": False,
                "mode": "play",
                "keyword": search_key,
                "message": message,
                "reply": reply,
                "transcript": text,
            },
            status=502,
        )

    if source is None:
        return web.json_response(
            {
                "ok": False,
                "mode": "play",
                "keyword": search_key,
                "message": f"网盘里没找到与「{search_key}」相关的音频",
                "reply": f"我在夸克网盘里搜了「{search_key}」，没找到合适的音频。你可以换个说法，比如「想听儿童故事」。",
                "transcript": text,
            },
            status=404,
        )

    cache_stream_source(request.app, source)
    if ack_override.strip():
        reply = ack_override.strip()
    elif source.needs_audio_extract:
        reply = (
            f"好的，正在从电影《{source.filename}》提取音轨播放。"
            "首次加载可能要等几十秒，请耐心等待。"
        )
    else:
        reply = f"好的，帮你播放《{source.filename}》。"
    stream_url = playback_stream_path(source)
    ack_stream_url = await _tts_stream_url(request.app, reply)
    payload: dict[str, Any] = {
        "ok": True,
        "mode": "play",
        "keyword": search_key,
        "reply": reply,
        "transcript": text,
        "fid": source.fid,
        "filename": source.filename,
        "size": source.size,
        "proxy_url": f"http://{settings.lan_ip}:{settings.http_port}{stream_url}",
        "stream_url": stream_url,
        "playback_mode": "audio_extract" if source.needs_audio_extract else "direct",
    }
    if ack_stream_url:
        payload["ack_stream_url"] = ack_stream_url
    return web.json_response(payload)


async def _spoken_reply_payload(
    request: web.Request,
    text: str,
    reply: str,
    *,
    mode: str,
) -> web.Response:
    stream_url = await _tts_stream_url(request.app, reply)
    payload: dict[str, Any] = {
        "ok": True,
        "mode": mode,
        "reply": reply,
        "transcript": text,
    }
    if stream_url:
        payload["stream_url"] = stream_url
    return web.json_response(payload)


async def _route_user_text(request: web.Request, text: str) -> web.Response:
    normalized = normalize_transcript(text)
    if not normalized:
        return web.json_response(
            {
                "ok": False,
                "reply": "没听清，请再说一次。",
                "transcript": text,
            },
            status=422,
        )

    session_key = request.headers.get("X-Session-Id") or request.remote or "web"
    history_store: dict[str, list[dict[str, str]]] = request.app.setdefault(
        "web_chat_history", {}
    )
    history = history_store.setdefault(str(session_key), [])

    routed = await analyze_user_intent(normalized, history)

    if routed.action in {"chat", "clarify"}:
        record_chat_turn(history, normalized, routed.reply)
        mode = "clarify" if routed.action == "clarify" else "chat"
        return await _spoken_reply_payload(
            request, normalized, routed.reply, mode=mode
        )

    if routed.action == "play":
        search_key = routed.search_query or normalized
        if routed.reply:
            record_chat_turn(history, normalized, routed.reply)
        return await _play_from_text(
            request,
            normalized,
            keyword=search_key,
            media_hint=routed.media_hint,
            ack_override=routed.reply,
        )

    record_chat_turn(history, normalized, routed.reply or "好的。")
    return await _spoken_reply_payload(
        request, normalized, routed.reply or "好的。", mode="chat"
    )


async def api_play_text(request: web.Request) -> web.Response:
    """Search best match and return stream URL in one step."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    text = str(body.get("text") or "").strip()
    if not text:
        raise web.HTTPBadRequest(text="missing text")
    return await _route_user_text(request, text)


async def api_voice_turn(request: web.Request) -> web.Response:
    """Browser microphone -> faster-whisper -> same story play flow as text."""
    if not ffmpeg_available():
        return web.json_response(
            {
                "ok": False,
                "reply": "服务器还没装 ffmpeg，暂时不能处理语音。",
            },
            status=503,
        )

    audio_bytes: bytes | None = None
    content_type = request.content_type or ""

    if content_type.startswith("multipart/"):
        reader = await request.multipart()
        async for part in reader:
            if part.name == "audio":
                audio_bytes = await part.read()
                break
    elif content_type.startswith("audio/") or content_type == "application/octet-stream":
        audio_bytes = await request.read()

    if not audio_bytes:
        raise web.HTTPBadRequest(text="missing audio")

    from server.pipeline import transcribe_audio_bytes

    try:
        transcript = await asyncio.to_thread(transcribe_audio_bytes, audio_bytes)
    except Exception as exc:
        log.exception("Voice transcribe failed")
        return web.json_response(
            {"ok": False, "reply": f"语音识别失败：{exc}"},
            status=502,
        )

    if not transcript:
        return web.json_response(
            {
                "ok": False,
                "transcript": "",
                "reply": "没听清，请再说一次。可以说「想听冰雪奇缘故事」。",
            },
            status=422,
        )

    normalized = normalize_transcript(transcript)
    if not normalized:
        return web.json_response(
            {
                "ok": False,
                "transcript": transcript,
                "reply": "没听清，请再说一次。可以说「想听冰雪奇缘故事」。",
            },
            status=422,
        )

    response = await _route_user_text(request, normalized)
    try:
        payload = json.loads(response.text or "{}")
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        payload["transcript"] = normalized
        return web.json_response(payload, status=response.status)
    return response


def register_web_demo_routes(app: web.Application, static_dir) -> None:
    from pathlib import Path

    static_path = Path(static_dir)
    index_file = static_path / "index.html"

    async def demo_page(_: web.Request) -> web.Response:
        if not index_file.is_file():
            raise web.HTTPNotFound(text="demo page missing")
        resp = web.FileResponse(index_file)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return resp

    async def redirect_demo(_: web.Request) -> web.Response:
        raise web.HTTPFound("/demo/")

    app.router.add_get("/demo", redirect_demo)
    app.router.add_get("/demo/", demo_page)
    app.router.add_get("/demo/index.html", demo_page)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/story/search", api_search)
    app.router.add_post("/api/story/prepare", api_prepare)
    app.router.add_post("/api/story/play", api_play_text)
    app.router.add_post("/api/voice/turn", api_voice_turn)
