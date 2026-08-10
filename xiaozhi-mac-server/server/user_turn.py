"""Unified user turn: LLM intent -> chat/clarify TTS or Quark play."""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from server.intent_router import RoutedIntent, analyze_user_intent
from server.llm import record_chat_turn
from server.quark_playback import play_quark_content
from server.speech_downlink import emit_speech
from server.voice_text import normalize_transcript

log = logging.getLogger(__name__)

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendBinary = Callable[[bytes], Awaitable[None]]


async def _emit_spoken_reply(
    *,
    send_json: SendJson,
    send_binary: SendBinary,
    session_id: str,
    user_text: str,
    reply: str,
    emotion: str = "happy",
) -> None:
    await emit_speech(
        send_json=send_json,
        send_binary=send_binary,
        session_id=session_id,
        user_text=user_text,
        reply=reply,
        emotion=emotion,
    )


async def handle_user_turn(
    user_text: str,
    *,
    history: list[dict[str, str]],
    http_app,
    send_json: SendJson,
    send_binary: SendBinary,
    session_id: str,
    session=None,
) -> None:
    from server.config import settings

    if settings.use_mcp_tools and session is not None:
        from server.mcp_turn import handle_user_turn_mcp

        await handle_user_turn_mcp(
            user_text,
            history=history,
            session=session,
            send_json=send_json,
            send_binary=send_binary,
            session_id=session_id,
        )
        return

    text = normalize_transcript(user_text) or (user_text or "").strip()
    if not text:
        await _emit_spoken_reply(
            send_json=send_json,
            send_binary=send_binary,
            session_id=session_id,
            user_text=user_text or "（空）",
            reply="我没听清，你可以再说一次吗？",
            emotion="sad",
        )
        return

    routed = await analyze_user_intent(text, history)

    if routed.action in {"chat", "clarify"}:
        record_chat_turn(history, text, routed.reply)
        emotion = "happy"
        await _emit_spoken_reply(
            send_json=send_json,
            send_binary=send_binary,
            session_id=session_id,
            user_text=text,
            reply=routed.reply,
            emotion=emotion,
        )
        return

    if routed.action == "play":
        mem = getattr(session, "playback_memory", None) if session else None
        should_stop = getattr(session, "should_stop_playback", None) if session else None
        on_process = getattr(session, "_attach_ffmpeg_proc", None) if session else None
        # Keep session interruptible: without should_stop, wake/abort cannot
        # end the await and _busy stays true forever (Session busy queue).
        if session is not None:
            session._playback_active = True
            if hasattr(session, "_reset_playback_cancel"):
                session._reset_playback_cancel()
        try:
            played = await play_quark_content(
                routed,
                user_text=text,
                http_app=http_app,
                send_json=send_json,
                send_binary=send_binary,
                session_id=session_id,
                should_stop=should_stop,
                on_process=on_process,
                playback_memory=mem,
            )
        finally:
            if session is not None:
                session._playback_active = False
                session._ffmpeg_proc = None
        if played and routed.reply:
            record_chat_turn(history, text, routed.reply)
        return

    record_chat_turn(history, text, routed.reply or "好的。")
    await _emit_spoken_reply(
        send_json=send_json,
        send_binary=send_binary,
        session_id=session_id,
        user_text=text,
        reply=routed.reply or "好的。",
    )
