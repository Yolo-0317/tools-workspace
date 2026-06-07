"""Offline TTS via Piper (ONNX models under english-buddy/voices/piper/)."""

from __future__ import annotations

import io
import json
import os
import wave
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from piper import PiperVoice
from piper.config import SynthesisConfig

ROOT = Path(__file__).resolve().parent.parent.parent
PIPER_ROOT = Path(os.getenv("PIPER_VOICES_DIR", str(ROOT / "voices" / "piper")))

PIPER_LENGTH_SCALE = float(os.getenv("PIPER_LENGTH_SCALE", "1.05"))


def piper_voice_dir(name: str) -> Path:
    return PIPER_ROOT / name.strip()


def voice_ready(name: str) -> bool:
    d = piper_voice_dir(name)
    return any(d.glob("*.onnx"))


def list_ready_voices() -> list[str]:
    if not PIPER_ROOT.is_dir():
        return []
    out: list[str] = []
    for child in sorted(PIPER_ROOT.iterdir()):
        if child.is_dir() and any(child.glob("*.onnx")):
            out.append(child.name)
    return out


def _slot_synthesis_overrides(name: str) -> dict[str, Any]:
    path = piper_voice_dir(name) / "synthesis.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=4)
def _load_voice(name: str) -> PiperVoice:
    d = piper_voice_dir(name)
    onnx_files = sorted(d.glob("*.onnx"))
    if not onnx_files:
        raise FileNotFoundError(
            f"Piper voice '{name}' not found under {d}. "
            f"Run: ./scripts/download_piper_voices.sh"
        )
    model = onnx_files[0]
    config = model.with_suffix(".onnx.json")
    if not config.is_file():
        raise FileNotFoundError(f"Missing Piper config: {config}")
    return PiperVoice.load(model, config)


def _build_synthesis_config(voice: PiperVoice, slot: str) -> SynthesisConfig:
    overrides = _slot_synthesis_overrides(slot)
    try:
        base_len = float(getattr(voice.config, "length_scale", 1.0) or 1.0)
    except (TypeError, ValueError, AttributeError):
        base_len = 1.0
    try:
        base_noise = float(getattr(voice.config, "noise_scale", 0.667) or 0.667)
    except (TypeError, ValueError, AttributeError):
        base_noise = 0.667
    try:
        base_noise_w = float(getattr(voice.config, "noise_w_scale", 0.8) or 0.8)
    except (TypeError, ValueError, AttributeError):
        base_noise_w = 0.8

    length_scale = float(overrides.get("length_scale", base_len * PIPER_LENGTH_SCALE))
    noise_scale = float(overrides.get("noise_scale", base_noise))
    noise_w_scale = float(overrides.get("noise_w_scale", base_noise_w))
    volume = float(overrides.get("volume", 1.0))

    return SynthesisConfig(
        length_scale=length_scale,
        noise_scale=noise_scale,
        noise_w_scale=noise_w_scale,
        volume=volume,
    )


def _pitch_shift_wav(wav_bytes: bytes, ratio: float) -> bytes:
    """Raise/lower pitch without changing duration. ratio > 1 = higher (younger)."""
    if ratio <= 0 or abs(ratio - 1.0) < 0.02:
        return wav_bytes
    import numpy as np

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    if sample_width != 2 or n_frames < 2:
        return wav_bytes

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    src_len = len(audio)
    comp_len = max(2, int(src_len / ratio))
    x_src = np.arange(src_len, dtype=np.float64)
    x_comp = np.linspace(0, src_len - 1, comp_len)
    compressed = np.interp(x_comp, x_src, audio)
    shifted = np.interp(x_src, np.linspace(0, comp_len - 1, comp_len), compressed)
    pcm = np.clip(shifted, -32768, 32767).astype(np.int16)

    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    return out.getvalue()


def synthesize_wav_bytes(
    text: str,
    voice_name: str,
    *,
    length_scale: Optional[float] = None,
) -> bytes:
    if not text.strip():
        return b""
    voice = _load_voice(voice_name)
    overrides = _slot_synthesis_overrides(voice_name)
    syn = _build_synthesis_config(voice, voice_name)
    if length_scale is not None:
        syn = SynthesisConfig(
            length_scale=length_scale,
            noise_scale=syn.noise_scale,
            noise_w_scale=syn.noise_w_scale,
            volume=syn.volume,
        )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        voice.synthesize_wav(text.strip(), wf, syn_config=syn)
    wav = buf.getvalue()
    pitch = float(overrides.get("pitch_shift", 1.0) or 1.0)
    if pitch != 1.0:
        wav = _pitch_shift_wav(wav, pitch)
    return wav
