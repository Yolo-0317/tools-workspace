#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.user.english-buddy"
BUILD="${1:-}"

cd "$ROOT"

if [[ "${BUILD}" == "--build" ]]; then
  echo "构建前端 (VITE_BASE_PATH=/english/)..."
  (cd frontend && npm install && VITE_BASE_PATH=/english/ npm run build)
fi

launchctl kickstart -k "gui/$(id -u)/${LABEL}" 2>/dev/null || {
  echo "launchd 未安装，执行 ./scripts/install-launchd.sh" >&2
  exit 1
}
echo "english-buddy 已重启，等待健康检查..."
for _ in $(seq 1 24); do
  if curl -sf "http://127.0.0.1:18787/api/health" >/dev/null 2>&1; then
    curl -sf "http://127.0.0.1:18787/api/health" | head -c 200
    echo ""
    exit 0
  fi
  sleep 0.5
done
echo "健康检查超时（服务可能仍在启动）" >&2
exit 1
