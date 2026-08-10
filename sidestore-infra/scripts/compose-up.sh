#!/usr/bin/env bash
# launchd 专用：非 login shell，避免开机时 bash -lc 触发 conda/profile fork 风暴
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/compose-up.log"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"
}

wait_for_docker() {
  local n=0
  until docker info >/dev/null 2>&1; do
    n=$((n + 1))
    if [ "$n" -gt 360 ]; then
      log "ERROR: docker 在 30 分钟内未就绪，退出"
      exit 1
    fi
    sleep 5
  done
  log "Docker 引擎已就绪"
}

main() {
  log "===== sidestore compose-up 开始 ====="
  wait_for_docker
  (cd "$ROOT" && docker compose --env-file .env up -d) >>"$LOG" 2>&1
  log "===== sidestore compose-up 完成 ====="
}

main "$@"
