"""English Buddy API — REST fallback + WebSocket voice call."""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from starlette.staticfiles import StaticFiles

from services import llm, stt, tts
from teaching.guide import load_references, teaching_status
from db.database import init_db
from routers.auth_api import router as auth_router
from routers.calls_api import router as calls_router
from routers.lessons_api import router as lessons_router
from routers.ort_api import router as ort_router
from services.user_store import assign_orphan_custom_lessons, bootstrap_from_env, list_users
from services.builtin_prewarm import schedule_builtin_prewarm
from services.lesson_store import ensure_db
from teaching.grades import list_grades_public
from teaching.programs import list_programs_public
from middleware.url_prefix import StripUrlPrefixMiddleware
from ws_call import router as ws_router

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

URL_PREFIX = os.getenv("ENGLISH_BUDDY_URL_PREFIX", "/english").strip().rstrip("/")
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-JennyNeural")  # edge fallback only
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,"
        "https://hub.yoloworld.site:8883,https://hub.yoloworld.site:8443",
    ).split(",")
    if o.strip()
]

app = FastAPI(title="English Buddy", version="0.2.0")
if URL_PREFIX:
    app.add_middleware(StripUrlPrefixMiddleware, prefix=URL_PREFIX)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ws_router)
app.include_router(auth_router)
app.include_router(calls_router)
app.include_router(lessons_router)
app.include_router(ort_router)


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    ensure_db()
    bootstrap_from_env()
    users = list_users()
    if users:
        assign_orphan_custom_lessons(users[0]["id"])
    schedule_builtin_prewarm()


class HistoryTurn(BaseModel):
    role: str
    content: str


class ReplyRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list)


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class ReplyResponse(BaseModel):
    text: str
    audio_base64: str
    audio_mime: str = "audio/mpeg"


class HealthResponse(BaseModel):
    ok: bool
    ollama: bool
    model: str
    stt: str
    whisper_ready: bool
    whisper_model: str
    teaching_guide: dict[str, object]


async def _text_to_audio_b64(text: str) -> str:
    if not text:
        return ""
    audio = await tts.text_to_mp3_bytes(text.strip())
    return base64.b64encode(audio).decode("ascii")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    w = stt.whisper_status()
    return HealthResponse(
        ok=True,
        ollama=await llm.ollama_reachable(),
        model=llm.OLLAMA_MODEL,
        stt="whisper",
        whisper_ready=bool(w.get("ready")),
        whisper_model=str(w.get("model", "")),
        teaching_guide=teaching_status(),
    )


@app.get("/api/teaching/references")
async def teaching_references() -> dict:
    """Public kid-English resources for parents (not auto-scraped into lessons)."""
    return load_references()


@app.get("/api/programs")
async def programs() -> dict:
    """Themed shows: Elsa · Ultraman."""
    return {"programs": list_programs_public()}


@app.get("/api/grades")
async def grades() -> dict:
    """Shanghai kindergarten + primary grade levels."""
    from pathlib import Path
    import json

    curriculum = "上海幼儿园启蒙 + 沪教牛津小学"
    path = Path(__file__).resolve().parent / "teaching" / "lessons.json"
    if path.is_file():
        try:
            curriculum = json.loads(path.read_text(encoding="utf-8")).get(
                "curriculum", curriculum
            )
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "curriculum": curriculum,
        "grades": list_grades_public(),
    }


@app.post("/api/reply", response_model=ReplyResponse)
async def reply(req: ReplyRequest) -> ReplyResponse:
    try:
        assistant_text = await llm.chat(
            req.message.strip(),
            [{"role": t.role, "content": t.content} for t in req.history],
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        audio_b64 = await _text_to_audio_b64(assistant_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}") from e
    return ReplyResponse(text=assistant_text, audio_base64=audio_b64)


@app.post("/api/tts")
async def tts_endpoint(req: TtsRequest) -> Response:
    """Synthesize speech for frontend Audio playback."""
    try:
        audio = await tts.text_to_mp3_bytes(req.text.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}") from e
    if not audio:
        raise HTTPException(status_code=400, detail="Empty TTS result")
    return Response(content=audio, media_type=tts.output_mime_type())


@app.get("/api/config")
async def config() -> dict[str, Any]:
    w = stt.whisper_status()
    return {
        "model": llm.OLLAMA_MODEL,
        "tts_engine": tts.TTS_ENGINE,
        "tts_voice": TTS_VOICE,
        "tts_mime": tts.output_mime_type(),
        "doubao_configured": __import__(
            "services.tts_doubao", fromlist=["doubao_configured"]
        ).doubao_configured(),
        "piper_voices": __import__(
            "services.tts_piper", fromlist=["list_ready_voices"]
        ).list_ready_voices(),
        "stt": "whisper",
        "whisper_model": w.get("model"),
        "ws_path": "/ws/call",
        "duplex": True,
        "teaching_guide": teaching_status(),
    }


_STATIC_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".ico", ".woff", ".woff2"}
)

_STATIC_MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def _file_response(path: Path) -> FileResponse:
    media_type = _STATIC_MEDIA_TYPES.get(path.suffix.lower())
    no_cache_names = {"index.html", "sw.js"}
    headers = (
        {"Cache-Control": "no-cache, no-store, must-revalidate"}
        if path.name in no_cache_names
        or path.name.startswith("workbox-")
        or path.suffix.lower() == ".webmanifest"
        else None
    )
    if media_type:
        return FileResponse(path, media_type=media_type, headers=headers)
    return FileResponse(path, headers=headers)


def _mount_frontend() -> None:
    """Serve built Vue app when frontend/dist exists (production / launchd)."""
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        return

    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    characters = FRONTEND_DIST / "characters"
    if characters.is_dir():
        app.mount(
            "/characters",
            StaticFiles(directory=characters),
            name="frontend-characters",
        )

    def _serve_spa_root(request: Request) -> FileResponse | RedirectResponse:
        if URL_PREFIX:
            # Direct :18787/english/ — prefix stripped by middleware.
            if request.scope.get("english_buddy_stripped_prefix"):
                return _file_response(index)
            # Caddy handle_path already stripped /english — do not redirect again.
            if request.headers.get("x-forwarded-host"):
                return _file_response(index)
            return RedirectResponse(url=f"{URL_PREFIX}/", status_code=307)
        return _file_response(index)

    @app.get("/")
    async def spa_root(request: Request):
        return _serve_spa_root(request)

    @app.get("/{path:path}")
    async def spa_fallback(path: str) -> FileResponse:
        if path.startswith("api") or path.startswith("ws"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / path
        if candidate.is_file():
            return _file_response(candidate)
        # Missing avatar/asset must not return index.html (breaks <img>/<picture>).
        if Path(path).suffix.lower() in _STATIC_SUFFIXES:
            raise HTTPException(status_code=404, detail="Not found")
        return _file_response(index)


_mount_frontend()
