"""Strip /hub URL prefix for direct :8780 access (Caddy handle_path already strips)."""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send


class StripUrlPrefixMiddleware:
    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            if path == self.prefix or path.startswith(f"{self.prefix}/"):
                scope["hub_stripped_prefix"] = True
                scope["path"] = path[len(self.prefix) :] or "/"
        await self.app(scope, receive, send)
