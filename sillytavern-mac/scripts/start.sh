#!/usr/bin/env bash
# 前台启动 SillyTavern（Ctrl+C 停止）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor/SillyTavern"

if [[ ! -d "$VENDOR" ]]; then
  echo "未安装。请先运行: bash scripts/install.sh"
  exit 1
fi

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "$ROOT/.env"
  set +a
fi

PORT="${ST_PORT:-8792}"
LISTEN="${ST_LISTEN:-127.0.0.1}"

mkdir -p "$ROOT/logs"

echo "==> SillyTavern 启动中"
echo "    地址: http://${LISTEN}:${PORT}"
echo "    日志: $ROOT/logs/server.log"
echo "    按 Ctrl+C 停止"
echo ""

cd "$VENDOR"
export SILLYTAVERN_PORT="$PORT"
export SILLYTAVERN_HOST="$LISTEN"

# start.sh 会检测依赖并启动 node server.js
exec bash start.sh 2>&1 | tee -a "$ROOT/logs/server.log"
