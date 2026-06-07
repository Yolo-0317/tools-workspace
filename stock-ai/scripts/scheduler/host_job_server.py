#!/usr/bin/env python3
"""本机任务执行器：Docker scheduler 经 host.docker.internal 触发需 OpenCLI / 微信的脚本。"""

from __future__ import annotations

import hmac
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
PORT = int(os.getenv("HOST_JOB_PORT", "9876"))
TOKEN = os.getenv("HOST_JOB_TOKEN", "").strip()
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _job_command(name: str, body: dict) -> list[str] | None:
    if name == "selection":
        return ["/bin/bash", str(ROOT / "push_selection_wechat.sh")]
    if name == "monitor":
        return ["/bin/bash", str(ROOT / "push_holdings_monitor.sh"), "--push"]
    if name == "news-sync":
        return ["/bin/bash", str(ROOT / "sync_macro_news.sh")]
    if name == "advisor-weekly":
        return ["/bin/bash", str(ROOT / "push_advisor_weekly_review.sh")]
    return None


def _authorized(headers) -> bool:
    if not TOKEN:
        return True
    got = headers.get("X-Job-Token", "")
    return hmac.compare_digest(got, TOKEN)


class JobHandler(BaseHTTPRequestHandler):
    server_version = "StockAIHostJobs/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[host-jobs] {self.address_string()} - {fmt % args}\n")

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._json(200, {"ok": True, "root": str(ROOT)})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not _authorized(self.headers):
            self._json(401, {"error": "unauthorized"})
            return

        parts = [p for p in unquote(self.path).split("/") if p]
        if len(parts) != 2 or parts[0] != "run":
            self._json(404, {"error": "use POST /run/{job}"})
            return

        job = parts[1].strip().lower()
        body: dict = {}
        length = int(self.headers.get("Content-Length") or 0)
        if length > 0:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json body"})
                return

        cmd = _job_command(job, body)
        if cmd is None:
            self._json(404, {"error": f"unknown job: {job}"})
            return

        env = os.environ.copy()
        env["STOCK_AI_ROOT"] = str(ROOT)
        env["PYTHONPATH"] = str(ROOT) + (f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else "")
        if (ROOT / ".env").is_file():
            # 子进程 bash 脚本会自行 source .env
            pass

        log_file = LOG_DIR / f"host-job-{job}.log"
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"\n===== {job} start =====\n")
            fh.flush()
            proc = subprocess.run(
                cmd,
                cwd=ROOT,
                env=env,
                stdout=fh,
                stderr=subprocess.STDOUT,
                check=False,
            )
            fh.write(f"===== exit {proc.returncode} =====\n")

        if proc.returncode != 0:
            self._json(500, {"error": "job failed", "job": job, "exit_code": proc.returncode})
            return
        self._json(200, {"ok": True, "job": job})

    def _json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    if not ROOT.is_dir():
        print(f"❌ stock-ai 根目录不存在: {ROOT}", file=sys.stderr)
        return 1
    host = os.getenv("HOST_JOB_BIND", "127.0.0.1")
    httpd = ThreadingHTTPServer((host, PORT), JobHandler)
    print(f"[host-jobs] listening http://{host}:{PORT}  root={ROOT}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
