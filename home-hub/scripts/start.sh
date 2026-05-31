#!/usr/bin/env bash
# 生产模式启动（无 reload）
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

export PATH="${HOME}/.local/bin:${PATH}"

if [ ! -d frontend/dist ]; then
  echo "frontend/dist 不存在，请先: cd frontend && npm install && npm run build" >&2
  exit 1
fi

mkdir -p logs data
exec uv run uvicorn backend.main:app \
  --host "${HUB_HOST:-127.0.0.1}" \
  --port "${HUB_PORT:-8780}" \
  --log-level info \
  2>&1 | tee -a "logs/home-hub.log"
