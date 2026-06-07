"""Disk TTS cache + lesson prewarm (per teacher voice)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from services import tts
from services.lesson_store import (
    PREWARM_FAILED,
    PREWARM_PENDING,
    PREWARM_READY,
    get_lesson,
    set_prewarm_progress,
)
from services.read_along import material_chunks
from teaching.programs import get_program

logger = logging.getLogger(__name__)

CACHE_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "tts_cache"


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def _audio_path(
    lesson_id: str,
    program_id: str,
    speed: float,
    chunk_index: int,
    text_hash: str,
) -> Path:
    spd = f"{speed:.2f}".replace(".", "_")
    return (
        CACHE_ROOT
        / lesson_id
        / program_id
        / spd
        / f"{chunk_index:03d}_{text_hash}.audio"
    )


def get_cached_audio(
    lesson_id: str,
    program_id: str,
    chunk_index: int,
    tts_speed: float,
    text: str,
) -> bytes | None:
    path = _audio_path(
        lesson_id, program_id, tts_speed, chunk_index, _text_hash(text)
    )
    if path.is_file():
        return path.read_bytes()
    return None


def _save_cache_row(
    lesson_id: str,
    program_id: str,
    chunk_index: int,
    tts_speed: float,
    text: str,
    audio: bytes,
) -> None:
    from db.database import connect

    th = _text_hash(text)
    path = _audio_path(lesson_id, program_id, tts_speed, chunk_index, th)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio)
    conn = connect()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO tts_cache
                (lesson_id, program_id, chunk_index, tts_speed, text_hash, audio_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (lesson_id, program_id, chunk_index, tts_speed, th, str(path)),
        )
        conn.commit()
    finally:
        conn.close()


def clear_lesson_cache(
    lesson_id: str,
    program_id: str,
    tts_speed: float | None = None,
) -> None:
    from db.database import connect

    conn = connect()
    try:
        if tts_speed is None:
            conn.execute(
                "DELETE FROM tts_cache WHERE lesson_id = ? AND program_id = ?",
                (lesson_id, program_id),
            )
        else:
            conn.execute(
                """
                DELETE FROM tts_cache
                WHERE lesson_id = ? AND program_id = ? AND tts_speed = ?
                """,
                (lesson_id, program_id, tts_speed),
            )
        conn.commit()
    finally:
        conn.close()
    lesson_dir = CACHE_ROOT / lesson_id / program_id
    if lesson_dir.is_dir() and tts_speed is None:
        import shutil

        shutil.rmtree(lesson_dir, ignore_errors=True)
    elif tts_speed is not None:
        spd_dir = lesson_dir / f"{tts_speed:.2f}".replace(".", "_")
        if spd_dir.is_dir():
            import shutil

            shutil.rmtree(spd_dir, ignore_errors=True)


async def prewarm_lesson(
    lesson_id: str, tts_speed: float, program_id: str
) -> dict:
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise ValueError("课文不存在")

    prog = get_program(program_id)
    chunks = material_chunks(lesson["text"])
    if not chunks:
        raise ValueError("课文无有效句子")

    speed = tts.clamp_tts_speed(tts_speed)
    clear_lesson_cache(lesson_id, prog.id, speed)
    set_prewarm_progress(
        lesson_id,
        prog.id,
        status=PREWARM_PENDING,
        speed=speed,
        chunks=len(chunks),
        done=0,
        error=None,
    )

    done = 0
    try:
        for i, chunk in enumerate(chunks):
            audio = await tts.text_to_mp3_bytes(
                chunk,
                voice=prog.tts_voice,
                rate=prog.tts_rate or None,
                pitch=prog.tts_pitch or None,
                program=prog,
                speed=speed,
            )
            if not audio:
                raise RuntimeError(f"空音频 chunk {i}")
            _save_cache_row(lesson_id, prog.id, i, speed, chunk, audio)
            done = i + 1
            set_prewarm_progress(
                lesson_id,
                prog.id,
                status=PREWARM_PENDING,
                speed=speed,
                chunks=len(chunks),
                done=done,
            )
        set_prewarm_progress(
            lesson_id,
            prog.id,
            status=PREWARM_READY,
            speed=speed,
            chunks=len(chunks),
            done=len(chunks),
        )
        return {
            "lesson_id": lesson_id,
            "program_id": prog.id,
            "status": PREWARM_READY,
            "chunks": len(chunks),
            "done": len(chunks),
            "tts_speed": speed,
        }
    except Exception as e:
        logger.warning("prewarm failed %s/%s: %s", lesson_id, prog.id, e)
        set_prewarm_progress(
            lesson_id,
            prog.id,
            status=PREWARM_FAILED,
            speed=speed,
            chunks=len(chunks),
            done=done,
            error=str(e),
        )
        raise


async def synthesize_with_cache(
    text: str,
    *,
    lesson_id: str | None,
    chunk_index: int | None,
    tts_speed: float,
    program,
) -> bytes:
    if lesson_id and chunk_index is not None:
        cached = get_cached_audio(
            lesson_id, program.id, chunk_index, tts_speed, text
        )
        if cached:
            return cached
    return await tts.text_to_mp3_bytes(
        text,
        voice=program.tts_voice,
        rate=program.tts_rate or None,
        pitch=program.tts_pitch or None,
        program=program,
        speed=tts_speed,
    )
