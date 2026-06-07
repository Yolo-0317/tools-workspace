"""English Buddy auth configuration. See docs/AUTH.md."""

from __future__ import annotations

import os

SESSION_COOKIE = "eb_session"


def require_auth() -> bool:
    return os.getenv("ENGLISH_BUDDY_REQUIRE_AUTH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def session_ttl_hours() -> int:
    try:
        return max(1, int(os.getenv("ENGLISH_BUDDY_SESSION_TTL_HOURS", "720")))
    except ValueError:
        return 720


def cookie_path() -> str:
    raw = os.getenv("ENGLISH_BUDDY_COOKIE_PATH", "/english/").strip() or "/"
    if not raw.startswith("/"):
        raw = f"/{raw}"
    if raw != "/" and not raw.endswith("/"):
        raw = f"{raw}/"
    return raw


def cookie_secure() -> bool:
    return os.getenv("ENGLISH_BUDDY_COOKIE_SECURE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def cookie_samesite() -> str:
    return os.getenv("ENGLISH_BUDDY_COOKIE_SAMESITE", "lax").strip().lower() or "lax"


def bootstrap_users() -> list[tuple[str, str]]:
    """Parse ENGLISH_BUDDY_USERS=user:pass,user2:pass2 from env."""
    out: list[tuple[str, str]] = []
    raw = os.getenv("ENGLISH_BUDDY_USERS", "").strip()
    if raw:
        for part in raw.split(","):
            piece = part.strip()
            if not piece or ":" not in piece:
                continue
            name, password = piece.split(":", 1)
            name = name.strip()
            if name and password:
                out.append((name, password))
    admin_user = os.getenv("ENGLISH_BUDDY_ADMIN_USER", "").strip()
    admin_pass = os.getenv("ENGLISH_BUDDY_ADMIN_PASSWORD", "").strip()
    if admin_user and admin_pass:
        out.append((admin_user, admin_pass))
    dedup: dict[str, str] = {}
    for name, password in out:
        dedup[name] = password
    return list(dedup.items())
