"""User accounts (SQLite) — bootstrap from ENGLISH_BUDDY_USERS. See docs/AUTH.md."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from db.database import connect
from services.auth_settings import bootstrap_users
from services.passwords import hash_password, verify_password


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _user_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"] or row["username"],
        "created_at": row["created_at"],
    }


def ensure_users_table() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def list_users() -> list[dict]:
    ensure_users_table()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY username ASC"
        ).fetchall()
        return [_user_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> dict | None:
    if not user_id:
        return None
    ensure_users_table()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id.strip(),)
        ).fetchone()
        return _user_row_to_dict(row) if row else None
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    name = username.strip()
    if not name:
        return None
    ensure_users_table()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (name,)
        ).fetchone()
        return _user_row_to_dict(row) if row else None
    finally:
        conn.close()


def _get_password_hash(username: str) -> str | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        return str(row["password_hash"]) if row else None
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict | None:
    name = username.strip()
    if not name or not password:
        return None
    stored = _get_password_hash(name)
    if not stored or not verify_password(password, stored):
        return None
    return get_user_by_username(name)


def upsert_user(username: str, password: str) -> dict:
    ensure_users_table()
    name = username.strip()
    if not name:
        raise ValueError("用户名不能为空")
    if not password:
        raise ValueError("密码不能为空")
    ph = hash_password(password)
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (name,)
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE users SET password_hash = ?, display_name = ?
                WHERE username = ?
                """,
                (ph, name, name),
            )
            uid = row["id"]
        else:
            uid = f"user_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (uid, name, ph, name, _now()),
            )
        conn.commit()
    finally:
        conn.close()
    user = get_user_by_username(name)
    assert user
    return user


def bootstrap_from_env() -> int:
    """Create/update users from ENGLISH_BUDDY_USERS / ADMIN_* env."""
    ensure_users_table()
    pairs = bootstrap_users()
    if not pairs:
        return 0
    n = 0
    for username, password in pairs:
        upsert_user(username, password)
        n += 1
    return n


def delete_user(username: str) -> bool:
    """Remove user, sessions, and owned custom lessons (incl. TTS cache)."""
    name = username.strip()
    if not name:
        return False
    ensure_users_table()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (name,)
        ).fetchone()
        if not row:
            return False
        uid = row["id"]
        lesson_rows = conn.execute(
            """
            SELECT id FROM lessons
            WHERE owner_user_id = ? AND is_builtin = 0
            """,
            (uid,),
        ).fetchall()
        for lr in lesson_rows:
            lid = lr["id"]
            conn.execute("DELETE FROM tts_cache WHERE lesson_id = ?", (lid,))
            conn.execute("DELETE FROM lesson_prewarm WHERE lesson_id = ?", (lid,))
            conn.execute("DELETE FROM lessons WHERE id = ?", (lid,))
        conn.execute("DELETE FROM eb_sessions WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
        return True
    finally:
        conn.close()


def assign_orphan_custom_lessons(default_user_id: str) -> int:
    """Attach legacy custom lessons (no owner) to the first bootstrap user."""
    if not default_user_id:
        return 0
    conn = connect()
    try:
        cur = conn.execute(
            """
            UPDATE lessons
            SET owner_user_id = ?
            WHERE is_builtin = 0
              AND (owner_user_id IS NULL OR owner_user_id = '')
            """,
            (default_user_id,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def lesson_owned_by(lesson_id: str, user_id: str) -> bool:
    lesson = _get_lesson_owner(lesson_id)
    if not lesson:
        return False
    if lesson["is_builtin"]:
        return True
    return lesson["owner_user_id"] == user_id


def _get_lesson_owner(lesson_id: str) -> dict | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, is_builtin, owner_user_id FROM lessons WHERE id = ?",
            (lesson_id.strip(),),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "is_builtin": bool(row["is_builtin"]),
            "owner_user_id": row["owner_user_id"],
        }
    finally:
        conn.close()
