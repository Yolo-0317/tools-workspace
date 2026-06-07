"""Which logged-in users may use microphone STT during read-along."""

from __future__ import annotations

import os
from typing import Optional


def stt_allowed_usernames() -> frozenset[str]:
    raw = os.getenv("ENGLISH_BUDDY_STT_USERS", "").strip()
    if not raw:
        return frozenset()
    return frozenset(
        name.strip().lower() for part in raw.split(",") if (name := part.strip())
    )


def stt_enabled_for_username(username: Optional[str]) -> bool:
    """Empty ENGLISH_BUDDY_STT_USERS → all users may use STT."""
    allowed = stt_allowed_usernames()
    if not allowed:
        return True
    if not username:
        return False
    return username.strip().lower() in allowed


def stt_users_public() -> list[str]:
    return sorted(stt_allowed_usernames())
