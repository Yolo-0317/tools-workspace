#!/usr/bin/env bash
# launchd 常驻入口：前台跑 uvicorn，进程退出后由 KeepAlive 拉起
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

PORT="${HUB_PORT:-8780}"
HOST="${HUB_HOST:-127.0.0.1}"

if [ ! -f frontend/dist/index.html ]; then
  echo "[$(date '+%F %T')] frontend/dist 缺失，尝试构建..." >&2
  (cd frontend && npm run build) || exit 1
fi

mkdir -p logs data

echo "[$(date '+%F %T')] home-hub 启动 ${HOST}:${PORT}" >&2
exec uv run uvicorn backend.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --log-level info
