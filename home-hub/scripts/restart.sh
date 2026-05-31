#!/usr/bin/env bash
# 重启 Home Hub（单服务 :8780，launchd 常驻）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.user.home-hub"
UID="$(id -u)"

do_build() {
  echo "[restart] 构建前端…" >&2
  (cd "${ROOT}/frontend" && npm run build)
}

case "${1:-}" in
  --build|-b) do_build ;;
  --help|-h)
    echo "用法: $0 [--build]" >&2
    echo "  无参数   仅重启 launchd 服务（:8780）" >&2
    echo "  --build  先 npm run build 再重启" >&2
    exit 0
    ;;
esac

if launchctl print "gui/${UID}/${LABEL}" &>/dev/null; then
  launchctl kickstart -k "gui/${UID}/${LABEL}"
  echo "[restart] 已重启 ${LABEL} → http://127.0.0.1:${HUB_PORT:-8780}"
else
  echo "[restart] launchd 未安装，执行: ./scripts/install-launchd.sh" >&2
  if [[ ! -f "${ROOT}/frontend/dist/index.html" ]]; then
    do_build
  fi
  exec "${ROOT}/scripts/start.sh"
fi
