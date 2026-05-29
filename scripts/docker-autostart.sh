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
    if [ "$n" -gt 120 ]; then
      log "ERROR: docker 在 10 分钟内未就绪，退出"
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

  # 独立 MySQL（stock-ai 等依赖宿主机 3306）
  compose_up "$HOME/dev/docker/mysql"

  # 媒体 / 基础设施
  compose_up "$HOME/docker/jellyfin-stack"
  compose_up "$HOME/dev/yolo/tools-workspace/sidestore-infra" "--env-file .env"
  compose_up "$HOME/dev/yolo/tools-workspace/substore-clash" "--env-file .env"

  # stock-ai
  compose_up "$HOME/dev/yolo/tools-workspace/stock-ai/docker/daily-sync"
  compose_up "$HOME/dev/yolo/tools-workspace/stock-ai/stock_analysis"

  log "===== docker-autostart 完成 ====="
}

main "$@"
