#!/usr/bin/env bash
# launchd 常驻：静态站 :8791（Caddy hub /readalong/* 反代，不经 Home Hub 登录）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export READALONG_PORT="${READALONG_PORT:-8791}"
export READALONG_HOST="${READALONG_HOST:-127.0.0.1}"

mkdir -p logs

if [[ ! -f output/ch01.json ]]; then
  echo "[$(date '+%F %T')] WARN: output/ch01.json 缺失，先运行 ./scripts/pipeline.sh 1" >&2
fi

echo "[$(date '+%F %T')] readalong 启动 ${READALONG_HOST}:${READALONG_PORT}" >&2
exec python3 "$ROOT/scripts/serve.py"
