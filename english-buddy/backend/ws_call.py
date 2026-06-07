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
from services.read_along import (
    ReadAlongState,
    align_child_spoken,
    expected_chunk_at,
    llm_user_wrapper,
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


async def _play_teacher_tts(
    session: CallSession,
    assistant: str,
    *,
    send_listen_status: bool = True,
    listen_message: str = "轮到小朋友",
) -> None:
    """Stream teacher TTS. Caller must hold session.turn_lock."""
    prog = get_program(session.program_id)
    await session.send_json({"type": "tts_start"})
    chunk_i = (
        session.read_along.index
        if session.call_mode == "read_along" and session.lesson_id
        else None
    )
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


async def _finish_read_along_child_turn(
    session: CallSession,
    user_text: str,
    raw_child_text: str,
) -> None:
    """Advance read-along after child spoke. Caller must hold session.turn_lock."""
    await session.send_json(
        {"type": "transcript", "text": raw_child_text, "final": True}
    )
    session.history.append({"role": "user", "content": user_text})
    await session.send_status("processing", "准备下一句…")
    if raw_child_text.strip() != CHILD_DONE_MARKER:
        await _pronunciation_gate(session, user_text, raw_spoken=raw_child_text)
    assistant, lesson_done, _unclear = session.read_along.after_child_spoke(
        raw_child_text
    )
    if lesson_done and assistant is None:
        session.discard_mic_buffer()
        await session.send_json({"type": "lesson_complete"})
        await session.send_status("listening", "课文读完了，点句子可重读")
        return
    if not (assistant or "").strip():
        session.discard_mic_buffer()
        await session.send_json({"type": "lesson_complete"})
        await session.send_status("listening", "课文读完了，点句子可重读")
        return

    session.history.append({"role": "assistant", "content": assistant})
    session.discard_mic_buffer()
    line_idx = session.read_along.material_line_index_at()
    await _send_assistant_text(session, assistant, line_index=line_idx)
    await session.send_status("speaking", "听老师念下一句…")
    # 等客户端播完再切「小朋友说」，避免 listening 早于 tts_audio 导致同一句循环
    await _play_teacher_tts(session, assistant, send_listen_status=False)


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
) -> None:
    payload: dict[str, Any] = {"type": "assistant_text", "text": text}
    if line_index is not None:
        payload["line_index"] = line_index
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
        self.stt_enabled: bool = True
        self.reread_in_progress: bool = False
        self.listen_only_busy: bool = False
        # Skip one auto-advance after manual nav (上一句/翻页/下一句) in listen-only
        self.listen_only_hold_after_teacher: bool = False
        self.child_spoken_buffer: str = ""
        self.from_pcm_inflight: bool = False

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
            return

        pcm: bytes | None = None
        read_along_stt = False

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
                    if not pcm:
                        if read_along_turn:
                            await _finish_read_along_child_turn(
                                self, CHILD_DONE_MARKER, CHILD_DONE_MARKER
                            )
                            return
                        await self.send_status("listening", "没听清，请再说一次")
                        return
                    read_along_stt = read_along_turn
                    await self.send_status("processing", "正在识别…")

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
                    await self.send_json({"type": "error", "message": f"STT: {e}"})
                    if read_along_stt:
                        async with self.turn_lock:
                            await _finish_read_along_child_turn(
                                self, CHILD_DONE_MARKER, CHILD_DONE_MARKER
                            )
                    else:
                        await _resume_listening(self)
                    return
                if self.cancel.is_set():
                    await _resume_listening(self)
                    return
                if not user_text:
                    if read_along_stt:
                        user_text = CHILD_DONE_MARKER
                    else:
                        await self.send_status("listening", "没听清，请再说一次")
                        return

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
                    if user_text.strip() != CHILD_DONE_MARKER:
                        expected = self.read_along.current_expected()
                        if expected:
                            next_expected = expected_chunk_at(
                                self.read_along.chunks, self.read_along.index + 1
                            )
                            merged = merge_child_spoken(
                                self.child_spoken_buffer, user_text
                            )
                            self.child_spoken_buffer = ""
                            user_text = align_child_spoken(
                                merged, expected, next_expected
                            )
                            raw_child_text = merged
                    await _finish_read_along_child_turn(
                        self, user_text, raw_child_text
                    )
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
    async with session.turn_lock:
        session.clear_interrupt()
        session.discard_mic_buffer()
        if session.read_along.done:
            return
        if session.stt_enabled:
            await _finish_read_along_child_turn(
                session, CHILD_DONE_MARKER, CHILD_DONE_MARKER
            )
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
    try:
        await asyncio.sleep(0.6)
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
        assistant, lesson_done, _unclear = session.read_along.after_child_spoke(expected)
        if lesson_done and not assistant:
            await session.send_json({"type": "lesson_complete"})
            await session.send_status("listening", "课文读完了，点句子可重读")
            return
        if assistant:
            await _speak_teacher_line(
                session,
                assistant,
                user_echo_for_history="(Listen-only advance)",
            )
    finally:
        session.listen_only_busy = False


