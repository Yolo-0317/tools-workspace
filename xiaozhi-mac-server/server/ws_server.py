"""WebSocket server implementing xiaozhi-esp32 protocol (v1 binary Opus)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiohttp import web
import websockets
from websockets.server import WebSocketServerProtocol

from server.config import settings
from server.device_registry import register, touch, unregister
from server.http_server import APP
from server.protocol import (
    dumps,
    new_session_id,
    server_hello,
    stt_message,
)
from server.streaming_uplink import OpusStreamingTurnSegmenter
from server.playback_memory import (
    PlaybackStore,
    find_next_episode_source,
    resolve_source_for_record,
)

log = logging.getLogger(__name__)


def _header(headers: dict[str, str], name: str) -> str:
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return ""


def _auth_ok(headers: dict[str, str]) -> bool:
    auth = _header(headers, "Authorization")
    expected = f"Bearer {settings.token}"
    if auth == expected:
        return True
    if auth == settings.token:
        return True
    return False


class DeviceSession:
    def __init__(
        self,
        ws: WebSocketServerProtocol,
        http_app: web.Application,
        *,
        device_id: str = "",
    ) -> None:
        self.ws = ws
        self.http_app = http_app
        self.device_id = device_id or "default"
        self.session_id = new_session_id()
        self.playback_memory = PlaybackStore(self.device_id)
        self.hello_done = False
        self.listening = False
        self.listen_mode = "manual"
        self.uplink: list[bytes] = []
        self.history: list[dict[str, str]] = []
        self._busy = False
        self._segmenter: OpusStreamingTurnSegmenter | None = None
        self._pending_turn: list[bytes] | None = None
        self._listen_holdoff_until: float = 0.0
        self._uplink_muted_until: float = 0.0
        self._last_turn_at: float = 0.0
        self._wake_nudge_task: asyncio.Task | None = None
        self.mcp_audio_already_spoken = False
        self.mcp_playback_started = False
        self.device_volume = settings.device_default_volume
        self._cancel_playback = asyncio.Event()
        self._playback_active = False
        self._playback_task: asyncio.Task | None = None
        self._ffmpeg_proc: asyncio.subprocess.Process | None = None

    def should_stop_playback(self) -> bool:
        return self._cancel_playback.is_set()

    async def stop_playback(self, *, reason: str = "user") -> None:
        if not self._cancel_playback.is_set():
            log.info("Stop playback (%s)", reason)
        self._cancel_playback.set()
        proc = self._ffmpeg_proc
        if proc is not None and proc.returncode is None:
            proc.terminate()
        from server.protocol import tts_message

        await self.send_json(tts_message(self.session_id, "stop"))
        if self.playback_memory.current is not None:
            self.playback_memory.save()

    async def _wait_playback_stopped(self, timeout_s: float = 2.5) -> None:
        if not self._playback_active:
            return
        try:
            await asyncio.wait_for(
                self._wait_until(lambda: not self._playback_active),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            log.warning("Timed out waiting for playback to stop")

    async def _wait_until(self, predicate) -> None:
        while not predicate():
            await asyncio.sleep(0.05)

    def _reset_playback_cancel(self) -> None:
        self._cancel_playback.clear()

    def _attach_ffmpeg_proc(self, proc: asyncio.subprocess.Process) -> None:
        self._ffmpeg_proc = proc

    async def play_quark_from_mcp(
        self,
        query: str,
        *,
        user_text: str = "",
        media_hint: str = "story_audio",
        external: bool = False,
        mode: str = "search",
    ) -> dict:
        from server.intent_router import RoutedIntent
        from server.quark_client import QuarkClient
        from server.quark_playback import play_quark_content, play_quark_source

        touch(self.session_id)
        play_mode = (mode or "search").strip().lower()

        if external and (self._busy or self._playback_active):
            return {"success": False, "error": "device busy"}

        if self._playback_task and not self._playback_task.done():
            await self.stop_playback(reason="replace")
            await self._wait_playback_stopped()

        client = QuarkClient.from_env()
        if client is None:
            return {"success": False, "error": "Quark not configured"}

        source = None
        start_offset_s = 0.0
        search_key = (query or "").strip()
        catalog_key = None
        reply = ""

        mem = self.playback_memory
        if play_mode == "resume":
            target = mem.resume_target()
            if target is None:
                return {"success": False, "error": "没有可续播的内容，可以说想听什么。"}
            source = await asyncio.to_thread(
                resolve_source_for_record, client, target, self.http_app
            )
            if source is None:
                return {"success": False, "error": f"找不到上次的内容：{target.short_title()}"}
            search_key = target.query
            media_hint = target.media_hint
            catalog_key = target.catalog_key
            start_offset_s = target.position_s()
            reply = ""
        elif play_mode == "replay":
            target = mem.last_played()
            if target is None:
                return {"success": False, "error": "还没有播放记录。"}
            source = await asyncio.to_thread(
                resolve_source_for_record, client, target, self.http_app
            )
            if source is None:
                return {"success": False, "error": f"找不到：{target.short_title()}"}
            search_key = target.query
            media_hint = target.media_hint
            catalog_key = target.catalog_key
            start_offset_s = 0.0
            reply = ""
        elif play_mode == "next":
            target = mem.last_played()
            if target is None:
                return {"success": False, "error": "还不知道上一集是什么，先说想听哪一部。"}
            source = await asyncio.to_thread(find_next_episode_source, client, target)
            if source is None:
                return {
                    "success": False,
                    "error": f"没找到《{target.short_title()}》的下一集。",
                }
            search_key = target.query
            media_hint = target.media_hint
            catalog_key = target.catalog_key
            reply = ""
        else:
            if not search_key:
                return {"success": False, "error": "query is required"}

        routed = RoutedIntent(
            action="play",
            reply=reply,
            search_query=search_key,
            media_hint=media_hint,
        )
        self.mcp_audio_already_spoken = False
        self._reset_playback_cancel()
        self.mcp_playback_started = True

        async def _run_playback() -> None:
            self._playback_active = True
            try:
                if source is not None:
                    played = await play_quark_source(
                        source,
                        user_text=user_text or search_key,
                        query=search_key,
                        media_hint=media_hint,
                        http_app=self.http_app,
                        send_json=self.send_json,
                        send_binary=self.send_binary,
                        session_id=self.session_id,
                        should_stop=self.should_stop_playback,
                        on_process=self._attach_ffmpeg_proc,
                        playback_memory=mem,
                        start_offset_s=start_offset_s,
                        catalog_key=catalog_key,
                        reply=reply,
                    )
                else:
                    played = await play_quark_content(
                        routed,
                        user_text=user_text or search_key,
                        http_app=self.http_app,
                        send_json=self.send_json,
                        send_binary=self.send_binary,
                        session_id=self.session_id,
                        should_stop=self.should_stop_playback,
                        on_process=self._attach_ffmpeg_proc,
                        playback_memory=mem,
                    )
                if played and not self.should_stop_playback():
                    self.mcp_audio_already_spoken = True
            except Exception:
                log.exception("Background quark playback failed")
            finally:
                self._playback_active = False
                self._ffmpeg_proc = None
                self.mcp_playback_started = False

        self._playback_task = asyncio.create_task(_run_playback())
        return {
            "success": True,
            "started": True,
            "query": search_key,
            "media_hint": media_hint,
            "mode": play_mode,
            "session_id": self.session_id,
        }

    async def send_json(self, msg: dict[str, Any]) -> None:
        await self.ws.send(dumps(msg))

    async def send_binary(self, packet: bytes) -> None:
        await self.ws.send(packet)

    def _uses_streaming_segmenter(self) -> bool:
        return settings.streaming_asr and self.listen_mode in {"auto", "realtime"}

    async def handle_text(self, raw: str) -> None:
        data = json.loads(raw)
        msg_type = data.get("type")

        if msg_type == "hello":
            await self._on_device_hello(data)
            return

        if not self.hello_done:
            log.warning("Ignoring message before hello handshake: %s", msg_type)
            return

        if msg_type == "listen":
            await self._on_listen(data)
            return

        if msg_type == "abort":
            reason = str(data.get("reason") or "")
            log.info("Device abort speaking reason=%s", reason or "unknown")
            await self.stop_playback(reason=reason or "abort")
            return

        log.debug("Unhandled device message: %s", data)

    async def handle_binary(self, packet: bytes) -> None:
        if not self.listening or not packet:
            return
        loop = asyncio.get_running_loop()
        if loop.time() < self._uplink_muted_until:
            return
        if self._segmenter is not None:
            for turn_packets in self._segmenter.feed(packet):
                self._schedule_turn(turn_packets)
            return
        self.uplink.append(packet)

    async def _on_device_hello(self, data: dict[str, Any]) -> None:
        transport = data.get("transport")
        if transport != "websocket":
            log.error("Unsupported transport: %s", transport)
            await self.ws.close(code=1008, reason="unsupported transport")
            return
        self.hello_done = True
        await self.send_json(
            server_hello(
                self.session_id,
                sample_rate=settings.downlink_rate,
                frame_ms=settings.frame_ms,
            )
        )
        log.info("Handshake OK session=%s device=%s", self.session_id, _header(dict(self.ws.request.headers), "Device-Id"))
        asyncio.create_task(self._bootstrap_device())

    async def _bootstrap_device(self) -> None:
        try:
            from server.device_control import ensure_device_volume

            await ensure_device_volume(self)
        except Exception:
            log.exception("Device bootstrap failed")

    async def _on_listen(self, data: dict[str, Any]) -> None:
        state = data.get("state")
        if state == "start":
            self.listening = True
            self.uplink = []
            self.listen_mode = str(data.get("mode") or "manual")
            if self._uses_streaming_segmenter():
                self._segmenter = OpusStreamingTurnSegmenter()
                loop = asyncio.get_running_loop()
                remaining_ms = int((self._listen_holdoff_until - loop.time()) * 1000)
                if remaining_ms > 0:
                    self._segmenter.begin_holdoff(remaining_ms)
                log.info(
                    "Listen start mode=%s streaming=on silence=%sms",
                    self.listen_mode,
                    settings.stream_silence_ms,
                )
            else:
                self._segmenter = None
                log.info("Listen start mode=%s streaming=off", self.listen_mode)
            return

        if state == "stop":
            self.listening = False
            text_override = data.get("text")
            if text_override:
                self._segmenter = None
                self.uplink = []
                asyncio.create_task(self._process_text(str(text_override)))
                return

            if self._segmenter is not None:
                for turn_packets in self._segmenter.flush():
                    self._schedule_turn(turn_packets)
                self._segmenter = None
                return

            packets = self.uplink
            self.uplink = []
            if not packets:
                log.info("Listen stop with empty uplink")
                return
            self._schedule_turn(packets)
            return

        if state == "detect":
            wake_text = str(data.get("text") or "")
            log.info("Wake word detect: %s", wake_text)
            if self._playback_active:
                await self.stop_playback(reason="wake")
            loop = asyncio.get_running_loop()
            holdoff_s = settings.stream_wake_holdoff_ms / 1000.0
            self._uplink_muted_until = loop.time() + holdoff_s
            self._listen_holdoff_until = self._uplink_muted_until
            if self._wake_nudge_task and not self._wake_nudge_task.done():
                self._wake_nudge_task.cancel()
            asyncio.create_task(self._ack_wake_word(wake_text))

    async def _ack_wake_word(self, wake_text: str) -> None:
        if self._playback_active:
            await self._wait_playback_stopped()
        if self._busy:
            log.info("Skip wake ack while busy (%s)", wake_text)
            return
        self._busy = True
        try:
            from server.device_control import set_device_volume
            from server.speech_downlink import emit_speech

            # Re-assert volume right before TTS; handshake MCP can race codec open.
            await set_device_volume(self, self.device_volume)
            await emit_speech(
                send_json=self.send_json,
                send_binary=self.send_binary,
                session_id=self.session_id,
                reply="我在呢，请说。",
                include_stt=False,
                emotion="happy",
            )
        except Exception:
            log.exception("Wake word ack failed")
        finally:
            self._busy = False
            loop = asyncio.get_running_loop()
            self._listen_holdoff_until = loop.time() + (
                settings.stream_calibration_holdoff_ms / 1000.0
            )
            self._uplink_muted_until = max(
                self._uplink_muted_until,
                self._listen_holdoff_until,
            )
            if self._segmenter is not None:
                self._segmenter.begin_holdoff(settings.stream_calibration_holdoff_ms)
            self._drain_pending_turn()
            self._wake_nudge_task = asyncio.create_task(self._nudge_if_idle_after_wake())

    async def _nudge_if_idle_after_wake(self) -> None:
        await asyncio.sleep(12)
        loop = asyncio.get_running_loop()
        if loop.time() - self._last_turn_at < 10:
            return
        if self._busy or self._playback_active or not self.listening:
            return
        log.info("Wake idle nudge: no user speech detected")
        self._busy = True
        try:
            from server.speech_downlink import emit_speech

            await emit_speech(
                send_json=self.send_json,
                send_binary=self.send_binary,
                session_id=self.session_id,
                reply="我没听到，请再说一次。",
                include_stt=False,
                emotion="neutral",
            )
        except Exception:
            log.exception("Wake idle nudge failed")
        finally:
            self._busy = False
            self._drain_pending_turn()

    def _mark_turn_handled(self) -> None:
        self._last_turn_at = asyncio.get_running_loop().time()
        if self._wake_nudge_task and not self._wake_nudge_task.done():
            self._wake_nudge_task.cancel()

    def _schedule_turn(self, packets: list[bytes]) -> None:
        if not packets:
            return
        asyncio.create_task(self._process_turn(packets))

    def _drain_pending_turn(self) -> None:
        pending = self._pending_turn
        if not pending:
            return
        self._pending_turn = None
        if self._busy:
            self._pending_turn = pending
            return
        self._schedule_turn(pending)

    async def _process_text(self, user_text: str) -> None:
        if self._playback_active and not settings.playback_wake_interrupt:
            await self.stop_playback(reason="barge-in")
            await self._wait_playback_stopped()
        elif self._playback_active:
            log.info("Ignore text during playback (use wake word to interrupt)")
            return
        if self._busy:
            log.info("Session busy, ignore text turn")
            return
        self._busy = True
        try:
            from server.user_turn import handle_user_turn

            self._mark_turn_handled()
            await handle_user_turn(
                user_text,
                history=self.history,
                http_app=self.http_app,
                send_json=self.send_json,
                send_binary=self.send_binary,
                session_id=self.session_id,
                session=self,
            )
        except Exception:
            log.exception("Text turn failed")
        finally:
            self._busy = False
            self._drain_pending_turn()

    async def _process_turn(self, packets: list[bytes]) -> None:
        if self._playback_active and not settings.playback_wake_interrupt:
            await self.stop_playback(reason="barge-in")
            await self._wait_playback_stopped()
        elif self._playback_active:
            log.info("Ignore uplink during playback (use wake word to interrupt)")
            return
        if self._busy:
            log.info("Session busy, queue voice turn (%d packets)", len(packets))
            self._pending_turn = packets
            return
        self._busy = True
        try:
            from server.pipeline import transcribe_opus_packets
            from server.user_turn import handle_user_turn

            user_text = await asyncio.to_thread(transcribe_opus_packets, packets)
            if not user_text:
                user_text = "（没听清，请再说一次）"
            from server.voice_text import normalize_transcript

            user_text = normalize_transcript(user_text) or user_text
            log.info("User: %s", user_text)
            touch(self.session_id)
            self._mark_turn_handled()

            await handle_user_turn(
                user_text,
                history=self.history,
                http_app=self.http_app,
                send_json=self.send_json,
                send_binary=self.send_binary,
                session_id=self.session_id,
                session=self,
            )
        except Exception:
            log.exception("Turn failed")
            await self.send_json(
                stt_message(self.session_id, "（处理失败，请重试）")
            )
        finally:
            self._busy = False
            self._drain_pending_turn()


async def ws_handler(ws: WebSocketServerProtocol) -> None:
    headers = {k: v for k, v in ws.request.headers.items()}
    if not _auth_ok(headers):
        log.warning("Unauthorized connection from %s", ws.remote_address)
        await ws.close(code=1008, reason="unauthorized")
        return

    session = DeviceSession(
        ws,
        APP,
        device_id=_header(headers, "Device-Id") or _header(headers, "Client-Id") or "",
    )
    register(session)
    log.info(
        "Client connected from %s device=%s client=%s",
        ws.remote_address,
        _header(headers, "Device-Id") or "?",
        _header(headers, "Client-Id") or "?",
    )
    try:
        async for message in ws:
            if isinstance(message, bytes):
                await session.handle_binary(message)
            else:
                await session.handle_text(message)
    except websockets.ConnectionClosed:
        log.info("Client disconnected session=%s", session.session_id)
    finally:
        unregister(session.session_id)


async def run_ws_server() -> None:
    async with websockets.serve(
        ws_handler,
        settings.host,
        settings.ws_port,
        ping_interval=20,
        ping_timeout=20,
        max_size=8 * 1024 * 1024,
    ):
        log.info("WebSocket listening on ws://%s:%s", settings.host, settings.ws_port)
        await asyncio.Future()
