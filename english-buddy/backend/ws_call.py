"""WebSocket voice call: Whisper STT, Ollama, streaming TTS, barge-in."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import llm, stt, tts
from services.echo_guard import is_likely_teacher_echo
from services.auth_deps import ws_user_from_cookies
from services.call_registry import call_registry
from services.free_chat_limits import max_free_chat_sessions
from services.read_along_limits import max_read_along_sessions
from services.free_chat_access import free_chat_enabled_for_username
from services.stt_access import stt_enabled_for_username
from services.lesson_store import get_lesson, is_prewarm_ready
from services.user_store import lesson_owned_by
from services.pronunciation.assess import (
    assess_chunk,
    pronunciation_enabled,
    result_payload,
)
from services.call_session_log import log_call_event
from services.read_along import (
    ReadAlongState,
    align_child_spoken,
    child_attempt_coverage,
    expected_chunk_at,
    is_sufficient_child_attempt,
    merge_child_spoken,
)
from services.tts_cache import synthesize_with_cache
from teaching.free_chat_kickoffs import pick_free_kickoff
from teaching.programs import get_program

logger = logging.getLogger(__name__)
router = APIRouter()

SAMPLE_RATE = 16000
# STT 空结果时仍进入下一句（不写入 history 括号系统消息）
CHILD_DONE_MARKER = "__child_done__"


async def _pronunciation_gate(
    session: CallSession,
    spoken: str,
    *,
    raw_spoken: str | None = None,
) -> None:
    """Score child read-along attempt for UI colors; never blocks advancing."""
    if not pronunciation_enabled() or not session.stt_enabled:
        return
    if session.call_mode != "read_along" or not session.read_along.chunks:
        return
    expected = session.read_along.current_expected()
    if not expected:
        return

    chunk_index = session.read_along.index
    line_index = session.read_along.material_line_index_at(chunk_index)
    next_expected = expected_chunk_at(
        session.read_along.chunks, session.read_along.index + 1
    )
    result = assess_chunk(spoken, expected, next_expected=next_expected)
    payload = result_payload(
        line_index=line_index,
        chunk_index=chunk_index,
        expected=expected,
        spoken=raw_spoken or spoken,
        result=result,
    )
    payload["advance"] = True
    await session.send_json(payload)


def _read_along_tts_chunk_index(
    session: CallSession,
    assistant: str,
    line_index: int | None,
) -> int | None:
    """
    Chunk cache key for TTS. None → live synthesis (multi-chunk material line).
    """
    if session.call_mode != "read_along" or not session.lesson_id:
        return None
    ra = session.read_along
    if line_index is not None:
        span = ra.chunk_span_for_line(line_index)
        if not span:
            return ra.index
        start, end = span
        if end - start == 1 and ra.chunks[start].strip() == assistant.strip():
            return start
        return None
    return ra.index


async def _play_teacher_tts(
    session: CallSession,
    assistant: str,
    *,
    send_listen_status: bool = True,
    listen_message: str = "轮到小朋友",
    line_index: int | None = None,
) -> None:
    """Stream teacher TTS (synthesis may run while turn_lock is free)."""
    prog = get_program(session.program_id)
    await session.send_json({"type": "tts_start"})
    chunk_i = _read_along_tts_chunk_index(session, assistant, line_index)
    try:
        mp3 = await session.synthesize_teacher(assistant, chunk_index=chunk_i)
        if session.cancel.is_set():
            await session.send_json({"type": "interrupted"})
            await session.send_status("listening")
            return
        if mp3:
            await session.send_json(
                {
                    "type": "tts_audio",
                    "audio_base64": base64.b64encode(mp3).decode("ascii"),
                    "audio_mime": tts.output_mime_type(prog),
                }
            )
        else:
            await session.send_json({"type": "tts_failed"})
    except Exception as e:
        logger.warning("TTS failed: %s", e)
        await session.send_json({"type": "tts_failed", "message": str(e)})

    if session.cancel.is_set():
        await session.send_json({"type": "interrupted"})
    await session.send_json({"type": "tts_end"})
    session.discard_mic_buffer()
    if send_listen_status:
        if (
            session.call_mode == "read_along"
            and session.stt_enabled
            and not session.read_along.done
        ):
            await session.send_status("listening", listen_message)
        else:
            await session.send_status("listening")


async def _prepare_read_along_child_turn(
    session: CallSession,
    user_text: str,
    raw_child_text: str,
) -> str | None:
    """
    Advance read-along after child spoke. Caller must hold session.turn_lock.
    Returns next teacher chunk text, or None if lesson ended / waiting for more speech.
    """
    await session.send_json(
        {"type": "transcript", "text": raw_child_text, "final": True}
    )
    session.history.append({"role": "user", "content": user_text})
    await session.send_status("processing", "准备下一句…")

    scoring_text = raw_child_text
    if raw_child_text.strip() != CHILD_DONE_MARKER:
        expected = session.read_along.current_expected()
        if expected:
            next_expected = expected_chunk_at(
                session.read_along.chunks, session.read_along.index + 1
            )
            merged = merge_child_spoken(session.child_spoken_buffer, raw_child_text)
            if not is_sufficient_child_attempt(
                merged, expected, next_expected=next_expected
            ):
                session.child_spoken_buffer = merged
                aligned = align_child_spoken(merged, expected, next_expected)
                log_call_event(
                    session,
                    "read_along_retry",
                    chunk_index=session.read_along.index,
                    line_index=session.read_along.material_line_index_at(),
                    expected=expected,
                    spoken=raw_child_text,
                    merged=merged,
                    coverage=child_attempt_coverage(aligned, expected),
                )
                await session.send_status("listening", "继续说这一句…")
                return None
            session.child_spoken_buffer = ""
            scoring_text = align_child_spoken(merged, expected, next_expected)
            raw_child_text = merged
            user_text = scoring_text
    elif session.child_spoken_buffer.strip():
        expected = session.read_along.current_expected()
        if expected:
            merged = session.child_spoken_buffer.strip()
            session.child_spoken_buffer = ""
            next_expected = expected_chunk_at(
                session.read_along.chunks, session.read_along.index + 1
            )
            scoring_text = align_child_spoken(merged, expected, next_expected)
            raw_child_text = merged
            user_text = scoring_text

    if scoring_text.strip() != CHILD_DONE_MARKER:
        await _pronunciation_gate(session, user_text, raw_spoken=raw_child_text)

    assistant, lesson_done, _unclear = session.read_along.after_child_spoke(
        raw_child_text
    )
    if lesson_done and assistant is None:
        session.discard_mic_buffer()
        log_call_event(session, "lesson_complete", reason="done_no_next")
        await session.send_json({"type": "lesson_complete"})
        await session.send_status("listening", "课文读完了，点句子可重读")
        return None
    if not (assistant or "").strip():
        session.discard_mic_buffer()
        log_call_event(session, "lesson_complete", reason="empty_assistant")
        await session.send_json({"type": "lesson_complete"})
        await session.send_status("listening", "课文读完了，点句子可重读")
        return None

    log_call_event(
        session,
        "read_along_advance",
        chunk_index=session.read_along.index,
        line_index=session.read_along.material_line_index_at(),
        child_text=scoring_text,
        next_teacher=assistant,
        child_done=raw_child_text.strip() == CHILD_DONE_MARKER,
    )
    session.history.append({"role": "assistant", "content": assistant})
    session.discard_mic_buffer()
    return assistant


async def _deliver_teacher_read_along(
    session: CallSession,
    assistant: str,
    *,
    line_index: int | None = None,
    send_listen_status: bool = False,
    emit_reread_line: bool = False,
) -> None:
    """Send assistant_text + TTS; synthesis runs outside turn_lock."""
    async with session.turn_lock:
        session.clear_interrupt()
        session.child_spoken_buffer = ""
        session.discard_mic_buffer()
        session.playback_generation += 1
        await _send_assistant_text(
            session,
            assistant,
            line_index=line_index,
            playback_generation=session.playback_generation,
        )
        await session.send_status("speaking", "听老师念下一句…")
    await _play_teacher_tts(
        session,
        assistant,
        send_listen_status=send_listen_status,
        line_index=line_index,
    )
    if emit_reread_line and line_index is not None:
        await session.send_json(
            {
                "type": "reread_line",
                "line_index": line_index,
                "text": assistant,
            }
        )


async def _finish_read_along_child_turn(
    session: CallSession,
    user_text: str,
    raw_child_text: str,
) -> None:
    """Advance read-along after child spoke (prepare under lock, TTS outside)."""
    assistant: str | None = None
    line_idx: int | None = None
    async with session.turn_lock:
        assistant = await _prepare_read_along_child_turn(
            session, user_text, raw_child_text
        )
        if assistant:
            line_idx = session.read_along.material_line_index_at()
    if assistant and line_idx is not None:
        await _deliver_teacher_read_along(
            session, assistant, line_index=line_idx, send_listen_status=False
        )


async def _resume_listening(session: CallSession, message: str = "请再说一次") -> None:
    session.clear_interrupt()
    await session.send_status("listening", message)


async def _safe_run_turn(
    session: CallSession,
    user_text: str | None = None,
    *,
    from_pcm: bool = False,
) -> None:
    try:
        await session.run_turn(user_text, from_pcm=from_pcm)
    except Exception:
        logger.exception("run_turn failed")
        await _resume_listening(session, "出错了，请再说一次")


async def _send_assistant_text(
    session: "CallSession",
    text: str,
    *,
    line_index: int | None = None,
    playback_generation: int | None = None,
) -> None:
    payload: dict[str, Any] = {"type": "assistant_text", "text": text}
    if line_index is not None:
        payload["line_index"] = line_index
    if playback_generation is not None:
        payload["playback_generation"] = playback_generation
    elif (
        session.call_mode == "read_along"
        and session.reading_material
        and session.read_along.chunks
    ):
        payload["line_index"] = session.read_along.material_line_index_at()
    await session.send_json(payload)


class CallSession:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.history: list[dict[str, str]] = []
        self.reading_material: str | None = None
        self.call_mode: str = "free"
        self.read_along = ReadAlongState()
        self.program_id: str = "elsa_snow"
        self.call_started = False
        self.pcm_buffer = bytearray()
        self.cancel = asyncio.Event()
        self.turn_lock = asyncio.Lock()
        self.active = True
        self.tts_speed: float = 1.0
        self.lesson_id: str | None = None
        self.username: str | None = None
        self.registry_id: str = ""
        self.stt_enabled: bool = True
        self.reread_in_progress: bool = False
        self.listen_only_busy: bool = False
        # Skip one auto-advance after manual nav (上一句/翻页/下一句) in listen-only
        self.listen_only_hold_after_teacher: bool = False
        self.child_spoken_buffer: str = ""
        self.from_pcm_inflight: bool = False
        self.utterance_queued: bool = False
        self.playback_generation: int = 0

    def reset_read_along_session_state(self) -> None:
        """Clear listen-only / reread flags between calls or after end_call."""
        self.listen_only_busy = False
        self.listen_only_hold_after_teacher = False
        self.reread_in_progress = False
        self.from_pcm_inflight = False
        self.child_spoken_buffer = ""
        self.utterance_queued = False
        self.playback_generation = 0
        self.clear_interrupt()

    async def synthesize_teacher(
        self, text: str, *, chunk_index: int | None = None
    ) -> bytes:
        prog = get_program(self.program_id)
        return await synthesize_with_cache(
            text,
            lesson_id=self.lesson_id,
            chunk_index=chunk_index,
            tts_speed=self.tts_speed,
            program=prog,
        )

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self.active:
            await self.ws.send_text(json.dumps(payload))

    async def send_status(self, phase: str, message: str = "") -> None:
        await self.send_json({"type": "status", "phase": phase, "message": message})

    def request_interrupt(self) -> None:
        self.cancel.set()
        self.playback_generation += 1

    def clear_interrupt(self) -> None:
        self.cancel.clear()

    def append_pcm(self, data: bytes) -> None:
        self.pcm_buffer.extend(data)

    def take_pcm(self) -> bytes:
        buf = bytes(self.pcm_buffer)
        self.pcm_buffer.clear()
        return buf

    def discard_mic_buffer(self) -> None:
        """Drop buffered audio (e.g. while teacher TTS was playing)."""
        self.pcm_buffer.clear()

    def last_assistant_text(self) -> str | None:
        for turn in reversed(self.history):
            if turn.get("role") == "assistant":
                c = (turn.get("content") or "").strip()
                if c and not c.startswith("("):
                    return c
        return None

    async def run_turn(self, user_text: str | None = None, *, from_pcm: bool = False) -> None:
        if from_pcm and self.from_pcm_inflight:
            self.utterance_queued = True
            return

        pcm: bytes | None = None
        read_along_stt = False
        replay_utterance = False

        child_done_tap = False
        try:
            if from_pcm:
                self.from_pcm_inflight = True
                async with self.turn_lock:
                    self.clear_interrupt()
                    if not self.stt_enabled:
                        self.discard_mic_buffer()
                        return
                    if self.call_mode == "read_along" and self.read_along.done:
                        await self.send_json({"type": "lesson_complete"})
                        await self.send_status(
                            "listening", "课文读完了，点句子可重读"
                        )
                        return
                    read_along_turn = (
                        self.call_mode == "read_along"
                        and bool(self.reading_material)
                        and bool(self.read_along.chunks)
                    )
                    pcm = self.take_pcm()
                    pcm_ms = round(len(pcm) / (SAMPLE_RATE * 2) * 1000, 1) if pcm else 0
                    if not pcm:
                        if read_along_turn:
                            child_done_tap = True
                            log_call_event(
                                self,
                                "utterance_empty_pcm",
                                chunk_index=self.read_along.index,
                                line_index=self.read_along.material_line_index_at(),
                                expected=self.read_along.current_expected(),
                            )
                        else:
                            await self.send_status("listening", "没听清，请再说一次")
                            return
                    else:
                        read_along_stt = read_along_turn
                        log_call_event(
                            self,
                            "utterance_pcm",
                            pcm_bytes=len(pcm),
                            pcm_ms=pcm_ms,
                            chunk_index=self.read_along.index
                            if read_along_turn
                            else None,
                            line_index=self.read_along.material_line_index_at()
                            if read_along_turn
                            else None,
                            expected=self.read_along.current_expected()
                            if read_along_turn
                            else None,
                        )
                        await self.send_status("processing", "正在识别…")

                if child_done_tap:
                    await _finish_read_along_child_turn(
                        self, CHILD_DONE_MARKER, CHILD_DONE_MARKER
                    )
                    return

                if self.cancel.is_set():
                    await _resume_listening(self)
                    return
                try:
                    user_text = await stt.transcribe_pcm(
                        pcm,
                        SAMPLE_RATE,
                        fast=read_along_stt,
                    )
                except Exception as e:
                    log_call_event(self, "stt_error", error=str(e), pcm_ms=pcm_ms)
                    await self.send_json({"type": "error", "message": f"STT: {e}"})
                    if read_along_stt:
                        await _finish_read_along_child_turn(
                            self, CHILD_DONE_MARKER, CHILD_DONE_MARKER
                        )
                    else:
                        await _resume_listening(self)
                    return
                if self.cancel.is_set():
                    await _resume_listening(self)
                    return
                if read_along_stt:
                    log_call_event(
                        self,
                        "stt_result",
                        stt_text=user_text or "",
                        empty=not bool(user_text),
                        pcm_ms=pcm_ms,
                        chunk_index=self.read_along.index,
                        line_index=self.read_along.material_line_index_at(),
                        expected=self.read_along.current_expected(),
                    )
                if not user_text:
                    if read_along_stt:
                        user_text = CHILD_DONE_MARKER
                    else:
                        await self.send_status("listening", "没听清，请再说一次")
                        return

            pending_teacher: str | None = None
            pending_line_idx: int | None = None
            handled_read_along_child = False
            async with self.turn_lock:
                self.clear_interrupt()
                if from_pcm and self.call_mode != "read_along" and is_likely_teacher_echo(
                    user_text or "",
                    self.last_assistant_text(),
                ):
                    await self.send_status(
                        "listening", "听到的是老师刚才说的，请小朋友再说一次"
                    )
                    return

                if not user_text:
                    return

                raw_child_text = user_text
                read_along_child = (
                    from_pcm
                    and self.call_mode == "read_along"
                    and self.reading_material
                    and self.read_along.chunks
                )
                if read_along_child:
                    handled_read_along_child = True
                    pending_teacher = await _prepare_read_along_child_turn(
                        self, user_text, raw_child_text
                    )
                    if pending_teacher:
                        pending_line_idx = self.read_along.material_line_index_at()

            if handled_read_along_child:
                if pending_teacher and pending_line_idx is not None:
                    await _deliver_teacher_read_along(
                        self,
                        pending_teacher,
                        line_index=pending_line_idx,
                        send_listen_status=False,
                    )
                return

            async with self.turn_lock:
                if not user_text:
                    return

                await self.send_json(
                    {"type": "transcript", "text": user_text, "final": True}
                )
                self.history.append({"role": "user", "content": user_text})
                await self.send_status("processing", "想一想…")

                assistant: str | None = None
                if assistant is None:
                    try:
                        assistant = await llm.chat(
                            user_text,
                            self.history[:-1],
                            self.reading_material,
                            self.program_id,
                        )
                    except Exception as e:
                        await self.send_json({"type": "error", "message": str(e)})
                        await self.send_status("listening")
                        return

                if not (assistant or "").strip():
                    self.discard_mic_buffer()
                    await self.send_status("listening")
                    return

                if self.cancel.is_set():
                    await self.send_json({"type": "interrupted"})
                    await self.send_status("listening")
                    return

                self.history.append({"role": "assistant", "content": assistant})
                self.discard_mic_buffer()
                await _send_assistant_text(self, assistant)
                await self.send_status("speaking", "老师正在说…")
                await _play_teacher_tts(
                    self,
                    assistant,
                    listen_message="轮到你了，请说话…",
                )
        finally:
            if from_pcm:
                self.from_pcm_inflight = False
                if self.utterance_queued:
                    self.utterance_queued = False
                    replay_utterance = True
            if replay_utterance and self.active and self.call_started:
                asyncio.create_task(self.run_turn(from_pcm=True))


async def _advance_read_along_manual(session: CallSession) -> None:
    """ORT / manual skip: interrupt teacher and advance one line."""
    if (
        session.call_mode != "read_along"
        or not session.call_started
        or session.read_along.done
        or session.reread_in_progress
        or session.listen_only_busy
    ):
        return
    session.request_interrupt()
    assistant_to_speak: str | None = None
    stt_line_idx: int | None = None
    async with session.turn_lock:
        session.clear_interrupt()
        session.discard_mic_buffer()
        if session.read_along.done:
            return
        if session.stt_enabled:
            assistant_to_speak = await _prepare_read_along_child_turn(
                session, CHILD_DONE_MARKER, CHILD_DONE_MARKER
            )
            if assistant_to_speak:
                stt_line_idx = session.read_along.material_line_index_at()
    if session.stt_enabled:
        if assistant_to_speak and stt_line_idx is not None:
            await _deliver_teacher_read_along(
                session,
                assistant_to_speak,
                line_index=stt_line_idx,
                send_listen_status=False,
            )
        return
    async with session.turn_lock:
        session.clear_interrupt()
        session.discard_mic_buffer()
        if session.read_along.done:
            return
        expected = session.read_along.current_expected()
        if not expected:
            return
        assistant, lesson_done, _unclear = session.read_along.after_child_spoke(
            expected
        )
        if lesson_done and not assistant:
            await session.send_json({"type": "lesson_complete"})
            await session.send_status("listening", "课文读完了，点句子可重读")
            return
        if assistant:
            assistant_to_speak = assistant
    if assistant_to_speak:
        await _speak_teacher_line(
            session,
            assistant_to_speak,
            user_echo_for_history="(Manual advance)",
        )
        if not session.stt_enabled:
            session.listen_only_hold_after_teacher = True


async def _safe_advance_read_along(session: CallSession) -> None:
    try:
        await _advance_read_along_manual(session)
    except Exception:
        logger.exception("read_along_advance failed")
        await _resume_listening(session, "出错了，请再试")


async def _continue_listen_only(session: CallSession) -> None:
    """Listen-only: advance after client finished playing teacher TTS."""
    if (
        session.stt_enabled
        or session.call_mode != "read_along"
        or not session.call_started
        or session.read_along.done
        or session.reread_in_progress
        or session.listen_only_busy
    ):
        return
    if session.listen_only_hold_after_teacher:
        session.listen_only_hold_after_teacher = False
        return
    session.listen_only_busy = True
    assistant_to_speak: str | None = None
    lesson_done_flag = False
    try:
        async with session.turn_lock:
            if (
                not session.call_started
                or session.cancel.is_set()
                or session.stt_enabled
                or session.read_along.done
                or session.reread_in_progress
                or session.listen_only_hold_after_teacher
            ):
                if session.listen_only_hold_after_teacher:
                    session.listen_only_hold_after_teacher = False
                return
            expected = session.read_along.current_expected()
            if not expected:
                return
            assistant, lesson_done, _unclear = session.read_along.after_child_spoke(
                expected
            )
            if lesson_done and not assistant:
                lesson_done_flag = True
            elif assistant:
                assistant_to_speak = assistant
        if lesson_done_flag:
            await session.send_json({"type": "lesson_complete"})
            await session.send_status("listening", "课文读完了，点句子可重读")
            return
        if assistant_to_speak:
            await _speak_teacher_line(
                session,
                assistant_to_speak,
                user_echo_for_history="(Listen-only advance)",
            )
    finally:
        session.listen_only_busy = False


async def _kickoff_read_along(session: CallSession) -> None:
    material = (session.reading_material or "").strip()
    session.read_along.reset(material)
    opening = session.read_along.opening_line()
    await _speak_teacher_line(
        session,
        opening,
        user_echo_for_history=prog_hint(material),
        line_index=0,
    )


def prog_hint(material: str) -> str:
    return f"(Read-along started. Material:\n{material})"


async def _reread_line(
    session: CallSession,
    line_index: int,
    *,
    resume_listen_auto: bool = False,
) -> None:
    if session.call_mode != "read_along" or not session.reading_material:
        return
    if resume_listen_auto:
        session.listen_only_hold_after_teacher = False
    session.request_interrupt()
    session.reread_in_progress = True
    try:
        text: str | None = None
        idx = line_index
        async with session.turn_lock:
            session.clear_interrupt()
            session.discard_mic_buffer()
            text, idx = session.read_along.jump_to_line(line_index)
        if not text:
            return
        # 读完后点句子：从该句恢复带读（小朋友跟读 + 发音评分），而非只播一遍就结束
        await _speak_teacher_line(
            session,
            text,
            user_echo_for_history=f"(Reread line {idx + 1})",
            line_index=idx,
            reread_only=False,
        )
        if not session.stt_enabled and not resume_listen_auto:
            session.listen_only_hold_after_teacher = True
    finally:
        session.reread_in_progress = False


async def _speak_teacher_line(
    session: CallSession,
    assistant: str,
    *,
    user_echo_for_history: str,
    line_index: int | None = None,
    reread_only: bool = False,
) -> None:
    """Play a teacher line without treating kickoff text as child speech."""
    async with session.turn_lock:
        session.history.append({"role": "user", "content": user_echo_for_history})
        session.history.append({"role": "assistant", "content": assistant})
    await _deliver_teacher_read_along(
        session,
        assistant,
        line_index=line_index,
        send_listen_status=False,
        emit_reread_line=line_index is not None,
    )
    async with session.turn_lock:
        if reread_only or session.read_along.done:
            await session.send_json({"type": "lesson_complete"})
            await session.send_status("listening", "课文读完了，点句子可重读")
        elif not session.stt_enabled:
            await session.send_status("speaking", "听老师念下一句…")
        elif session.call_mode != "read_along":
            await session.send_status("listening", "轮到小朋友")


async def _kickoff_free_chat(session: CallSession) -> None:
    await session.run_turn(pick_free_kickoff(), from_pcm=False)


@router.websocket("/ws/call")
async def ws_call(websocket: WebSocket) -> None:
    await websocket.accept()
    session = CallSession(websocket)
    ws_user = ws_user_from_cookies(dict(websocket.cookies))
    ws_username = ws_user["username"] if ws_user else None
    registry_id = await call_registry.register(
        user_id=ws_user["id"] if ws_user else None,
        username=ws_username,
    )
    session.registry_id = registry_id
    session.username = ws_username
    if ws_username:
        log_call_event(session, "ws_connect")

    whisper = stt.whisper_status()
    await session.send_json(
        {
            "type": "ready",
            "stt": "whisper",
            "whisper": whisper,
            "model": llm.OLLAMA_MODEL,
            "sample_rate": SAMPLE_RATE,
            "duplex": True,
        }
    )

    try:
        if not whisper.get("ready"):
            try:
                await session.send_status("connecting", "加载 Whisper…")
                await stt.warmup()
                await session.send_json(
                    {
                        "type": "ready",
                        "stt": "whisper",
                        "whisper": stt.whisper_status(),
                        "model": llm.OLLAMA_MODEL,
                        "sample_rate": SAMPLE_RATE,
                        "duplex": True,
                    }
                )
            except Exception as e:
                await session.send_json(
                    {"type": "error", "message": f"Whisper unavailable: {e}"}
                )
                await websocket.close(code=1011)
                return

        if not await llm.ollama_reachable():
            await session.send_json(
                {
                    "type": "error",
                    "message": f"Ollama not reachable; pull {llm.OLLAMA_MODEL}",
                }
            )
            await websocket.close(code=1011)
            return

        while session.active:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                break

            if message.get("type") == "websocket.disconnect":
                break

            if bytes_data := message.get("bytes"):
                if session.stt_enabled:
                    session.append_pcm(bytes_data)
                continue

            text_data = message.get("text")
            if not text_data:
                continue

            try:
                data = json.loads(text_data)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "interrupt":
                session.request_interrupt()
                await session.send_json({"type": "interrupted"})
                if session.call_mode != "read_along":
                    await session.send_status("listening", "已打断，请说")
                continue

            if msg_type == "update_tts_speed":
                try:
                    session.tts_speed = tts.clamp_tts_speed(
                        float(data.get("tts_speed", 1.0))
                    )
                except (TypeError, ValueError):
                    pass
                await session.send_json(
                    {"type": "tts_speed", "tts_speed": session.tts_speed}
                )
                continue

            if msg_type == "reread_line":
                if not session.call_started:
                    continue
                try:
                    line_index = int(data.get("line_index", 0))
                except (TypeError, ValueError):
                    continue
                resume_listen_auto = bool(data.get("resume_listen_auto"))
                asyncio.create_task(
                    _reread_line(
                        session,
                        line_index,
                        resume_listen_auto=resume_listen_auto,
                    )
                )
                continue

            if msg_type == "end_call":
                if session.call_started:
                    log_call_event(
                        session,
                        "call_end",
                        chunk_index=session.read_along.index,
                        lesson_done=session.read_along.done,
                    )
                session.call_started = False
                session.reading_material = None
                session.lesson_id = None
                session.read_along = ReadAlongState()
                session.history.clear()
                session.request_interrupt()
                session.reset_read_along_session_state()
                await call_registry.update(
                    registry_id,
                    call_started=False,
                    call_mode="",
                    lesson_id=None,
                    program_id=None,
                )
                await session.send_json({"type": "call_ended"})
                continue

            if msg_type == "start_call":
                mode = (data.get("mode") or "read_along").strip()
                if mode == "free":
                    ws_user = ws_user_from_cookies(dict(websocket.cookies))
                    free_user = ws_user["username"] if ws_user else None
                    if not free_chat_enabled_for_username(free_user):
                        await session.send_json(
                            {
                                "type": "error",
                                "message": "自由聊天仅对指定账号开放",
                            }
                        )
                        continue
                if mode == "read_along":
                    cap = max_read_along_sessions()
                    active = await call_registry.read_along_active_count(
                        exclude_session_id=registry_id
                    )
                    if active >= cap:
                        await session.send_json(
                            {
                                "type": "error",
                                "message": (
                                    f"当前已有 {cap} 位小朋友在带读，"
                                    "请稍后再试"
                                ),
                            }
                        )
                        continue
                if mode == "free":
                    cap = max_free_chat_sessions()
                    active = await call_registry.free_chat_active_count(
                        exclude_session_id=registry_id
                    )
                    if active >= cap:
                        await session.send_json(
                            {
                                "type": "error",
                                "message": (
                                    f"当前已有 {cap} 位小朋友在自由聊天，"
                                    "请稍后再试"
                                ),
                            }
                        )
                        continue
                try:
                    session.tts_speed = tts.clamp_tts_speed(
                        float(data.get("tts_speed", 1.0))
                    )
                except (TypeError, ValueError):
                    session.tts_speed = 1.0
                session.program_id = (data.get("program") or data.get("program_id") or "elsa_snow").strip()
                lesson_id = (data.get("lesson_id") or "").strip()
                material = (data.get("reading_material") or "").strip()
                session.lesson_id = None
                if lesson_id:
                    row = get_lesson(lesson_id)
                    if not row:
                        await session.send_json(
                            {"type": "error", "message": "课文不存在"}
                        )
                        continue
                    if not row["is_builtin"]:
                        ws_user = ws_user_from_cookies(dict(websocket.cookies))
                        if not ws_user or not lesson_owned_by(
                            lesson_id, ws_user["id"]
                        ):
                            await session.send_json(
                                {"type": "error", "message": "自定义课文请先登录"}
                            )
                            continue
                    if not is_prewarm_ready(
                        lesson_id, session.tts_speed, session.program_id
                    ):
                        await session.send_json(
                            {
                                "type": "error",
                                "message": "请先完成课文语音预热（当前语速）",
                            }
                        )
                        continue
                    material = row["text"]
                    session.lesson_id = lesson_id
                elif mode == "read_along":
                    await session.send_json(
                        {
                            "type": "error",
                            "message": "请选择已预热的课文",
                        }
                    )
                    continue
                if session.call_started:
                    session.request_interrupt()
                    session.reset_read_along_session_state()
                session.reading_material = material or None
                session.call_mode = mode
                current_user = ws_user_from_cookies(dict(websocket.cookies))
                session.username = (
                    current_user["username"] if current_user else None
                )
                session.stt_enabled = stt_enabled_for_username(session.username)
                session.call_started = True
                session.history.clear()
                session.reset_read_along_session_state()
                await call_registry.update(
                    registry_id,
                    call_started=True,
                    call_mode=mode,
                    lesson_id=session.lesson_id,
                    program_id=session.program_id,
                )
                if mode == "read_along" and material:
                    session.read_along.reset(material)
                else:
                    session.read_along = ReadAlongState()
                prog = get_program(session.program_id)
                await session.send_json(
                    {
                        "type": "call_started",
                        "mode": mode,
                        "has_material": bool(material),
                        "stt_enabled": session.stt_enabled,
                        "pronunciation_assess": pronunciation_enabled(),
                        "program": prog.id,
                        "program_title": prog.title,
                        "program_subtitle": prog.subtitle,
                        "program_emoji": prog.emoji,
                    }
                )
                log_call_event(
                    session,
                    "call_start",
                    program=session.program_id,
                    tts_speed=session.tts_speed,
                    material_lines=len(session.read_along.chunks)
                    if mode == "read_along" and material
                    else 0,
                )
                await session.send_status(
                    "connecting",
                    "准备聊天…" if mode == "free" else "准备带读…",
                )
                if mode == "read_along" and material:
                    asyncio.create_task(_kickoff_read_along(session))
                else:
                    asyncio.create_task(_kickoff_free_chat(session))
                continue

            if msg_type == "text_message":
                text = (data.get("text") or "").strip()
                if not text:
                    continue
                if not session.call_started:
                    await session.send_json(
                        {
                            "type": "error",
                            "message": "请先点击开始通话",
                        }
                    )
                    continue
                asyncio.create_task(_safe_run_turn(session, text, from_pcm=False))
                continue

            if msg_type == "teacher_playback_done":
                if not (
                    session.call_started
                    and not session.stt_enabled
                    and session.call_mode == "read_along"
                ):
                    continue
                try:
                    client_gen = int(data.get("playback_generation", -1))
                except (TypeError, ValueError):
                    client_gen = -1
                if client_gen != session.playback_generation:
                    continue
                asyncio.create_task(_continue_listen_only(session))
                continue

            if msg_type == "read_along_advance":
                if session.call_started and session.call_mode == "read_along":
                    log_call_event(
                        session,
                        "manual_advance",
                        chunk_index=session.read_along.index,
                        line_index=session.read_along.material_line_index_at(),
                    )
                    asyncio.create_task(_safe_advance_read_along(session))
                continue

            if msg_type == "utterance_end":
                if not session.call_started:
                    continue
                if not session.stt_enabled:
                    log_call_event(session, "utterance_listen_only")
                    await session.send_status(
                        "listening", "只听模式，请跟老师一起读"
                    )
                    continue
                log_call_event(
                    session,
                    "utterance_end",
                    chunk_index=session.read_along.index,
                    line_index=session.read_along.material_line_index_at(),
                    expected=session.read_along.current_expected()
                    if session.call_mode == "read_along"
                    else None,
                )
                asyncio.create_task(_safe_run_turn(session, from_pcm=True))
                continue

            if msg_type == "ping":
                await session.send_json({"type": "pong"})
                continue

            if msg_type == "set_stt_active":
                if session.call_started:
                    session.stt_enabled = bool(data.get("enabled", False))
                    session.listen_only_busy = False
                    session.listen_only_hold_after_teacher = False
                    log_call_event(
                        session,
                        "stt_active",
                        enabled=session.stt_enabled,
                    )
                    await session.send_json(
                        {"type": "stt_active", "enabled": session.stt_enabled}
                    )
                continue

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws_call error")
    finally:
        if session.call_started:
            log_call_event(
                session,
                "ws_disconnect",
                chunk_index=session.read_along.index,
                lesson_done=session.read_along.done,
            )
        session.active = False
        session.request_interrupt()
        await call_registry.unregister(registry_id)
