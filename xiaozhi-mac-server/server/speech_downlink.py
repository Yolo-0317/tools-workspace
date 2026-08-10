"""TTS + Opus downlink with device speaking-state timing."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable
from typing import Any, Awaitable, Callable

from server.config import settings
from server.pipeline import synthesize_opus_packets
from server.protocol import llm_message, stt_message, tts_message
from server.voice_text import sanitize_for_speech

log = logging.getLogger(__name__)

# AtomS3R schedules kDeviceStateSpeaking asynchronously after tts.start;
# binary packets that arrive too early are dropped by firmware.
# Pyramid + CAM needs a bit more slack than stock AtomS3R.
SPEAKING_STATE_DELAY_S = 0.40

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendBinary = Callable[[bytes], Awaitable[None]]


def _should_stop(should_stop: Callable[[], bool] | None) -> bool:
    return bool(should_stop and should_stop())


async def send_opus_packets_paced(
    send_binary: SendBinary,
    packets: Iterable[bytes],
    *,
    frame_ms: int | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> int:
    """Send Opus frames at real-time rate so the device decode queue is not flooded."""
    ms = frame_ms or settings.frame_ms
    interval = ms / 1000.0
    loop = asyncio.get_running_loop()
    next_at = loop.time()
    count = 0
    for packet in packets:
        if _should_stop(should_stop):
            break
        now = loop.time()
        if now < next_at:
            await asyncio.sleep(next_at - now)
            now = loop.time()
        await send_binary(packet)
        count += 1
        if now > next_at + interval:
            next_at = now + interval
        else:
            next_at += interval
    return count


async def send_opus_stream_paced(
    send_binary: SendBinary,
    packets: AsyncIterator[bytes],
    *,
    send_json: SendJson | None = None,
    session_id: str | None = None,
    frame_ms: int | None = None,
    should_stop: Callable[[], bool] | None = None,
    listen_every_packets: int = 0,
    listen_window_s: float = 0.0,
) -> int:
    ms = frame_ms or settings.frame_ms
    interval = ms / 1000.0
    loop = asyncio.get_running_loop()
    next_at = loop.time()
    count = 0
    async for packet in packets:
        if _should_stop(should_stop):
            break
        now = loop.time()
        if now < next_at:
            await asyncio.sleep(next_at - now)
            now = loop.time()
        await send_binary(packet)
        count += 1
        if now > next_at + interval:
            next_at = now + interval
        else:
            next_at += interval

        if (
            listen_every_packets > 0
            and listen_window_s > 0
            and send_json is not None
            and session_id
            and count % listen_every_packets == 0
        ):
            # Legacy barge-in: pause playback briefly so the device can listen.
            # Disabled by default (STREAM_LISTEN_EVERY_S=0) because tts.stop cuts audio.
            await send_json(tts_message(session_id, "stop"))
            log.debug("Stream listen window (%d packets)", count)
            await asyncio.sleep(listen_window_s)
            if _should_stop(should_stop):
                break
            await send_json(tts_message(session_id, "start"))
            await asyncio.sleep(SPEAKING_STATE_DELAY_S)
    return count


async def emit_speech(
    *,
    send_json: SendJson,
    send_binary: SendBinary,
    session_id: str,
    reply: str,
    user_text: str | None = None,
    emotion: str = "happy",
    include_stt: bool = True,
) -> None:
    reply = sanitize_for_speech(reply)
    if include_stt and user_text is not None:
        await send_json(stt_message(session_id, user_text))
    await send_json(llm_message(session_id, reply, emotion))
    await send_json(tts_message(session_id, "start"))
    await asyncio.sleep(SPEAKING_STATE_DELAY_S)
    await send_json(tts_message(session_id, "sentence_start", reply))
    packets = await synthesize_opus_packets(reply)
    sent = await send_opus_packets_paced(send_binary, packets)
    await send_json(tts_message(session_id, "stop"))
    log.info("Speech downlink done (%d packets): %s", sent, reply[:60])


async def begin_speaking_session(
    *,
    send_json: SendJson,
    send_binary: SendBinary,
    session_id: str,
    ack: str,
    user_text: str | None = None,
    emotion: str = "happy",
    include_stt: bool = True,
) -> None:
    """Enter speaking state and play a short ack; caller sends more binary then tts.stop."""
    ack = sanitize_for_speech(ack)
    if include_stt and user_text is not None:
        await send_json(stt_message(session_id, user_text))
    await send_json(llm_message(session_id, ack, emotion))
    await send_json(tts_message(session_id, "start"))
    await asyncio.sleep(SPEAKING_STATE_DELAY_S)
    await send_json(tts_message(session_id, "sentence_start", ack))
    await send_opus_packets_paced(send_binary, await synthesize_opus_packets(ack))


async def end_speaking_session(*, send_json: SendJson, session_id: str) -> None:
    await send_json(tts_message(session_id, "stop"))
