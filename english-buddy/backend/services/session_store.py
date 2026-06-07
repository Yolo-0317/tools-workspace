"""Login sessions (SQLite)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from db.database import connect
from services.auth_settings import session_ttl_hours


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_sessions_table() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS eb_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_eb_sessions_user ON eb_sessions(user_id);
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_session(user_id: str) -> tuple[str, datetime]:
    ensure_sessions_table()
    token = secrets.token_urlsafe(32)
    now = _now()
    expires = now + timedelta(hours=session_ttl_hours())
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO eb_sessions (token, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, _iso(now), _iso(expires)),
        )
        conn.commit()
    finally:
        conn.close()
    return token, expires


def get_session(token: str) -> dict | None:
    if not token:
        return None
    ensure_sessions_table()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT token, user_id, expires_at FROM eb_sessions WHERE token = ?",
            (token.strip(),),
        ).fetchone()
        if not row:
            return None
        expires = datetime.strptime(row["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        if expires <= _now():
            conn.execute("DELETE FROM eb_sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        return {"token": row["token"], "user_id": row["user_id"]}
    finally:
        conn.close()


def delete_session(token: str) -> None:
    if not token:
        return
    ensure_sessions_table()
    conn = connect()
    try:
        conn.execute("DELETE FROM eb_sessions WHERE token = ?", (token.strip(),))
        conn.commit()
    finally:
        conn.close()
