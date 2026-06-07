#!/usr/bin/env python3
"""Static server for readalong (launchd :8791, Caddy /readalong/*)."""

from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("READALONG_PORT", "8791"))
HOST = os.environ.get("READALONG_HOST", "127.0.0.1")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path.rstrip("/") == "/api/health":
            body = json.dumps({"ok": True, "service": "readalong"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # Never 301 → /web/ (breaks Caddy /readalong/* strip; browser lands on /hub/web/).
        if path == "/web" or path == "/web/":
            self.path = "/web/index.html"
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        # Quieter logs for launchd.
        if args and str(args[0]).startswith("GET /api/health"):
            return
        super().log_message(fmt, *args)


def main() -> None:
    os.chdir(ROOT)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"readalong static server http://{HOST}:{PORT}/web/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
