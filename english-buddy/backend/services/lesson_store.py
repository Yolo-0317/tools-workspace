"""Lesson CRUD backed by SQLite; seeds from lessons.json by curriculum version."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from db.database import connect, init_db
from services.read_along import material_chunks
from teaching.grades import default_grade_id, get_grade

LESSONS_JSON = Path(__file__).resolve().parent.parent / "teaching" / "lessons.json"

PREWARM_NONE = "none"
PREWARM_PENDING = "pending"
PREWARM_READY = "ready"
PREWARM_FAILED = "failed"
CUSTOM_GRADE_ID = "custom"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _curriculum_version() -> str:
    if not LESSONS_JSON.is_file():
        return "0"
    try:
        data = json.loads(LESSONS_JSON.read_text(encoding="utf-8"))
        return str(data.get("version", 1))
    except (OSError, json.JSONDecodeError):
        return "0"


def _meta_get(conn, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = ?", (key,)
    ).fetchone()
    return str(row["value"]) if row else None


def _meta_set(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


def _lesson_row_to_dict(row, prewarm: dict | None = None) -> dict:
    out = {
        "id": row["id"],
        "grade_id": row["grade_id"],
        "title": row["title"],
        "text": row["text"],
        "unit_num": int(row["unit_num"] or 0),
        "is_builtin": bool(row["is_builtin"]),
        "owner_user_id": row["owner_user_id"],
        "updated_at": row["updated_at"],
    }
    if prewarm:
        out.update(
            {
                "prewarm_status": prewarm["status"],
                "prewarm_speed": prewarm["tts_speed"],
                "prewarm_chunks": prewarm["chunks"],
                "prewarm_done": prewarm["done"],
                "prewarm_error": prewarm["error"],
                "prewarm_program_id": prewarm["program_id"],
            }
        )
    else:
        out.update(
            {
                "prewarm_status": PREWARM_NONE,
                "prewarm_speed": None,
                "prewarm_chunks": 0,
                "prewarm_done": 0,
                "prewarm_error": None,
                "prewarm_program_id": None,
            }
        )
    return out


def _fetch_prewarm(
    conn, lesson_id: str, program_id: str, tts_speed: float
) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM lesson_prewarm
        WHERE lesson_id = ? AND program_id = ? AND tts_speed = ?
        """,
        (lesson_id, program_id, tts_speed),
    ).fetchone()
    if not row:
        return None
    return {
        "lesson_id": row["lesson_id"],
        "program_id": row["program_id"],
        "tts_speed": float(row["tts_speed"]),
        "status": row["status"],
        "chunks": int(row["chunks"] or 0),
        "done": int(row["done"] or 0),
        "error": row["error"],
    }


def _invalidate_lesson_prewarm(conn, lesson_id: str) -> None:
    conn.execute("DELETE FROM tts_cache WHERE lesson_id = ?", (lesson_id,))
    conn.execute("DELETE FROM lesson_prewarm WHERE lesson_id = ?", (lesson_id,))


def _parse_builtin_lessons(data: dict) -> dict[str, dict]:
    """Return {lesson_id: {grade_id, title, text, unit_num}} from lessons.json."""
    out: dict[str, dict] = {}
    lessons_by_grade = data.get("lessons") or {}
    for grade_id, items in lessons_by_grade.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            lid = str(item.get("id", "")).strip()
            title = str(item.get("title", "")).strip()
            text = str(item.get("text", "")).strip()
            unit_num = int(item.get("unit", 0) or 0)
            if not lid or not title or not text:
                continue
            out[lid] = {
                "grade_id": grade_id,
                "title": title,
                "text": text,
                "unit_num": unit_num,
            }
    return out


