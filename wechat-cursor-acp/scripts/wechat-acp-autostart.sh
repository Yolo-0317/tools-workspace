#!/usr/bin/env bash
# 登录后幂等启动 wechat-acp 守护进程（供 launchd 调用）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib/common.sh"

export PATH="${HOME}/.local/bin:${HOME}/.nvm/versions/node/v24.14.1/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
if [[ -s "${HOME}/.nvm/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/.nvm/nvm.sh"
fi

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

INSTANCE_DIR="${HOME}/.wechat-acp/instances/${WECHAT_ACP_INSTANCE}"
PID_FILE="${INSTANCE_DIR}/daemon.pid"
TOKEN_FILE="${INSTANCE_DIR}/token.json"

if [[ -f "${PID_FILE}" ]]; then
  pid="$(tr -d '[:space:]' < "${PID_FILE}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    log "Daemon already running (PID ${pid}), skip"
    "${ROOT}/scripts/start-typing-watcher.sh" || true
    exit 0
  fi
fi

if pgrep -f "wechat-acp.*--instance[ =]${WECHAT_ACP_INSTANCE}" >/dev/null 2>&1; then
  log "wechat-acp instance already running, skip"
  "${ROOT}/scripts/start-typing-watcher.sh" || true
  exit 0
fi

if [[ ! -f "${TOKEN_FILE}" ]]; then
  log "No WeChat token at ${TOKEN_FILE}; run ./scripts/start.sh --login once"
  exit 0
fi

if ! command -v agent >/dev/null 2>&1; then
  log "Cursor CLI (agent) not in PATH; install from https://cursor.com/docs/cli"
  exit 1
fi

log "Starting wechat-acp daemon (instance=${WECHAT_ACP_INSTANCE})"
cd "${ROOT}"
exec "${ROOT}/scripts/start.sh"