async def _kickoff_read_along(session: CallSession) -> None:
    material = (session.reading_material or "").strip()
    session.read_along.reset(material)
    opening = session.read_along.opening_line()
    await _speak_teacher_line(
        session, opening, user_echo_for_history=prog_hint(material)
    )


def prog_hint(material: str) -> str:
    return f"(Read-along started. Material:\n{material})"


async def _reread_line(session: CallSession, line_index: int) -> None:
    if session.call_mode != "read_along" or not session.reading_material:
        return
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
        if not session.stt_enabled:
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
        session.clear_interrupt()
        session.child_spoken_buffer = ""
        session.history.append({"role": "user", "content": user_echo_for_history})
        session.history.append({"role": "assistant", "content": assistant})
        session.discard_mic_buffer()
        await _send_assistant_text(
            session, assistant, line_index=line_index
        )
        await session.send_status("speaking", "听老师念下一句…")
        await _play_teacher_tts(session, assistant, send_listen_status=False)
        if line_index is not None:
            await session.send_json(
                {"type": "reread_line", "line_index": line_index, "text": assistant}
            )
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
                asyncio.create_task(_reread_line(session, line_index))
                continue

            if msg_type == "end_call":
                session.call_started = False
                session.reading_material = None
                session.lesson_id = None
                session.read_along = ReadAlongState()
                session.history.clear()
                session.request_interrupt()
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
                session.reading_material = material or None
                session.call_mode = mode
                current_user = ws_user_from_cookies(dict(websocket.cookies))
                session.username = (
                    current_user["username"] if current_user else None
                )
                session.stt_enabled = stt_enabled_for_username(session.username)
                session.call_started = True
                session.history.clear()
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
                if (
                    session.call_started
                    and not session.stt_enabled
                    and session.call_mode == "read_along"
                ):
                    asyncio.create_task(_continue_listen_only(session))
                continue

            if msg_type == "read_along_advance":
                if session.call_started and session.call_mode == "read_along":
                    asyncio.create_task(_safe_advance_read_along(session))
                continue

            if msg_type == "utterance_end":
                if not session.call_started:
                    continue
                if not session.stt_enabled:
                    await session.send_status(
                        "listening", "只听模式，请跟老师一起读"
                    )
                    continue
                asyncio.create_task(_safe_run_turn(session, from_pcm=True))
                continue

            if msg_type == "ping":
                await session.send_json({"type": "pong"})
                continue

            if msg_type == "set_stt_active":
                if session.call_started:
                    session.stt_enabled = bool(data.get("enabled", False))
                    await session.send_json(
                        {"type": "stt_active", "enabled": session.stt_enabled}
                    )
                continue

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws_call error")
    finally:
        session.active = False
        session.request_interrupt()
        await call_registry.unregister(registry_id)
