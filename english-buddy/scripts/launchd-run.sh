#!/usr/bin/env bash
# launchd 常驻：构建前端 + FastAPI :18787（Caddy hub /english/* 反代）
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

PORT="${ENGLISH_BUDDY_PORT:-18787}"
HOST="${ENGLISH_BUDDY_HOST:-127.0.0.1}"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r backend/requirements.txt
fi

# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="$ROOT/backend"

if [ ! -f frontend/dist/index.html ]; then
  echo "[$(date '+%F %T')] frontend/dist 缺失，构建（VITE_BASE_PATH=/english/）..." >&2
  (cd frontend && npm install && VITE_BASE_PATH=/english/ npm run build) || exit 1
elif [[ ! -f frontend/dist/characters/elsa.jpg ]] || [[ ! -f frontend/dist/sw.js ]]; then
  echo "[$(date '+%F %T')] dist 需重建（角色头像或 PWA）..." >&2
  (cd frontend && npm install && VITE_BASE_PATH=/english/ npm run build) || exit 1
fi

if [[ ! -f voices/piper/elsa/en_US-amy-medium.onnx ]]; then
  echo "[$(date '+%F %T')] Piper 语音未下载，运行 download_piper_voices.sh..." >&2
  ./scripts/download_piper_voices.sh || exit 1
fi

mkdir -p logs

echo "[$(date '+%F %T')] english-buddy 启动 ${HOST}:${PORT}" >&2
exec uvicorn main:app --app-dir "$ROOT/backend" --host "${HOST}" --port "${PORT}" --log-level info
