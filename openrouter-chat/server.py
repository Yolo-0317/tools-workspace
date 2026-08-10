#!/usr/bin/env python3
"""Minimal OpenRouter streaming chat — bind localhost only, no chat persistence."""

from __future__ import annotations

import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8795
DEFAULT_MODEL = "sao10k/l3.1-euryale-70b"
ST_SECRETS = (
    ROOT.parent
    / "sillytavern-mac"
    / "vendor"
    / "SillyTavern"
    / "data"
    / "default-user"
    / "secrets.json"
)


def resolve_api_key() -> str:
    env_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if env_key:
        return env_key
    if not ST_SECRETS.is_file():
        raise RuntimeError(
            "OPENROUTER_API_KEY not set and SillyTavern secrets.json missing"
        )
    data = json.loads(ST_SECRETS.read_text(encoding="utf-8") or "{}")
    entries = data.get("api_key_openrouter") or []
    for entry in entries:
        if entry.get("active") and entry.get("value"):
            return str(entry["value"]).strip()
    for entry in entries:
        if entry.get("value"):
            return str(entry["value"]).strip()
    raise RuntimeError("No OpenRouter API key in env or SillyTavern secrets.json")


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenRouterPlainChat/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, code: int, message: str) -> None:
        payload = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self._send(code, payload, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            target = STATIC / "index.html"
        elif path == "/api/health":
            try:
                resolve_api_key()
                ok = True
                detail = "ok"
            except RuntimeError as exc:
                ok = False
                detail = str(exc)
            body = json.dumps(
                {"ok": ok, "detail": detail, "default_model": DEFAULT_MODEL},
                ensure_ascii=False,
            ).encode("utf-8")
            self._send(200 if ok else 503, body, "application/json; charset=utf-8")
            return
        else:
            # only serve files under static/
            rel = path.lstrip("/")
            target = (STATIC / rel).resolve()
            if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
                self._json_error(404, "not found")
                return

        data = target.read_bytes()
        ctype = "text/html; charset=utf-8"
        if target.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif target.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        self._send(200, data, ctype)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/api/chat":
            self._json_error(404, "not found")
            return

        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_error(400, "invalid JSON")
            return

        messages = req.get("messages")
        if not isinstance(messages, list) or not messages:
            self._json_error(400, "messages required")
            return

        model = (req.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
        temperature = req.get("temperature", 0.9)
        max_tokens = req.get("max_tokens", 1024)

        try:
            api_key = resolve_api_key()
        except RuntimeError as exc:
            self._json_error(503, str(exc))
            return

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "HTTP-Referer": f"http://127.0.0.1:{os.environ.get('CHAT_PORT', str(DEFAULT_PORT))}/",
            "X-Title": "openrouter-plain-chat",
            "Connection": "close",
        }

        headers_sent = False
        conn: Optional[http.client.HTTPSConnection] = None
        try:
            print(f"chat → {model} ({len(messages)} msgs)", flush=True)
            conn = http.client.HTTPSConnection("openrouter.ai", timeout=120)
            conn.request("POST", "/api/v1/chat/completions", body=body, headers=headers)
            resp = conn.getresponse()
            if resp.status >= 400:
                err_body = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(err_body)
                    msg = (
                        parsed.get("error", {}).get("message")
                        or parsed.get("error")
                        or err_body
                    )
                    if isinstance(msg, dict):
                        msg = msg.get("message") or json.dumps(msg, ensure_ascii=False)
                except json.JSONDecodeError:
                    msg = err_body or resp.reason
                self._json_error(resp.status, f"OpenRouter {resp.status}: {msg}")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            headers_sent = True

            while True:
                line = resp.readline()
                if not line:
                    break
                self.wfile.write(line)
                self.wfile.flush()
                if line.strip() == b"data: [DONE]":
                    break
            print(f"chat done ← {model}", flush=True)
        except Exception as exc:
            text = f"upstream error: {exc}"
            print(text, flush=True)
            if headers_sent:
                try:
                    self.wfile.write(
                        f"data: {json.dumps({'error': text}, ensure_ascii=False)}\n\n".encode(
                            "utf-8"
                        )
                    )
                    self.wfile.flush()
                except Exception:
                    pass
            else:
                self._json_error(502, text)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def main() -> None:
    # Line-buffered logs when started from scripts
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    host = os.environ.get("CHAT_HOST", DEFAULT_HOST)
    port = int(os.environ.get("CHAT_PORT", str(DEFAULT_PORT)))
    try:
        resolve_api_key()
        key_src = "env" if os.environ.get("OPENROUTER_API_KEY") else "sillytavern secrets"
        print(f"OpenRouter key: {key_src}", flush=True)
    except RuntimeError as exc:
        print(f"Warning: {exc}", flush=True)
        print("Set OPENROUTER_API_KEY or configure SillyTavern OpenRouter first.", flush=True)

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"OpenRouter plain chat: http://{host}:{port}/", flush=True)
    print(f"Default model: {DEFAULT_MODEL}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
