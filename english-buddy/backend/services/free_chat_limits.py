"""Concurrent free-chat session cap (default 2)."""

from __future__ import annotations

import os

DEFAULT_MAX_FREE_CHAT_SESSIONS = 2


def max_free_chat_sessions() -> int:
    raw = os.getenv("MAX_FREE_CHAT_SESSIONS", "").strip()
    if not raw:
        return DEFAULT_MAX_FREE_CHAT_SESSIONS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_FREE_CHAT_SESSIONS
