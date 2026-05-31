#!/usr/bin/env bash
# 登录后幂等启动 home-hub（供 launchd 调用）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

PORT="${HUB_PORT:-8780}"
if lsof -iTCP:"${PORT}" -sTCP:LISTEN -P -n 2>/dev/null | grep -q LISTEN; then
  log "home-hub already listening on ${PORT}, skip"
  exit 0
fi

if pgrep -f "uvicorn backend.main:app.*--port ${PORT}" >/dev/null 2>&1; then
  log "uvicorn home-hub already running, skip"
  exit 0
fi

if [ ! -f "${ROOT}/frontend/dist/index.html" ]; then
  log "Building frontend..."
  (cd "${ROOT}/frontend" && npm run build) || {
    log "frontend build failed"
    exit 1
  }
fi

log "Starting home-hub on 127.0.0.1:${PORT}"
cd "${ROOT}"
exec "${ROOT}/scripts/start.sh"
