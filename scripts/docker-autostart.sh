#!/usr/bin/env bash
# 等待 Docker 就绪后，拉起本机常用 compose 栈（幂等：已运行则跳过）
set -euo pipefail

LOG_DIR="${LOG_DIR:-$HOME/dev/yolo/tools-workspace/logs}"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/docker-autostart.log"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"
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

compose_up() {
  local dir="$1"
  local extra="${2:-}"
  if [ ! -f "$dir/docker-compose.yml" ] && [ ! -f "$dir/docker-compose.yaml" ]; then
    log "SKIP: 无 compose 文件 $dir"
    return 0
  fi
  log "START: $dir"
  # shellcheck disable=SC2086
  (cd "$dir" && docker compose $extra up -d) >>"$LOG" 2>&1 || {
    log "WARN: compose up 失败 $dir（见日志）"
    return 0
  }
  log "OK: $dir"
}

main() {
  log "===== docker-autostart 开始 ====="
  wait_for_docker

  # MySQL（stock-ai 行情 + 持仓等业务表）
  compose_up "$HOME/dev/yolo/tools-workspace/stock-mysql" "--env-file .env"

  # 媒体 / 基础设施
  compose_up "$HOME/docker/jellyfin-stack"
  compose_up "$HOME/docker/immich-stack"
  compose_up "$HOME/dev/yolo/tools-workspace/sidestore-infra" "--env-file .env"
  compose_up "$HOME/dev/yolo/tools-workspace/substore-clash" "--env-file .env"

  # stock-ai 统一调度（含原 daily-sync Tushare cron）
  compose_up "$HOME/dev/yolo/tools-workspace/stock-ai/docker/scheduler" "--env-file ../../.env"

  log "===== docker-autostart 完成 ====="
}

main "$@"
