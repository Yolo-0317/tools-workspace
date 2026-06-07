"""Readalong admin login (stdlib, signed session cookie)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
SESSION_COOKIE = "ra_session"
DEFAULT_TTL_HOURS = 720


def auth_enabled() -> bool:
    return bool(admin_users())


def admin_users() -> dict[str, str]:
    out: dict[str, str] = {}
    raw = os.environ.get("READALONG_USERS", "").strip()
    if raw:
        for part in raw.split(","):
            piece = part.strip()
            if not piece or ":" not in piece:
                continue
            name, password = piece.split(":", 1)
            name = name.strip()
            if name and password:
                out[name] = password
    user = os.environ.get("READALONG_ADMIN_USER", "admin").strip()
    password = os.environ.get("READALONG_ADMIN_PASSWORD", "").strip()
    if user and password:
        out[user] = password
    return out


def session_ttl_seconds() -> int:
    try:
        hours = max(1, int(os.environ.get("READALONG_SESSION_TTL_HOURS", str(DEFAULT_TTL_HOURS))))
    except ValueError:
        hours = DEFAULT_TTL_HOURS
    return hours * 3600


def cookie_path() -> str:
    raw = os.environ.get("READALONG_COOKIE_PATH", "/readalong/").strip() or "/"
    if not raw.startswith("/"):
        raw = f"/{raw}"
    if raw != "/" and not raw.endswith("/"):
        raw = f"{raw}/"
    return raw


def cookie_secure() -> bool:
    return os.environ.get("READALONG_COOKIE_SECURE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def cookie_samesite() -> str:
    return os.environ.get("READALONG_COOKIE_SAMESITE", "lax").strip().lower() or "lax"


def _auth_secret() -> bytes:
    env = os.environ.get("READALONG_AUTH_SECRET", "").strip()
    if env:
        return env.encode("utf-8")
    path = ROOT / "data" / ".auth_secret"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip().encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(32)
    path.write_text(secret, encoding="utf-8")
    return secret.encode("utf-8")


def verify_login(username: str, password: str) -> bool:
    users = admin_users()
    stored = users.get((username or "").strip())
    if not stored:
        return False
    return hmac.compare_digest(stored, password)


def create_session_token(username: str) -> str:
    exp = int(time.time()) + session_ttl_seconds()
    payload = f"{username}:{exp}"
    sig = hmac.new(_auth_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{payload}:{sig}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def parse_session_token(token: str) -> str | None:
    if not token:
        return None
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad).decode("utf-8")
        username, exp_s, sig = raw.rsplit(":", 2)
        exp = int(exp_s)
    except (ValueError, UnicodeDecodeError):
        return None
    if exp <= int(time.time()):
        return None
    payload = f"{username}:{exp}"
    expected = hmac.new(_auth_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    if username not in admin_users():
        return None
    return username


def session_user_from_headers(headers: Mapping[str, str]) -> str | None:
    cookie_header = headers.get("Cookie") or headers.get("cookie") or ""
    if not cookie_header:
        return None
    jar = SimpleCookie()
    jar.load(cookie_header)
    morsel = jar.get(SESSION_COOKIE)
    if not morsel:
        return None
    return parse_session_token(morsel.value)


def set_session_cookie_header(username: str) -> str:
    token = create_session_token(username)
    parts = [
        f"{SESSION_COOKIE}={token}",
        f"Path={cookie_path()}",
        "HttpOnly",
        f"Max-Age={session_ttl_seconds()}",
        f"SameSite={cookie_samesite().capitalize()}",
    ]
    if cookie_secure():
        parts.append("Secure")
    return "; ".join(parts)


def clear_session_cookie_header() -> str:
    parts = [
        f"{SESSION_COOKIE}=",
        f"Path={cookie_path()}",
        "HttpOnly",
        "Max-Age=0",
        f"SameSite={cookie_samesite().capitalize()}",
    ]
    if cookie_secure():
        parts.append("Secure")
    return "; ".join(parts)


def read_json_body(body: bytes) -> dict:
    if not body:
        return {}
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
