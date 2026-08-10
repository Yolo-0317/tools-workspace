"""Decode browser / ffmpeg audio bytes to mono float32 PCM."""

from __future__ import annotations

import subprocess

import numpy as np

from server.config import settings


def decode_audio_bytes(data: bytes, sample_rate: int | None = None) -> np.ndarray:
    """Return mono float32 PCM in [-1, 1]. Empty array on failure."""
    if not data:
        return np.array([], dtype=np.float32)
    rate = sample_rate or settings.uplink_rate
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
        str(rate),
        "pipe:1",
    ]
    proc = subprocess.run(
        cmd,
        input=data,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0 or not proc.stdout:
        return np.array([], dtype=np.float32)
    pcm = np.frombuffer(proc.stdout, dtype=np.int16)
    if pcm.size == 0:
        return np.array([], dtype=np.float32)
    return pcm.astype(np.float32) / 32768.0
