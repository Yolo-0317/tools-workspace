"""Home Hub FastAPI 入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.config import ROOT, settings
from backend.routers import auth, chat, dashboard, services
from backend.services import chat_store, hub_auth, session_store
from backend.services.chat_agent import chat_agent_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    chat_store.init_db()
    session_store.init_db()
    session_store.purge_expired()
    await chat_agent_service.startup()
    yield
    await chat_agent_service.shutdown()


app = FastAPI(title="Home Hub", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_request_identity(request: Request) -> tuple[str | None, str | None]:
    """返回 (username, role)。"""
    if settings.api_token:
        header = request.headers.get("X-Hub-Token", "")
        if header == settings.api_token:
            return "api-token", "admin"

    if not settings.require_auth:
        return None, "admin"

    token = request.cookies.get(hub_auth.SESSION_COOKIE, "")
    session = session_store.get_session(token)
    if not session:
        return None, None
    return session["username"], session["role"]


@app.middleware("http")
async def hub_session_auth(request: Request, call_next):
    username, role = _resolve_request_identity(request)
    request.state.hub_user = username
    request.state.hub_role = role

    path = request.url.path
    if path.startswith("/api/"):
        if not hub_auth.public_api_allowed(path):
            if role is None:
                return JSONResponse(status_code=401, content={"detail": "未登录"})
            if role == "share" and not hub_auth.share_api_allowed(path, request.method):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "分享账号仅可查看选股数据"},
                )

    return await call_next(request)


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(services.router)

FRONTEND_DIST = ROOT / "frontend" / "dist"

_STATIC_MEDIA_TYPES = {
    ".webmanifest": "application/manifest+json",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def _static_file_response(path: Path) -> FileResponse:
    media_type = _STATIC_MEDIA_TYPES.get(path.suffix.lower())
    if media_type:
        return FileResponse(path, media_type=media_type)
    return FileResponse(path)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "auth_required": settings.require_auth,
        "chat": chat_agent_service.health(),
    }


if FRONTEND_DIST.is_dir():
    dist_root = FRONTEND_DIST.resolve()

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            try:
                candidate.relative_to(dist_root)
            except ValueError:
                candidate = None
            if candidate is not None and candidate.is_file():
                return _static_file_response(candidate)

        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(
                index,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        return JSONResponse(status_code=404, content={"detail": "frontend not built"})
