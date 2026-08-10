#!/usr/bin/env bash
# Cloud+HTTP media stack: thin HTTP (transcode + /api/media) + optional MCP pipe.
# Mutually exclusive with full Mode A dialogue gateway (MEDIA_ONLY=false + WS).
#
# Usage:
#   bash scripts/run-media-stack.sh           # HTTP only
#   bash scripts/run-media-stack.sh --with-mcp  # also start mcp_pipe (needs MCP_ENDPOINT)
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

export MEDIA_ONLY=true
export USE_MCP_TOOLS=false
HTTP_PORT="${HTTP_PORT:-8766}"
WITH_MCP=false
if [[ "${1:-}" == "--with-mcp" ]]; then
  WITH_MCP=true
fi

LAN_IP="$(python -c 'from server.config import settings; print(settings.lan_ip)')"
export XIAOZHI_GATEWAY="${XIAOZHI_GATEWAY:-http://${LAN_IP}:${HTTP_PORT}}"

echo "=== xiaozhi-media (MEDIA_ONLY) ==="
echo "GATEWAY: $XIAOZHI_GATEWAY"
echo "Device MP3: $XIAOZHI_GATEWAY/stream/quark/{fid}/device.mp3"
echo "Resolve API: POST $XIAOZHI_GATEWAY/api/media/resolve"
echo

if curl -sS -m 1 "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
  echo "HTTP already up on :${HTTP_PORT}"
else
  echo "Starting media HTTP..."
  nohup env MEDIA_ONLY=true USE_MCP_TOOLS=false python -u server/main.py \
    >/tmp/xiaozhi-media.log 2>&1 &
  echo "PID $!  log: /tmp/xiaozhi-media.log"
  for _ in $(seq 1 40); do
    if curl -sS -m 1 "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

curl -sS "http://127.0.0.1:${HTTP_PORT}/api/media/status" || true
echo
echo

if [[ "$WITH_MCP" == true ]]; then
  if [[ -z "${MCP_ENDPOINT:-}" ]]; then
    echo "MCP_ENDPOINT missing; skip pipe. Set in .env to use --with-mcp." >&2
    exit 1
  fi
  echo "Starting MCP pipe (Ctrl+C stops pipe; media HTTP keeps running)..."
  exec python scripts/mcp_pipe.py quark-audio
fi

echo "Media HTTP running. Optional: bash scripts/run-media-stack.sh --with-mcp"
echo "Smoke: curl -sS -X POST http://127.0.0.1:${HTTP_PORT}/api/media/resolve -H 'Content-Type: application/json' -d '{\"query\":\"冰雪奇缘第一集\"}'"
