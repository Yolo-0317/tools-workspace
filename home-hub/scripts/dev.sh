#!/usr/bin/env sh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
# 开发后端与 launchd 生产 (8780) 错开，可用 HUB_DEV_PORT 覆盖
export HUB_PORT="${HUB_DEV_PORT:-8781}"
echo "[dev] backend http://${HUB_HOST:-127.0.0.1}:${HUB_PORT} (prod/launchd: 8780)" >&2
exec uv run uvicorn backend.main:app --host "${HUB_HOST:-127.0.0.1}" --port "${HUB_PORT}" --reload "$@"
