"""Read-along lessons — SQLite store (seeded from lessons.json by grade)."""

from __future__ import annotations

from services.lesson_store import get_lesson as _get_by_id
from services.lesson_store import list_lessons as _list


def list_lessons(grade_id: str | None = None) -> list[dict]:
    return _list(grade_id)


def get_lesson(grade_id: str | None, lesson_id: str) -> dict | None:
    row = _get_by_id(lesson_id.strip())
    if not row:
        return None
    if grade_id and row["grade_id"] != grade_id.strip():
        return None
    return row
