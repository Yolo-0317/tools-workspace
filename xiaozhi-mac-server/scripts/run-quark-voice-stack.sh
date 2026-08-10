#!/usr/bin/env bash
# Start xiaozhi-mac-server for Mode A: local WS + DeepSeek MCP tools + Quark Opus play.
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

export USE_MCP_TOOLS="${USE_MCP_TOOLS:-true}"
export QUARK_STREAM_ENABLED="${QUARK_STREAM_ENABLED:-true}"

LAN_IP="$(python -c 'from server.config import settings; print(settings.lan_ip)')"
HTTP_PORT="${HTTP_PORT:-8766}"
WS_PORT="${WS_PORT:-8765}"

echo "=== Quark voice stack (Mode A) ==="
echo "USE_MCP_TOOLS=$USE_MCP_TOOLS"
echo "OTA  : http://${LAN_IP}:${HTTP_PORT}/xiaozhi/ota/"
echo "WS   : ws://${LAN_IP}:${WS_PORT}"
echo "MCP  : http://${LAN_IP}:${HTTP_PORT}/api/mcp/status"
echo
echo "Device must use the OTA URL above (not xiaozhi.me cloud)."
echo "Flash helper:  cd ../xiaozhi-atoms3r && bash scripts/flash-local-ota.sh"
echo "Doctor:        bash scripts/check-quark-mcp.sh"
echo
echo "Say: 想听儿童故事 / 想听冰雪奇缘"
echo

exec python server/main.py
