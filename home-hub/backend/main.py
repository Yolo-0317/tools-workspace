"""Home Hub FastAPI 入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from backend.config import ROOT, settings
from backend.middleware.url_prefix import StripUrlPrefixMiddleware
from backend.routers import auth, dashboard, services
from backend.services import hub_auth, public_news_guard, session_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_store.init_db()
    session_store.purge_expired()
    yield


app = FastAPI(title="Home Hub", lifespan=lifespan)

if settings.url_prefix:
    app.add_middleware(StripUrlPrefixMiddleware, prefix=settings.url_prefix)

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


def _api_token_ok(request: Request) -> bool:
    if not settings.api_token:
        return False
    return request.headers.get("X-Hub-Token", "") == settings.api_token


@app.middleware("http")
async def hub_session_auth(request: Request, call_next):
    username, role = _resolve_request_identity(request)
    request.state.hub_user = username
    request.state.hub_role = role

    path = request.url.path
    from backend.config import settings

    if settings.news_enabled and public_news_guard.is_public_news_path(path):
        blocked = public_news_guard.check_public_news_request(
            request,
            authenticated=role is not None,
            api_token_ok=_api_token_ok(request),
        )
        if blocked is not None:
            return blocked

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
    ".txt": "text/plain; charset=utf-8",
}


def _static_file_response(path: Path) -> FileResponse:
    media_type = _STATIC_MEDIA_TYPES.get(path.suffix.lower())
    name = path.name.lower()
    headers: dict[str, str] | None = None
    if name in {"index.html", "sw.js"} or name.startswith("workbox-"):
        headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    elif path.suffix.lower() == ".webmanifest":
        headers = {"Cache-Control": "no-cache, must-revalidate"}
    if media_type:
        return FileResponse(path, media_type=media_type, headers=headers)
    return FileResponse(path, headers=headers)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "auth_required": settings.require_auth,
    }


if FRONTEND_DIST.is_dir():
    dist_root = FRONTEND_DIST.resolve()
    _PREFIX = settings.url_prefix

    def _serve_index(request: Request) -> FileResponse:
        index = FRONTEND_DIST / "index.html"
        return FileResponse(
            index,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    @app.get("/")
    async def spa_root(request: Request):
        if _PREFIX and not request.scope.get("hub_stripped_prefix"):
            if not request.headers.get("x-forwarded-host"):
                return RedirectResponse(url=f"{_PREFIX}/", status_code=307)
        return _serve_index(request)

    @app.get("/{full_path:path}")
    async def spa(full_path: str, request: Request):
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
            if full_path.startswith("assets/"):
                return JSONResponse(status_code=404, content={"detail": "asset not found"})

        return _serve_index(request)