def _upsert_builtin_lesson(conn, lid: str, item: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO lessons
            (id, grade_id, title, text, unit_num, is_builtin, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        """,
        (
            lid,
            item["grade_id"],
            item["title"],
            item["text"],
            item["unit_num"],
            _now(),
        ),
    )


def _builtin_lesson_changed(old, item: dict) -> bool:
    if old is None:
        return True
    return (
        str(old["grade_id"]) != item["grade_id"]
        or str(old["title"]) != item["title"]
        or str(old["text"]) != item["text"]
        or int(old["unit_num"] or 0) != item["unit_num"]
    )


def _seed_from_json(conn) -> None:
    if not LESSONS_JSON.is_file():
        return
    try:
        data = json.loads(LESSONS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    target = str(data.get("version", 1))
    stored = _meta_get(conn, "curriculum_version")
    incoming = _parse_builtin_lessons(data)
    if not incoming:
        return

    existing_rows = conn.execute(
        "SELECT id, grade_id, title, text, unit_num FROM lessons WHERE is_builtin = 1"
    ).fetchall()
    existing = {str(row["id"]): row for row in existing_rows}

    if stored == target and existing:
        missing = set(incoming) - set(existing)
        removed = set(existing) - set(incoming)
        changed = any(
            _builtin_lesson_changed(existing.get(lid), item)
            for lid, item in incoming.items()
            if lid in existing
        )
        if not missing and not removed and not changed:
            return

    # First import or empty DB: full reseed (clears all builtin cache once).
    if not stored or not existing:
        conn.execute("DELETE FROM tts_cache")
        conn.execute("DELETE FROM lesson_prewarm")
        conn.execute("DELETE FROM lessons WHERE is_builtin = 1")
        for lid, item in incoming.items():
            _upsert_builtin_lesson(conn, lid, item)
    else:
        # Version bump with unchanged lessons: only invalidate lessons that changed.
        for lid in set(existing) - set(incoming):
            _invalidate_lesson_prewarm(conn, lid)
            conn.execute("DELETE FROM lessons WHERE id = ?", (lid,))
        for lid, item in incoming.items():
            old = existing.get(lid)
            if _builtin_lesson_changed(old, item):
                if old is not None:
                    _invalidate_lesson_prewarm(conn, lid)
                _upsert_builtin_lesson(conn, lid, item)

    _meta_set(conn, "curriculum_version", target)
    conn.commit()


def _migrate_custom_lessons(conn) -> None:
    conn.execute(
        """
        UPDATE lessons SET grade_id = ?
        WHERE is_builtin = 0 AND grade_id != ?
        """,
        (CUSTOM_GRADE_ID, CUSTOM_GRADE_ID),
    )
    conn.commit()


def _purge_demo_custom_lessons(conn) -> None:
    """Remove dev/test custom lessons (e.g. 测试课)."""
    rows = conn.execute(
        """
        SELECT id FROM lessons
        WHERE is_builtin = 0
          AND (title LIKE '测试%' OR title GLOB '*测试*')
        """
    ).fetchall()
    for row in rows:
        lid = row["id"]
        conn.execute("DELETE FROM tts_cache WHERE lesson_id = ?", (lid,))
        conn.execute("DELETE FROM lesson_prewarm WHERE lesson_id = ?", (lid,))
        conn.execute("DELETE FROM lessons WHERE id = ?", (lid,))
    if rows:
        conn.commit()


def ensure_db() -> None:
    init_db()
    conn = connect()
    try:
        _seed_from_json(conn)
        _migrate_custom_lessons(conn)
        _purge_demo_custom_lessons(conn)
    finally:
        conn.close()


def list_all_builtin_lessons() -> list[dict]:
    ensure_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM lessons WHERE is_builtin = 1 ORDER BY grade_id, unit_num"
        ).fetchall()
        return [_lesson_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_lessons(
    grade_id: str | None = None,
    *,
    program_id: str | None = None,
    tts_speed: float | None = None,
    custom_only: bool = False,
    owner_user_id: str | None = None,
    require_prewarm: bool = True,
) -> list[dict]:
    ensure_db()
    gid = (grade_id or default_grade_id()).strip()
    if not get_grade(gid):
        gid = default_grade_id()

    conn = connect()
    try:
        if custom_only:
            if not owner_user_id:
                return []
            rows = conn.execute(
                """
                SELECT * FROM lessons
                WHERE is_builtin = 0 AND owner_user_id = ?
                ORDER BY updated_at DESC, title ASC
                """,
                (owner_user_id,),
            ).fetchall()
        elif owner_user_id:
            rows = conn.execute(
                """
                SELECT * FROM lessons
                WHERE (is_builtin = 1 AND grade_id = ?)
                   OR (is_builtin = 0 AND owner_user_id = ?)
                ORDER BY is_builtin DESC, unit_num ASC, title ASC
                """,
                (gid, owner_user_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM lessons
                WHERE is_builtin = 1 AND grade_id = ?
                ORDER BY unit_num ASC, title ASC
                """,
                (gid,),
            ).fetchall()
        out: list[dict] = []
        picker_mode = (
            require_prewarm
            and not custom_only
            and program_id
            and tts_speed is not None
        )
        for row in rows:
            prewarm = None
            if program_id and tts_speed is not None:
                prewarm = _fetch_prewarm(conn, row["id"], program_id, tts_speed)
            if picker_mode:
                if not prewarm or prewarm.get("status") != PREWARM_READY:
                    continue
            out.append(_lesson_row_to_dict(row, prewarm))
        return out
    finally:
        conn.close()


def get_lesson(lesson_id: str) -> dict | None:
    ensure_db()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM lessons WHERE id = ?", (lesson_id.strip(),)
        ).fetchone()
        return _lesson_row_to_dict(row) if row else None
    finally:
        conn.close()


