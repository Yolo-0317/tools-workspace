"""HTTP endpoints: OTA config for real devices + health check."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from aiohttp import web

from server.config import settings
from server.http_stream import register_stream_routes
from server.mcp_api import register_mcp_routes
from server.media_api import register_media_routes
from server.web_api import register_web_demo_routes

log = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# Shared app instance (WebSocket playback caches stream sources here).
APP = web.Application()


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "ws_url": settings.ws_url})


async def ota_check(_: web.Request) -> web.Response:
    """Return websocket URL/token for xiaozhi-esp32 OTA polling."""
    body = {
        "websocket": {
            "url": settings.ws_url,
            "token": settings.token,
            "version": 1,
        },
        "firmware": {
            "version": "2.4.0",
            "url": "",
        },
        "server_time": {
            "timestamp": int(__import__("time").time() * 1000),
            "timezone_offset": 480,
        },
    }
    log.debug("OTA response: %s", json.dumps(body, ensure_ascii=False))
    return web.json_response(body)


def create_app() -> web.Application:
    return APP


def _setup_routes(app: web.Application) -> None:
    app.router.add_get("/health", health)
    app.router.add_post("/xiaozhi/ota/", ota_check)
    app.router.add_get("/xiaozhi/ota/", ota_check)
    register_stream_routes(app)
    register_mcp_routes(app)
    register_media_routes(app)
    register_web_demo_routes(app, _WEB_DIR)


_setup_routes(APP)


async def run_http_server() -> None:
    runner = web.AppRunner(APP)
    await runner.setup()
    site = web.TCPSite(runner, settings.host, settings.http_port)
    await site.start()
    log.info("HTTP OTA listening on http://%s:%s/xiaozhi/ota/", settings.host, settings.http_port)
    log.info(
        "Quark stream proxy: http://%s:%s/stream/quark/{fid}",
        settings.lan_ip,
        settings.http_port,
    )
    log.info(
        "Device MP3: http://%s:%s/stream/quark/{fid}/device.mp3",
        settings.lan_ip,
        settings.http_port,
    )
    log.info(
        "Media API: http://%s:%s/api/media/status",
        settings.lan_ip,
        settings.http_port,
    )
    if not settings.media_only:
        log.info(
            "Web demo: http://%s:%s/demo/",
            settings.lan_ip,
            settings.http_port,
        )
    log.info(
        "MCP bridge API: http://%s:%s/api/mcp/status (use_mcp_tools=%s media_only=%s)",
        settings.lan_ip,
        settings.http_port,
        settings.use_mcp_tools,
        settings.media_only,
    )
