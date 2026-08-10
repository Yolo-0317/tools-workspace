#!/usr/bin/env python3
"""Static server for HarryPutter (launchd :8791, Caddy /harryputter/*)."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

mimetypes.add_type("application/manifest+json", ".webmanifest")

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from auth import (  # noqa: E402
    auth_enabled,
    clear_session_cookie_headers,
    issue_session,
    read_json_body,
    session_user_from_headers,
    verify_login,
)
from dict_lookup import lookup as dict_lookup  # noqa: E402
from env_config import hp_env  # noqa: E402

PORT = int(hp_env("PORT", "8791"))
HOST = hp_env("HOST", "127.0.0.1")
MAX_PUBLIC_CHAPTER = int(hp_env("MAX_PUBLIC_CHAPTER", "1"))
FULL_ACCESS_PREFIXES = tuple(
    p.strip()
    for p in hp_env("FULL_ACCESS_CIDRS", "127.,10.,192.168.,172.16.,::1").split(",")
    if p.strip()
)
_CHAPTER_RE = re.compile(r"(?:chapter(\d{2})\.mp3|/ch(\d{2})\.json)")
_DEMO_SENSITIVE_RE = re.compile(
    r"(\.epub$|/ch\d{2}_(?:words|sentences|zh)\.json$|/data/book01_chapters\.json$)"
)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _client_ip(self) -> str:
        fwd = self.headers.get("X-Forwarded-For") or self.headers.get("X-Real-IP") or ""
        if fwd:
            return fwd.split(",")[0].strip()
        return self.client_address[0]

    def _lan_access(self) -> bool:
        ip = self._client_ip()
        return any(ip.startswith(p) or ip == p for p in FULL_ACCESS_PREFIXES)

    def _session_user(self) -> str | None:
        return session_user_from_headers(self.headers)

    def _has_full_access(self) -> bool:
        if MAX_PUBLIC_CHAPTER <= 0:
            return True
        if self._session_user():
            return True
        return self._lan_access()

    def _chapter_from_path(self, path: str) -> int | None:
        m = _CHAPTER_RE.search(path)
        if not m:
            return None
        return int(m.group(1) or m.group(2))

    def _path_restricted(self, path: str) -> bool:
        if self._has_full_access():
            return False
        if self._chapter_from_path(path) is not None:
            ch = self._chapter_from_path(path)
            return ch is not None and ch > MAX_PUBLIC_CHAPTER
        return bool(_DEMO_SENSITIVE_RE.search(path))

    def _app_config(self) -> dict:
        user = self._session_user()
        full = self._has_full_access()
        return {
            "ok": True,
            "requireAuth": auth_enabled(),
            "loggedIn": user is not None,
            "username": user,
            "maxPublicChapter": 0 if full else MAX_PUBLIC_CHAPTER,
            "fullAccess": full,
            "demoHint": ("各部试读第 1 章" if not full else ""),
        }

    def _catalog_path_for_request(self) -> Path:
        qs = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        book = (qs.get("book") or [""])[0].strip()
        if book and re.fullmatch(r"hp\d{2}", book):
            p = ROOT / "output" / book / "catalog.json"
            if p.is_file():
                return p
        legacy = ROOT / "output" / "catalog.json"
        if legacy.is_file():
            return legacy
        return ROOT / "output" / "hp01" / "catalog.json"

    def _filtered_catalog(self) -> dict:
        catalog_path = self._catalog_path_for_request()
        if not catalog_path.is_file():
            self._send_json({"error": "catalog_not_found"}, HTTPStatus.NOT_FOUND)
            return {}
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        if self._has_full_access():
            return data
        out = dict(data)
        chapters = []
        ready = 0
        for ch in data.get("chapters") or []:
            item = dict(ch)
            if item.get("id", 0) > MAX_PUBLIC_CHAPTER:
                item["ready"] = False
                item["locked"] = True
            elif item.get("ready"):
                ready += 1
            chapters.append(item)
        out["chapters"] = chapters
        out["ready_count"] = ready
        out["demo_max_chapter"] = MAX_PUBLIC_CHAPTER
        return out

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        return self.rfile.read(length) if length > 0 else b""

    def _send_json(self, payload: dict, code: int = 200, extra_headers: list[tuple[str, str]] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_head(self):
        """HTTP Range for audio seek (stdlib SimpleHTTP on 3.9 lacks this)."""
        path = self.path.split("?", 1)[0]
        if self._path_restricted(path):
            self.send_error(HTTPStatus.FORBIDDEN, "access denied")
            return None
        range_header = self.headers.get("Range")
        if range_header:
            fpath = self.translate_path(self.path)
            if os.path.isfile(fpath):
                ctype = self.guess_type(fpath)
                try:
                    f = open(fpath, "rb")
                except OSError:
                    self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                    return None
                fs = os.fstat(f.fileno())
                return self._send_partial_file(fpath, f, fs.st_size, ctype)
        return super().send_head()

    def _write_bytes(self, file, nbytes: int) -> None:
        remaining = nbytes
        while remaining > 0:
            chunk = file.read(min(64 * 1024, remaining))
            if not chunk:
                break
            self.wfile.write(chunk)
            remaining -= len(chunk)

    def _send_partial_file(self, path: str, file, file_size: int, ctype: str):
        try:
            match = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
            if not match:
                raise ValueError("bad range")
            first, last = match.groups()
            if first == "":
                first_byte = max(0, file_size - int(last))
                last_byte = file_size - 1
            else:
                first_byte = int(first)
                last_byte = int(last) if last else file_size - 1
            if first_byte >= file_size or first_byte > last_byte:
                raise ValueError("range out of bounds")
            last_byte = min(last_byte, file_size - 1)
            length = last_byte - first_byte + 1
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-type", ctype)
            self.send_header(
                "Content-Range",
                f"bytes {first_byte}-{last_byte}/{file_size}",
            )
            self.send_header("Content-Length", str(length))
            self.end_headers()
            if self.command != "HEAD":
                file.seek(first_byte)
                self._write_bytes(file, length)
                file.close()
                return None
            return file
        except (ValueError, OSError):
            file.close()
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            return None

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path.rstrip("/") == "/api/health":
            self._send_json({"ok": True, "service": "harryputter"})
            return
        if path.rstrip("/") == "/api/config":
            self._send_json(self._app_config())
            return
        if path.rstrip("/") == "/api/auth/me":
            user = self._session_user()
            if not user:
                self._send_json({"ok": False, "loggedIn": False}, HTTPStatus.UNAUTHORIZED)
                return
            self._send_json({"ok": True, "loggedIn": True, "username": user})
            return
        if path == "/api/dict":
            qs = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
            word = (qs.get("word") or [""])[0]
            payload = dict_lookup(word)
            body = json.dumps(payload, ensure_ascii=False).encode()
            code = 200 if payload.get("ok") else 404
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/output/library.json":
            lib = ROOT / "output" / "library.json"
            if lib.is_file():
                self._send_json(json.loads(lib.read_text(encoding="utf-8")))
            else:
                self._send_json({"default_book_id": "hp01", "books": []})
            return
        if path == "/output/catalog.json":
            payload = self._filtered_catalog()
            if payload:
                self._send_json(payload)
            return
        if self._path_restricted(path):
            self._send_json(
                {
                    "ok": False,
                    "error": "chapter_locked",
                    "hint": "该章未开放试读",
                    "maxPublicChapter": MAX_PUBLIC_CHAPTER,
                    "requireAuth": auth_enabled(),
                },
                HTTPStatus.FORBIDDEN,
            )
            return
        if path == "/web" or path == "/web/":
            self.path = "/web/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path.rstrip("/") == "/api/auth/login":
            if not auth_enabled():
                self._send_json({"ok": False, "error": "auth_disabled"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            data = read_json_body(self._read_body())
            username = str(data.get("username") or "").strip()
            password = str(data.get("password") or "")
            if not verify_login(username, password):
                self._send_json({"ok": False, "error": "invalid_credentials"}, HTTPStatus.UNAUTHORIZED)
                return
            token, cookie_headers = issue_session(username)
            self._send_json(
                {"ok": True, "username": username, "loggedIn": True, "token": token},
                extra_headers=[("Set-Cookie", h) for h in cookie_headers],
            )
            return
        if path.rstrip("/") == "/api/auth/refresh":
            user = self._session_user()
            if not user:
                self._send_json({"ok": False, "loggedIn": False}, HTTPStatus.UNAUTHORIZED)
                return
            token, cookie_headers = issue_session(user)
            self._send_json(
                {"ok": True, "username": user, "loggedIn": True, "token": token},
                extra_headers=[("Set-Cookie", h) for h in cookie_headers],
            )
            return
        if path.rstrip("/") == "/api/auth/logout":
            self._send_json(
                {"ok": True, "loggedIn": False},
                extra_headers=[("Set-Cookie", h) for h in clear_session_cookie_headers()],
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def end_headers(self) -> None:
        path = self.path.split("?", 1)[0]
        if path.endswith("/sw.js"):
            self.send_header("Cache-Control", "no-cache")
        translated = self.translate_path(path)
        if os.path.isfile(translated):
            ctype = self.guess_type(translated)
            if ctype.startswith("audio/") or ctype.startswith("video/"):
                self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        if args and str(args[0]).startswith("GET /api/health"):
            return
        super().log_message(fmt, *args)


def main() -> None:
    os.chdir(ROOT)
    if not auth_enabled():
        print("WARN: HARRYPUTTER_ADMIN_PASSWORD unset — login disabled", flush=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    mode = "full" if MAX_PUBLIC_CHAPTER <= 0 else f"demo≤ch{MAX_PUBLIC_CHAPTER}+login"
    print(f"harryputter http://{HOST}:{PORT}/web/ ({mode})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
