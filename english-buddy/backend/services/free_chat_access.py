"""Which logged-in users may see and start free chat (LLM conversation)."""

from __future__ import annotations

import os
from typing import Optional


def free_chat_allowed_usernames() -> frozenset[str]:
    raw = os.getenv("ENGLISH_BUDDY_FREE_CHAT_USERS", "").strip()
    if not raw:
        return frozenset()
    return frozenset(
        name.strip().lower() for part in raw.split(",") if (name := part.strip())
    )


def free_chat_enabled_for_username(username: Optional[str]) -> bool:
    """Empty ENGLISH_BUDDY_FREE_CHAT_USERS → free chat off for everyone."""
    allowed = free_chat_allowed_usernames()
    if not allowed:
        return False
    if not username:
        return False
    return username.strip().lower() in allowed


def free_chat_users_public() -> list[str]:
    return sorted(free_chat_allowed_usernames())
