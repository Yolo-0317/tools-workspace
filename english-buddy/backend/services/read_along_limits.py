"""Concurrent read-along session cap (aligned with Whisper workers by default)."""

from __future__ import annotations

import os

from services.stt import WHISPER_WORKERS


def max_read_along_sessions() -> int:
    raw = os.getenv("MAX_READ_ALONG_SESSIONS", "").strip()
    if not raw:
        return WHISPER_WORKERS
    try:
        return max(1, int(raw))
    except ValueError:
        return WHISPER_WORKERS
