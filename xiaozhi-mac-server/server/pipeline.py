"""ASR -> LLM -> TTS pipeline for local demo."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import edge_tts
import numpy as np
from faster_whisper import WhisperModel

from server.config import settings
from server.llm import chat_with_llm, record_chat_turn
from server.opus_codec import OpusCodec

log = logging.getLogger(__name__)

_whisper: WhisperModel | None = None
_codec = OpusCodec(
    uplink_rate=settings.uplink_rate,
    downlink_rate=settings.downlink_rate,
    frame_ms=settings.frame_ms,
)


def _get_whisper() -> WhisperModel:
    global _whisper
    if _whisper is None:
        log.info(
            "Loading faster-whisper model=%s profile=%s device=%s",
            settings.whisper_model,
            settings.whisper_profile,
            settings.whisper_device,
        )
        _whisper = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type="int8",
            cpu_threads=settings.whisper_cpu_threads,
        )
    return _whisper


def preload_whisper() -> None:
    """Load ASR model at startup so the first voice turn is not blocked."""
    import time

    t0 = time.perf_counter()
    _get_whisper()
    # Short warmup pass; real audio still decodes on the hot model.
    silence = np.zeros(settings.uplink_rate // 2, dtype=np.float32)
    _transcribe_float_audio(silence)
    log.info("Whisper preloaded in %.2fs", time.perf_counter() - t0)


def transcribe_opus_packets(packets: list[bytes]) -> str:
    if settings.asr_backend == "tencent":
        try:
            from server.tencent_asr import transcribe_opus_packets as tencent_transcribe

            text = tencent_transcribe(packets)
            if text or not settings.asr_fallback_local:
                return _fix_asr_text(text)
        except Exception as exc:
            log.warning("Tencent ASR unavailable, fallback=%s: %s", settings.asr_fallback_local, exc)
            if not settings.asr_fallback_local:
                return ""
    return _transcribe_opus_packets_local(packets)


def _transcribe_opus_packets_local(packets: list[bytes]) -> str:
    pcm = _codec.decode_packets(packets, settings.uplink_rate)
    if pcm.size == 0:
        return ""
    audio = pcm.astype(np.float32) / 32768.0
    return _transcribe_float_audio(audio)


def transcribe_audio_bytes(data: bytes) -> str:
    """Transcribe browser MediaRecorder payload (webm/wav/mp4)."""
    if settings.asr_backend == "tencent":
        try:
            from server.tencent_asr import transcribe_audio_bytes as tencent_transcribe

            text = tencent_transcribe(data)
            if text or not settings.asr_fallback_local:
                return _fix_asr_text(text)
        except Exception as exc:
            log.warning("Tencent ASR unavailable, fallback=%s: %s", settings.asr_fallback_local, exc)
            if not settings.asr_fallback_local:
                return ""
    return _transcribe_audio_bytes_local(data)


def _fix_asr_text(text: str) -> str:
    from server.voice_text import fix_asr_text

    return fix_asr_text(text)


def _transcribe_audio_bytes_local(data: bytes) -> str:
    if not data:
        return ""
    import subprocess

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(settings.uplink_rate),
        "pipe:1",
    ]
    proc = subprocess.run(
        cmd,
        input=data,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0 or not proc.stdout:
        log.warning("ffmpeg decode failed: %s", proc.stderr.decode("utf-8", errors="replace")[:200])
        return ""
    pcm = np.frombuffer(proc.stdout, dtype=np.int16)
    if pcm.size == 0:
        return ""
    audio = pcm.astype(np.float32) / 32768.0
    return _transcribe_float_audio(audio)


def _transcribe_float_audio(audio: np.ndarray) -> str:
    import time

    model = _get_whisper()
    t0 = time.perf_counter()
    segments, _ = model.transcribe(
        audio,
        language="zh",
        beam_size=settings.whisper_beam_size,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        condition_on_previous_text=False,
        initial_prompt="想听儿童故事。想听冰雪奇缘。播放牛津树。哈利波特。",
    )
    from server.voice_text import fix_asr_text

    text = "".join(seg.text for seg in segments).strip()
    result = fix_asr_text(text)
    elapsed = time.perf_counter() - t0
    if elapsed >= 0.5:
        log.info("ASR %.2fs audio=%.1fs text=%r", elapsed, len(audio) / settings.uplink_rate, result)
    return result


async def synthesize_mp3_bytes(text: str) -> bytes:
    if not text:
        return b""
    mp3_buf = bytearray()
    communicate = edge_tts.Communicate(text, settings.tts_voice)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_buf.extend(chunk["data"])
    return bytes(mp3_buf)


async def synthesize_opus_packets(text: str) -> list[bytes]:
    mp3_buf = await synthesize_mp3_bytes(text)
    if not mp3_buf:
        return []
    pcm = await asyncio.to_thread(
        OpusCodec.mp3_to_pcm_int16, mp3_buf, settings.downlink_rate
    )
    return await asyncio.to_thread(
        _codec.encode_pcm, pcm, settings.downlink_rate
    )


async def run_turn(
    opus_uplink: Iterable[bytes],
    history: list[dict[str, str]],
) -> tuple[str, str, list[bytes]]:
    packets = list(opus_uplink)
    user_text = await asyncio.to_thread(transcribe_opus_packets, packets)
    if not user_text:
        user_text = "（没听清，请再说一次）"
    reply = await chat_with_llm(user_text, history)
    record_chat_turn(history, user_text, reply)
    downlink = await synthesize_opus_packets(reply)
    return user_text, reply, downlink
