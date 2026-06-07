"""Per-program / per-character TTS profiles and speaker-aware segmentation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from teaching.programs import Program

_SPEAKER_PREFIX = re.compile(
    r"^(?:\*{0,2})?(Elsa|Ultra)(?:\*{0,2})?"
    r"(?:\s+here)?[!.,:\s\-]*",
    re.IGNORECASE,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class TtsProfile:
    voice: str
    rate: str
    pitch: str


@dataclass(frozen=True)
class TtsSegment:
    text: str
    profile: TtsProfile


def _cast_tts_profiles(prog: Program) -> dict[str, TtsProfile]:
    default = program_default_profile(prog)
    out: dict[str, TtsProfile] = {}
    for member in prog.cast:
        name = (member.get("name_en") or "").strip()
        if not name:
            continue
        voice = (member.get("tts_voice") or "").strip() or default.voice
        rate = (member.get("tts_rate") or "").strip() or default.rate
        pitch = (member.get("tts_pitch") or "").strip() or default.pitch
        out[name.lower()] = TtsProfile(voice=voice, rate=rate, pitch=pitch)
    return out


def program_default_profile(prog: Program) -> TtsProfile:
    from services.tts import TTS_PITCH, TTS_RATE, TTS_VOICE

    return TtsProfile(
        voice=(prog.tts_voice or "").strip() or TTS_VOICE,
        rate=(prog.tts_rate or "").strip() or TTS_RATE,
        pitch=(prog.tts_pitch or "").strip() or TTS_PITCH,
    )


def split_assistant_for_tts(text: str, prog: Program) -> list[TtsSegment]:
    """Split LLM reply by line/sentence and map Elsa/Judy (etc.) to cast voices."""
    raw = (text or "").strip()
    if not raw:
        return []

    default = program_default_profile(prog)
    speakers = _cast_tts_profiles(prog)
    if not speakers:
        return [TtsSegment(raw, default)]

    parts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts.extend(p for p in _SENTENCE_SPLIT.split(line) if p.strip())

    if not parts:
        parts = [raw]

    segments: list[TtsSegment] = []
    current = default

    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        m = _SPEAKER_PREFIX.match(chunk)
        if m:
            key = m.group(1).lower()
            current = speakers.get(key, default)
            chunk = chunk[m.end() :].strip()
            if not chunk:
                continue
        segments.append(TtsSegment(chunk, current))

    if not segments:
        return [TtsSegment(raw, default)]
    return segments
