"""TTS: 豆包(火山) / Piper(本地) / edge(备用)."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator

import asyncio

logger = logging.getLogger(__name__)

TTS_ENGINE = os.getenv("TTS_ENGINE", "piper").strip().lower()

TTS_VOICE = os.getenv("TTS_VOICE", "en-US-JennyNeural")
TTS_RATE = os.getenv("TTS_RATE", "+0%")
TTS_PITCH = os.getenv("TTS_PITCH", "+0Hz")

PIPER_VOICE_DEFAULT = os.getenv("PIPER_VOICE_DEFAULT", "elsa")

# User speed multiplier: 1.0 = default, >1 faster, <1 slower
TTS_SPEED_MIN = 0.7
TTS_SPEED_MAX = 1.4


def clamp_tts_speed(speed: float) -> float:
    return max(TTS_SPEED_MIN, min(TTS_SPEED_MAX, float(speed)))


def _adjust_edge_rate(rate: str | None, speed: float) -> str:
    import re

    base = (rate or TTS_RATE or "+0%").strip()
    m = re.fullmatch(r"([+-])(\d+)%", base)
    if m:
        sign, num = m.groups()
        pct = int(num) if sign == "+" else -int(num)
    else:
        pct = 0
    delta = int(round((speed - 1.0) * 100))
    new_pct = max(-50, min(50, pct + delta))
    return f"{new_pct:+d}%"


def _piper_length_scale_for_speed(speed: float) -> float | None:
    """Return length_scale override for Piper when speed != 1 (higher scale = slower)."""
    if abs(speed - 1.0) < 0.02:
        return None
    base = float(os.getenv("PIPER_LENGTH_SCALE", "1.0"))
    return base / clamp_tts_speed(speed)

# Slot names (elsa / ultra) → Microsoft neural voices when TTS_ENGINE=edge
EDGE_VOICE_BY_SLOT: dict[str, str] = {
    # Cheerful / conversational (比 Jenny 更活泼；嫌尖可改 AriaNeural / AvaNeural)
    "elsa": os.getenv("ELSA_EDGE_VOICE", "en-US-EmmaMultilingualNeural"),
    "ultra": os.getenv("ULTRA_EDGE_VOICE", "en-US-GuyNeural"),
}


def _program_backend(program) -> str:
    if program is None:
        return TTS_ENGINE
    backend = (getattr(program, "tts_backend", "") or "").strip().lower()
    return backend or TTS_ENGINE


def _resolve_piper_voice(voice: str | None) -> str:
    v = (voice or "").strip()
    if not v or v.endswith("Neural") or "zh_female" in v or "zh_male" in v:
        return PIPER_VOICE_DEFAULT
    return v


async def text_to_mp3_bytes(
    text: str,
    voice: str | None = None,
    *,
    rate: str | None = None,
    pitch: str | None = None,
    program=None,
    speed: float = 1.0,
) -> bytes:
    if not text.strip():
        return b""

    backend = _program_backend(program)

    if backend == "doubao":
        from services.tts_doubao import doubao_configured, synthesize_mp3_bytes as doubao_mp3

        if doubao_configured():
            voice_id = (voice or "").strip()
            if program and getattr(program, "id", "") == "elsa_snow":
                voice_id = os.getenv("ELSA_DOUBAO_VOICE", voice_id) or voice_id
            return await doubao_mp3(text, voice_id, rate=rate)
        logger.warning("豆包 TTS 未配置，艾莎回退 Piper")

    spd = clamp_tts_speed(speed)
    if backend == "edge" or (backend == "doubao" and not _doubao_ok()):
        eff_rate = _adjust_edge_rate(rate, spd)
        return await _edge_mp3(text, voice, rate=eff_rate, pitch=pitch)

    from services.tts_piper import synthesize_wav_bytes

    name = _resolve_piper_voice(voice)
    length_scale = _piper_length_scale_for_speed(spd)
    return await asyncio.to_thread(
        synthesize_wav_bytes, text, name, length_scale=length_scale
    )


def _doubao_ok() -> bool:
    from services.tts_doubao import doubao_configured

    return doubao_configured()


async def _edge_mp3(
    text: str,
    voice: str | None,
    *,
    rate: str | None,
    pitch: str | None,
) -> bytes:
    import edge_tts
    import io

    v = (voice or "").strip() or TTS_VOICE
    if v in EDGE_VOICE_BY_SLOT:
        v = EDGE_VOICE_BY_SLOT[v]
    elif not v.endswith("Neural"):
        v = TTS_VOICE
    r = (rate or "").strip() or TTS_RATE
    p = (pitch or "").strip() or TTS_PITCH
    communicate = edge_tts.Communicate(text.strip(), v, rate=r, pitch=p)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            buf.write(chunk["data"])
    return buf.getvalue()


def output_mime_type(program=None) -> str:
    backend = _program_backend(program)
    if backend == "doubao" and _doubao_ok():
        return "audio/mpeg"
    if backend == "edge":
        return "audio/mpeg"
    return "audio/wav"


async def stream_mp3(
    text: str,
    voice: str | None = None,
    *,
    rate: str | None = None,
    pitch: str | None = None,
    program=None,
) -> AsyncIterator[bytes]:
    data = await text_to_mp3_bytes(
        text, voice=voice, rate=rate, pitch=pitch, program=program
    )
    if data:
        yield data


async def text_to_mp3_for_program(text: str, program) -> bytes:
    return await text_to_mp3_bytes(
        text,
        voice=program.tts_voice,
        rate=program.tts_rate or None,
        pitch=program.tts_pitch or None,
        program=program,
    )
