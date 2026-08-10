#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "$ROOT/.env"
  set +a
fi

PORT="${ST_PORT:-8792}"
URL="http://127.0.0.1:${PORT}/"

if [[ ! -d "$ROOT/vendor/SillyTavern" ]]; then
  echo "FAIL: 未安装（vendor/SillyTavern 不存在）"
  exit 1
fi

if curl -sf --max-time 5 "$URL" >/dev/null 2>&1; then
  echo "OK: SillyTavern 可访问 $URL"
  exit 0
fi

echo "FAIL: $URL 无响应（服务未启动？运行 bash scripts/start.sh）"
exit 1
