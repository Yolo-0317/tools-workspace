#!/usr/bin/env bash
# Check Quark + MCP gateway readiness for Xiaozhi voice playback.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "FAIL: missing .venv — run: bash scripts/install.sh" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source .env
set +a

python - <<'PY'
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from server.config import settings
from server.quark_client import QuarkClient

ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok
    mark = "OK" if cond else "FAIL"
    if not cond:
        ok = False
    extra = f" — {detail}" if detail else ""
    print(f"[{mark}] {name}{extra}")


print("=== Quark / MCP doctor ===")
print(f"LAN IP     : {settings.lan_ip}")
print(f"OTA URL    : {settings.ota_url}")
print(f"WS URL     : {settings.ws_url}")
print(f"USE_MCP    : {settings.use_mcp_tools}")
print(f"MCP_ENDPOINT set: {bool(settings.mcp_endpoint)}")
print()

client = QuarkClient.from_env()
check("Quark client", client is not None, "skill login / .env paths")
if client is not None:
    try:
        hits = client.search_audio("故事", limit=2)
        check("Quark search", bool(hits), f"{len(hits)} hit(s)")
    except Exception as exc:
        check("Quark search", False, str(exc))

gateway = f"http://127.0.0.1:{settings.http_port}"
try:
    with urllib.request.urlopen(f"{gateway}/api/mcp/status", timeout=2) as resp:
        body = json.loads(resp.read().decode())
    devices = body.get("devices") or {}
    connected = int(devices.get("connected") or 0) if isinstance(devices, dict) else len(devices)
    check("Gateway /api/mcp/status", True, f"connected={connected}")
    check(
        "Device on local WS",
        connected > 0,
        "flash local OTA then power Pyramid" if connected == 0 else str(devices),
    )
except urllib.error.URLError as exc:
    check("Gateway running", False, f"start: bash scripts/run-quark-voice-stack.sh ({exc})")

if not settings.use_mcp_tools:
    print("[WARN] USE_MCP_TOOLS is false — set true in .env for Mode A voice play tools")

print()
sys.exit(0 if ok else 1)
PY