def _slug_id(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower().strip())[:24].strip("_")
    return f"custom_{base or 'lesson'}_{uuid.uuid4().hex[:8]}"


def create_lesson(title: str, text: str, *, owner_user_id: str) -> dict:
    ensure_db()
    title = title.strip()
    text = text.strip()
    if len(title) < 1 or len(title) > 80:
        raise ValueError("课文名称 1～80 字")
    if len(text) < 10:
        raise ValueError("课文内容至少 10 字")
    owner = owner_user_id.strip()
    if not owner:
        raise ValueError("未登录，无法保存自定义课文")
    lid = _slug_id(title)
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO lessons
                (id, grade_id, title, text, unit_num, is_builtin, owner_user_id, updated_at)
            VALUES (?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (lid, CUSTOM_GRADE_ID, title, text, owner, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    lesson = get_lesson(lid)
    assert lesson
    return lesson


def delete_lesson(lesson_id: str, *, owner_user_id: str | None = None) -> bool:
    ensure_db()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT is_builtin, owner_user_id FROM lessons WHERE id = ?",
            (lesson_id,),
        ).fetchone()
        if not row or row["is_builtin"]:
            return False
        if owner_user_id and row["owner_user_id"] != owner_user_id:
            return False
        conn.execute("DELETE FROM tts_cache WHERE lesson_id = ?", (lesson_id,))
        conn.execute("DELETE FROM lesson_prewarm WHERE lesson_id = ?", (lesson_id,))
        conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def set_prewarm_progress(
    lesson_id: str,
    program_id: str,
    *,
    status: str,
    speed: float,
    chunks: int = 0,
    done: int = 0,
    error: str | None = None,
) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO lesson_prewarm
                (lesson_id, program_id, tts_speed, status, chunks, done, error, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lesson_id, program_id, tts_speed) DO UPDATE SET
                status = excluded.status,
                chunks = excluded.chunks,
                done = excluded.done,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (lesson_id, program_id, speed, status, chunks, done, error, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_prewarm_status(
    lesson_id: str, program_id: str, tts_speed: float
) -> dict:
    ensure_db()
    conn = connect()
    try:
        row = _fetch_prewarm(conn, lesson_id, program_id, tts_speed)
        if not row:
            return {
                "lesson_id": lesson_id,
                "program_id": program_id,
                "tts_speed": tts_speed,
                "status": PREWARM_NONE,
                "chunks": 0,
                "done": 0,
                "error": None,
            }
        return row
    finally:
        conn.close()


def chunk_count_for_text(text: str) -> int:
    return len(material_chunks(text))


def is_prewarm_ready(lesson_id: str, tts_speed: float, program_id: str) -> bool:
    row = get_prewarm_status(lesson_id, program_id, tts_speed)
    return row["status"] == PREWARM_READY
