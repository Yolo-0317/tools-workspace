"""Play cloud audio via Quark HTTP streaming."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from server.config import settings
from server.http_stream import (
    cache_stream_source,
    ffmpeg_available,
    iter_opus_from_http_source,
    stream_playback_summary,
)
from server.intent_router import RoutedIntent
from server.quark_client import QuarkClient, QuarkStreamSource

if TYPE_CHECKING:
    from server.playback_memory import PlaybackStore

log = logging.getLogger(__name__)


async def play_quark_content(
    routed: RoutedIntent,
    *,
    user_text: str,
    http_app,
    send_json,
    send_binary,
    session_id: str,
    should_stop=None,
    on_process=None,
    playback_memory: PlaybackStore | None = None,
    source: QuarkStreamSource | None = None,
    start_offset_s: float = 0,
    catalog_key: str | None = None,
) -> bool:
    """Play Quark content for a routed play intent. Returns True if handled."""
    search_key = (routed.search_query or user_text).strip()
    client = QuarkClient.from_env()
    if client is None:
        await _reply_play_error(
            send_json,
            send_binary,
            session_id,
            user_text,
            "我还不能访问夸克网盘，请先配置 quark skill。",
        )
        return True

    if source is None:
        if not search_key:
            await _reply_play_error(
                send_json,
                send_binary,
                session_id,
                user_text,
                "我还不知道你想听什么，可以说具体一点吗？",
            )
            return True
        try:
            source = await asyncio.to_thread(
                client.find_stream_source,
                search_key,
                user_text=user_text,
                media_hint=routed.media_hint,
            )
        except Exception as exc:
            log.exception("Quark search/resolve failed")
            message = str(exc)
            if "53000" in message or "服务器内部异常" in message:
                tip = "夸克网盘搜索暂时异常，请稍后再试。"
            elif "size limit" in message.lower():
                tip = "找到了文件，但太大，暂时无法流式播放。"
            else:
                tip = f"网盘查找失败：{message}"
            await _reply_play_error(
                send_json,
                send_binary,
                session_id,
                user_text,
                tip,
            )
            return True

        if source is None:
            await _reply_play_error(
                send_json,
                send_binary,
                session_id,
                user_text,
                f"网盘里没找到「{search_key}」合适的内容。你可以换个说法，或告诉我想要故事还是电影。",
            )
            return True

    if not ffmpeg_available():
        await _reply_play_error(
            send_json,
            send_binary,
            session_id,
            user_text,
            "这台机器还没装 ffmpeg，暂时不能流式播放。",
        )
        return True

    cache_stream_source(http_app, source)
    summary = stream_playback_summary(
        source, settings.lan_ip, settings.http_port
    )
    log.info("Quark stream ready: %s", summary)

    if catalog_key is None:
        from server.content_catalog import resolve_play_request

        _, _, entry = resolve_play_request(
            search_key or source.filename,
            user_text=user_text,
            media_hint=routed.media_hint,
        )
        catalog_key = entry.key if entry else None

    if playback_memory is not None:
        playback_memory.begin(
            source,
            query=search_key or source.filename,
            media_hint=routed.media_hint,
            catalog_key=catalog_key,
            start_offset_ms=int(start_offset_s * 1000),
        )

    if routed.reply.strip():
        ack = routed.reply.strip()
    elif start_offset_s > 1:
        ack = f"好的，从上次位置继续播《{source.filename}》。"
    elif source.needs_audio_extract:
        ack = (
            f"好的，正在从《{source.filename}》提取音轨播放。"
            "首次加载可能要等一会儿，请耐心听。"
        )
    else:
        ack = f"好的，开始播放《{source.filename}》。"

    await _emit_playback(
        send_json,
        send_binary,
        session_id,
        user_text,
        ack,
        source,
        should_stop=should_stop,
        on_process=on_process,
        start_offset_s=start_offset_s,
        playback_memory=playback_memory,
    )
    return True


async def play_quark_source(
    source: QuarkStreamSource,
    *,
    user_text: str,
    query: str,
    media_hint: str,
    http_app,
    send_json,
    send_binary,
    session_id: str,
    should_stop=None,
    on_process=None,
    playback_memory: PlaybackStore | None = None,
    start_offset_s: float = 0,
    catalog_key: str | None = None,
    reply: str = "",
) -> bool:
    routed = RoutedIntent(
        action="play",
        reply=reply,
        search_query=query,
        media_hint=media_hint,
    )
    return await play_quark_content(
        routed,
        user_text=user_text,
        http_app=http_app,
        send_json=send_json,
        send_binary=send_binary,
        session_id=session_id,
        should_stop=should_stop,
        on_process=on_process,
        playback_memory=playback_memory,
        source=source,
        start_offset_s=start_offset_s,
        catalog_key=catalog_key,
    )


async def _reply_play_error(send_json, send_binary, session_id, user_text, message: str) -> None:
    from server.speech_downlink import emit_speech

    await emit_speech(
        send_json=send_json,
        send_binary=send_binary,
        session_id=session_id,
        user_text=user_text,
        reply=message,
        emotion="sad",
    )


async def _emit_playback(
    send_json,
    send_binary,
    session_id,
    user_text,
    ack,
    source,
    *,
    should_stop=None,
    on_process=None,
    start_offset_s: float = 0,
    playback_memory: PlaybackStore | None = None,
) -> None:
    from server.speech_downlink import begin_speaking_session, end_speaking_session, send_opus_stream_paced

    await begin_speaking_session(
        send_json=send_json,
        send_binary=send_binary,
        session_id=session_id,
        user_text=user_text,
        ack=ack,
        emotion="happy",
    )

    listen_every = 0
    listen_window = 0.0
    if settings.stream_listen_every_s > 0:
        listen_every = max(
            1,
            int(settings.stream_listen_every_s * 1000 / settings.frame_ms),
        )
        listen_window = settings.stream_listen_window_s

    base_offset_ms = int(start_offset_s * 1000)
    frame_ms = settings.frame_ms

    async def _tracked_stream():
        packets = 0
        async for packet in iter_opus_from_http_source(
            source,
            should_stop=should_stop,
            on_process=on_process,
            start_offset_s=start_offset_s,
        ):
            packets += 1
            if playback_memory is not None and packets % 50 == 0:
                playback_memory.update_progress(base_offset_ms + packets * frame_ms)
            yield packet

    sent = await send_opus_stream_paced(
        send_binary,
        _tracked_stream(),
        send_json=send_json,
        session_id=session_id,
        should_stop=should_stop,
        listen_every_packets=listen_every,
        listen_window_s=listen_window,
    )
    stopped = bool(should_stop and should_stop())
    final_ms = base_offset_ms + sent * frame_ms
    if playback_memory is not None:
        playback_memory.finish(interrupted=stopped, final_position_ms=final_ms)

    log.info(
        "Quark stream downlink done (%d packets%s): %s",
        sent,
        ", interrupted" if stopped else "",
        source.filename,
    )

    if not stopped:
        await end_speaking_session(send_json=send_json, session_id=session_id)
