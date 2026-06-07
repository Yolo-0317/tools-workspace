"""Lesson management + TTS prewarm REST API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services import tts
from services.auth_deps import get_optional_user, require_user
from services.lesson_store import (
    create_lesson,
    delete_lesson,
    get_lesson,
    get_prewarm_status,
    is_prewarm_ready,
    list_lessons,
)
from services.builtin_prewarm import builtin_prewarm_stats
from services.tts_cache import prewarm_lesson
from teaching.grades import default_grade_id
from teaching.programs import DEFAULT_PROGRAM_ID

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


class CreateLessonBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    text: str = Field(..., min_length=10, max_length=8000)


class PrewarmBody(BaseModel):
    tts_speed: float = Field(default=1.0, ge=0.7, le=1.4)
    program_id: str = Field(default=DEFAULT_PROGRAM_ID, min_length=1)


def _lesson_payload(x: dict) -> dict:
    return {
        "id": x["id"],
        "grade_id": x["grade_id"],
        "title": x["title"],
        "text": x["text"],
        "unit_num": x.get("unit_num", 0),
        "is_builtin": x["is_builtin"],
        "prewarm_status": x.get("prewarm_status"),
        "prewarm_speed": x.get("prewarm_speed"),
        "prewarm_chunks": x.get("prewarm_chunks"),
        "prewarm_done": x.get("prewarm_done"),
        "prewarm_error": x.get("prewarm_error"),
        "prewarm_program_id": x.get("prewarm_program_id"),
    }


def _assert_custom_access(
    lesson: dict, user: Optional[Dict[str, Any]]
) -> None:
    if lesson.get("is_builtin"):
        return
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    if lesson.get("owner_user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="无权访问该课文")


@router.get("/prewarm/builtin")
async def lessons_builtin_prewarm_status(
    program: Optional[str] = None,
    tts_speed: float = 1.0,
) -> dict:
    speed = tts.clamp_tts_speed(tts_speed)
    prog = program or DEFAULT_PROGRAM_ID
    return builtin_prewarm_stats(prog, speed)


@router.get("")
async def lessons_list(
    grade: Optional[str] = None,
    program: Optional[str] = None,
    tts_speed: float = 1.0,
    custom_only: bool = False,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> dict:
    if custom_only and not user:
        raise HTTPException(status_code=401, detail="请先登录")
    speed = tts.clamp_tts_speed(tts_speed)
    prog = program or DEFAULT_PROGRAM_ID
    gid = grade or default_grade_id()
    items = list_lessons(
        gid,
        program_id=prog,
        tts_speed=speed,
        custom_only=custom_only,
        owner_user_id=user["id"] if user else None,
    )
    return {
        "grade": gid,
        "program": prog,
        "tts_speed": speed,
        "lessons": [_lesson_payload(x) for x in items],
    }


@router.post("")
async def lessons_create(
    body: CreateLessonBody,
    user: dict = Depends(require_user),
) -> dict:
    try:
        lesson = create_lesson(body.title, body.text, owner_user_id=user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"lesson": _lesson_payload(lesson)}


@router.get("/{lesson_id}")
async def lessons_get(
    lesson_id: str,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> dict:
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课文不存在")
    _assert_custom_access(lesson, user)
    return {"lesson": _lesson_payload(lesson)}


@router.delete("/{lesson_id}")
async def lessons_delete(
    lesson_id: str,
    user: dict = Depends(require_user),
) -> dict:
    if not delete_lesson(lesson_id, owner_user_id=user["id"]):
        raise HTTPException(status_code=400, detail="无法删除（内置课文、不存在或无权限）")
    return {"ok": True}


@router.post("/{lesson_id}/prewarm")
async def lessons_prewarm(
    lesson_id: str,
    body: PrewarmBody,
    user: dict = Depends(require_user),
) -> dict:
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课文不存在")
    _assert_custom_access(lesson, user)
    if lesson["is_builtin"]:
        raise HTTPException(status_code=400, detail="内置课文由后台自动预热")
    speed = tts.clamp_tts_speed(body.tts_speed)
    try:
        result = await prewarm_lesson(lesson_id, speed, body.program_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return result


@router.get("/{lesson_id}/prewarm/status")
async def lessons_prewarm_status(
    lesson_id: str,
    tts_speed: float = 1.0,
    program: str = DEFAULT_PROGRAM_ID,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> dict:
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课文不存在")
    _assert_custom_access(lesson, user)
    speed = tts.clamp_tts_speed(tts_speed)
    row = get_prewarm_status(lesson_id, program, speed)
    return {
        "lesson_id": lesson_id,
        "program": program,
        "prewarm_status": row["status"],
        "prewarm_speed": row["tts_speed"],
        "prewarm_chunks": row["chunks"],
        "prewarm_done": row["done"],
        "prewarm_error": row["error"],
        "ready": is_prewarm_ready(lesson_id, speed, program),
        "tts_speed": speed,
    }
