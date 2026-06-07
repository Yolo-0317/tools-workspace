"""SQLite for lessons + per-teacher TTS prewarm."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "english_buddy.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    grade_id TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    unit_num INTEGER NOT NULL DEFAULT 0,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lesson_prewarm (
    lesson_id TEXT NOT NULL,
    program_id TEXT NOT NULL,
    tts_speed REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'none',
    chunks INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (lesson_id, program_id, tts_speed)
);

CREATE TABLE IF NOT EXISTS tts_cache (
    lesson_id TEXT NOT NULL,
    program_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    tts_speed REAL NOT NULL,
    text_hash TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    PRIMARY KEY (lesson_id, program_id, chunk_index, tts_speed)
);

"""

_lock = threading.Lock()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r["name"]) for r in rows}


def _rebuild_lessons_v3(conn: sqlite3.Connection) -> None:
    """Replace v2 lessons (program_id) with v3 (grade_id only)."""
    conn.execute("DROP TABLE IF EXISTS tts_cache")
    conn.execute("DROP TABLE IF EXISTS lesson_prewarm")
    conn.execute("ALTER TABLE lessons RENAME TO lessons_v2_backup")
    conn.execute(
        """
        CREATE TABLE lessons (
            id TEXT PRIMARY KEY,
            grade_id TEXT NOT NULL,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            unit_num INTEGER NOT NULL DEFAULT 0,
            is_builtin INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    backup_cols = _table_columns(conn, "lessons_v2_backup")
    if backup_cols:
        conn.execute(
            """
            INSERT INTO lessons (id, grade_id, title, text, unit_num, is_builtin, updated_at)
            SELECT id,
                CASE program_id
                    WHEN 'ultra_hero' THEN 'g2'
                    WHEN 'elsa_snow' THEN 'g1'
                    ELSE 'g2'
                END,
                title, text, 0, is_builtin, updated_at
            FROM lessons_v2_backup
            WHERE is_builtin = 0
            """
        )
    conn.execute("DROP TABLE IF EXISTS lessons_v2_backup")
    conn.execute("DELETE FROM app_meta WHERE key = 'curriculum_version'")


def _migrate_legacy(conn: sqlite3.Connection) -> None:
    """Upgrade v2 schema (program_id + inline prewarm) → v3 (grade_id + lesson_prewarm)."""
    cols = _table_columns(conn, "lessons")
    if not cols:
        return

    if "program_id" in cols:
        _rebuild_lessons_v3(conn)
        return

    if "grade_id" not in cols:
        conn.execute("ALTER TABLE lessons ADD COLUMN grade_id TEXT NOT NULL DEFAULT 'g1'")
    if "unit_num" not in cols:
        conn.execute(
            "ALTER TABLE lessons ADD COLUMN unit_num INTEGER NOT NULL DEFAULT 0"
        )

    cache_cols = _table_columns(conn, "tts_cache")
    if cache_cols and "program_id" not in cache_cols:
        conn.execute("DROP TABLE IF EXISTS tts_cache")


_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS lesson_prewarm (
    lesson_id TEXT NOT NULL,
    program_id TEXT NOT NULL,
    tts_speed REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'none',
    chunks INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (lesson_id, program_id, tts_speed)
);

CREATE TABLE IF NOT EXISTS tts_cache (
    lesson_id TEXT NOT NULL,
    program_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    tts_speed REAL NOT NULL,
    text_hash TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    PRIMARY KEY (lesson_id, program_id, chunk_index, tts_speed)
);
"""


def init_db() -> None:
    with _lock:
        conn = connect()
        try:
            conn.executescript(_SCHEMA)
            _migrate_legacy(conn)
            conn.executescript(_CACHE_SCHEMA)
            cols = _table_columns(conn, "lessons")
            if "grade_id" in cols:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_lessons_grade ON lessons(grade_id)"
                )
            _migrate_auth(conn)
            conn.commit()
        finally:
            conn.close()


def _migrate_auth(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            created_at TEXT NOT NULL
        );
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
    cols = _table_columns(conn, "lessons")
    if cols and "owner_user_id" not in cols:
        conn.execute("ALTER TABLE lessons ADD COLUMN owner_user_id TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lessons_owner ON lessons(owner_user_id)"
        )
