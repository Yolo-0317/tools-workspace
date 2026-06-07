"""Background TTS prewarm for all built-in lessons (concurrent)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from services.lesson_store import (
    PREWARM_FAILED,
    PREWARM_PENDING,
    PREWARM_READY,
    get_prewarm_status,
    list_all_builtin_lessons,
)
from services.tts_cache import prewarm_lesson

logger = logging.getLogger(__name__)

BUILTIN_SPEEDS = (0.85, 1.0, 1.15)
BUILTIN_PROGRAMS = ("elsa_snow", "ultra_hero")

_task: Optional[asyncio.Task] = None


def prewarm_enabled() -> bool:
    return os.getenv("BUILTIN_PREWARM", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def prewarm_concurrency() -> int:
    try:
        return max(1, min(12, int(os.getenv("BUILTIN_PREWARM_CONCURRENCY", "4"))))
    except ValueError:
        return 4


def _count_combo_stats() -> dict[str, int]:
    lessons = list_all_builtin_lessons()
    total = len(lessons) * len(BUILTIN_PROGRAMS) * len(BUILTIN_SPEEDS)
    ready = pending = failed = none = 0
    for lesson in lessons:
        lid = lesson["id"]
        for program_id in BUILTIN_PROGRAMS:
            for speed in BUILTIN_SPEEDS:
                row = get_prewarm_status(lid, program_id, speed)
                st = row["status"]
                if st == PREWARM_READY:
                    ready += 1
                elif st == PREWARM_PENDING:
                    pending += 1
                elif st == PREWARM_FAILED:
                    failed += 1
                else:
                    none += 1
    return {
        "builtin_lessons": len(lessons),
        "total": total,
        "ready": ready,
        "pending": pending,
        "failed": failed,
        "none": none,
    }


def builtin_prewarm_stats(
    program_id: str | None = None,
    tts_speed: float | None = None,
) -> dict:
    """Aggregate prewarm progress (all combos, or one teacher+speed slice)."""
    if program_id and tts_speed is not None:
        lessons = list_all_builtin_lessons()
        total = len(lessons)
        ready = pending = failed = none = 0
        for lesson in lessons:
            row = get_prewarm_status(lesson["id"], program_id, tts_speed)
            st = row["status"]
            if st == PREWARM_READY:
                ready += 1
            elif st == PREWARM_PENDING:
                pending += 1
            elif st == PREWARM_FAILED:
                failed += 1
            else:
                none += 1
        return {
            "scope": "slice",
            "program": program_id,
            "tts_speed": tts_speed,
            "total_lessons": total,
            "ready_lessons": ready,
            "pending_lessons": pending,
            "failed_lessons": failed,
            "waiting_lessons": none,
            "complete": ready >= total and total > 0,
        }
    combo = _count_combo_stats()
    combo["scope"] = "all"
    combo["complete"] = combo["ready"] >= combo["total"] and combo["total"] > 0
    combo["running"] = combo["pending"] > 0
    return combo


async def prewarm_all_builtin() -> dict[str, int]:
    """Prewarm every built-in lesson × teacher × speed (skip if already ready)."""
    lessons = list_all_builtin_lessons()
    jobs: list[tuple[str, float, str]] = []
    for lesson in lessons:
        lid = lesson["id"]
        for program_id in BUILTIN_PROGRAMS:
            for speed in BUILTIN_SPEEDS:
                jobs.append((lid, speed, program_id))

    stats = {"total": len(jobs), "skipped": 0, "done": 0, "failed": 0}
    sem = asyncio.Semaphore(prewarm_concurrency())
    lock = asyncio.Lock()

    async def _one(lid: str, speed: float, program_id: str) -> None:
        row = get_prewarm_status(lid, program_id, speed)
        if row["status"] == PREWARM_READY:
            async with lock:
                stats["skipped"] += 1
            return
        async with sem:
            try:
                await prewarm_lesson(lid, speed, program_id)
                async with lock:
                    stats["done"] += 1
            except Exception as e:
                async with lock:
                    stats["failed"] += 1
                logger.warning(
                    "builtin prewarm failed %s/%s@%.2f: %s",
                    lid,
                    program_id,
                    speed,
                    e,
                )

    await asyncio.gather(*[_one(lid, spd, prog) for lid, spd, prog in jobs])
    return stats


async def _run_prewarm_job() -> None:
    try:
        n = prewarm_concurrency()
        logger.info("builtin prewarm starting (concurrency=%s)", n)
        stats = await prewarm_all_builtin()
        logger.info(
            "builtin prewarm finished: done=%s skipped=%s failed=%s total=%s",
            stats["done"],
            stats["skipped"],
            stats["failed"],
            stats["total"],
        )
    except Exception:
        logger.exception("builtin prewarm job crashed")


def schedule_builtin_prewarm() -> None:
    """Fire-and-forget background prewarm (idempotent per lesson/program/speed)."""
    global _task
    if not prewarm_enabled():
        logger.info("builtin prewarm disabled (BUILTIN_PREWARM=0)")
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _task and not _task.done():
        logger.info("builtin prewarm already running")
        return
    _task = loop.create_task(_run_prewarm_job(), name="builtin-prewarm")
