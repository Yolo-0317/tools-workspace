#!/usr/bin/env python3
"""Baidu Netdisk OAuth (authorization_code) → write tokens into .env.

Prereq: BAIDU_APP_KEY / BAIDU_SECRET_KEY / BAIDU_REDIRECT_URI in .env
        and the same redirect_uri configured in pan.baidu.com union console.

Usage:
  cd xiaozhi-mac-server
  .venv/bin/python scripts/baidu_oauth.py
"""

from __future__ import annotations

import re
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
from dotenv import load_dotenv
import os

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

APP_KEY = os.getenv("BAIDU_APP_KEY", "").strip()
SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "").strip()
REDIRECT_URI = os.getenv(
    "BAIDU_REDIRECT_URI", "http://127.0.0.1:8766/oauth/baidu/callback"
).strip()
ENV_PATH = _ROOT / ".env"


def _upsert_env(key: str, value: str) -> None:
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    line = f"{key}={value}"
    if re.search(rf"^{re.escape(key)}=", text, flags=re.M):
        text = re.sub(rf"^{re.escape(key)}=.*$", line, text, flags=re.M)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    ENV_PATH.write_text(text, encoding="utf-8")


def _parse_redirect(uri: str) -> tuple[str, int, str]:
    u = urllib.parse.urlparse(uri)
    host = u.hostname or "127.0.0.1"
    port = u.port or (443 if u.scheme == "https" else 80)
    path = u.path or "/"
    return host, port, path


class _Handler(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path != self.server.expect_path:  # type: ignore[attr-defined]
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        if "error" in qs:
            _Handler.error = qs["error"][0]
            body = b"<h1>Auth failed</h1><p>You can close this tab.</p>"
        else:
            _Handler.code = (qs.get("code") or [None])[0]
            body = b"<h1>OK</h1><p>Authorization code received. Close this tab.</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
        threading.Thread(target=self.server.shutdown, daemon=True).start()  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return


def main() -> int:
    if not APP_KEY or not SECRET_KEY:
        print("Set BAIDU_APP_KEY and BAIDU_SECRET_KEY in .env first.", file=sys.stderr)
        return 1

    host, port, path = _parse_redirect(REDIRECT_URI)
    if host not in {"127.0.0.1", "localhost"}:
        print(
            f"REDIRECT_URI host is {host!r}; this script only binds localhost.",
            file=sys.stderr,
        )
        return 1

    auth_url = (
        "https://openapi.baidu.com/oauth/2.0/authorize?"
        + urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": APP_KEY,
                "redirect_uri": REDIRECT_URI,
                "scope": "basic,netdisk",
                "display": "popup",
            }
        )
    )

    httpd = HTTPServer((host, port), _Handler)
    httpd.expect_path = path  # type: ignore[attr-defined]
    print(f"Listening on {REDIRECT_URI}")
    print("Open this URL in a browser (will try to open automatically):\n")
    print(auth_url)
    print()
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    httpd.serve_forever()
    httpd.server_close()

    if _Handler.error or not _Handler.code:
        print(f"Auth failed: {_Handler.error or 'no code'}", file=sys.stderr)
        return 1

    print("Exchanging code for tokens...")
    r = httpx.get(
        "https://openapi.baidu.com/oauth/2.0/token",
        params={
            "grant_type": "authorization_code",
            "code": _Handler.code,
            "client_id": APP_KEY,
            "client_secret": SECRET_KEY,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30.0,
    )
    data = r.json()
    if "access_token" not in data:
        print(f"Token exchange failed: {data}", file=sys.stderr)
        return 1

    access = data["access_token"]
    refresh = data.get("refresh_token", "")
    expires = data.get("expires_in", "?")
    _upsert_env("BAIDU_ACCESS_TOKEN", access)
    if refresh:
        _upsert_env("BAIDU_REFRESH_TOKEN", refresh)

    print(f"Wrote BAIDU_ACCESS_TOKEN / BAIDU_REFRESH_TOKEN to {ENV_PATH}")
    print(f"expires_in={expires}s  scope={data.get('scope', '')}")

    # quick sanity
    u = httpx.get(
        "https://pan.baidu.com/rest/2.0/xpan/nas",
        params={"method": "uinfo", "access_token": access},
        timeout=30.0,
    )
    info = u.json()
    if info.get("errno", 0) == 0 or "baidu_name" in info or "uk" in info:
        print(f"uinfo OK: baidu_name={info.get('baidu_name')} uk={info.get('uk')}")
    else:
        print(f"uinfo unexpected: {info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
