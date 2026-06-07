"""Shanghai kindergarten + primary English grade levels."""

from __future__ import annotations

import json
from pathlib import Path

GRADES_JSON = Path(__file__).resolve().parent / "lessons.json"


def load_grades() -> list[dict]:
    if not GRADES_JSON.is_file():
        return []
    try:
        data = json.loads(GRADES_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    grades = data.get("grades") or []
    out: list[dict] = []
    for g in grades:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id", "")).strip()
        title = str(g.get("title", "")).strip()
        if not gid or not title:
            continue
        out.append(
            {
                "id": gid,
                "title": title,
                "subtitle": str(g.get("subtitle", "")).strip(),
                "stage": str(g.get("stage", "primary")).strip(),
                "stage_label": str(g.get("stage_label", "小学")).strip(),
                "semester": str(g.get("semester", "")).strip(),
                "book": str(g.get("book", "")).strip(),
            }
        )
    return out


def get_grade(grade_id: str | None) -> dict | None:
    gid = (grade_id or "").strip()
    for g in load_grades():
        if g["id"] == gid:
            return g
    return None


def default_grade_id() -> str:
    grades = load_grades()
    for g in grades:
        if g["id"] == "kg_middle":
            return "kg_middle"
    return grades[0]["id"] if grades else "kg_middle"


def list_grades_public() -> list[dict]:
    return load_grades()
