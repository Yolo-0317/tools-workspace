#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Run bash scripts/install.sh first" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source .env
set +a

if [[ -z "${MCP_ENDPOINT:-}" ]]; then
  echo "Set MCP_ENDPOINT in .env from xiaozhi.me console (MCP WebSocket URL with token)." >&2
  echo "Mode A (no cloud MCP) instead: bash scripts/run-quark-voice-stack.sh" >&2
  exit 1
fi

LAN_IP="$(python -c 'from server.config import settings; print(settings.lan_ip)')"
export XIAOZHI_GATEWAY="${XIAOZHI_GATEWAY:-http://${LAN_IP}:8766}"

echo "Gateway: $XIAOZHI_GATEWAY"
echo "MCP endpoint: $MCP_ENDPOINT"
echo "Note: play still needs the device on local WS (OTA -> this gateway)."
echo "Starting quark-audio MCP pipe..."

exec python scripts/mcp_pipe.py quark-audio
