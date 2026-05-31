"""Home Hub FastAPI 入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import ROOT, settings
from backend.routers import chat, dashboard, services
from backend.services import chat_store
from backend.services.chat_agent import chat_agent_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    chat_store.init_db()
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


@app.middleware("http")
async def optional_api_token(request: Request, call_next):
    token = settings.api_token
    if token and request.url.path.startswith("/api/"):
        header = request.headers.get("X-Hub-Token", "")
        if header != token:
            return JSONResponse(status_code=401, content={"detail": "未授权"})
    return await call_next(request)


app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(services.router)

FRONTEND_DIST = ROOT / "frontend" / "dist"


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "chat": chat_agent_service.health(),
    }


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(status_code=404, content={"detail": "frontend not built"})
