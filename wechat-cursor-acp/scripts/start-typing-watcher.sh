#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

PID_FILE="${PROJECT_DIR}/logs/typing-watcher.pid"
LOG_FILE="${PROJECT_DIR}/logs/typing-watcher.log"

mkdir -p "${PROJECT_DIR}/logs"

if [[ -f "${PID_FILE}" ]]; then
  old_pid="$(tr -d '[:space:]' < "${PID_FILE}")"
  if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
    echo "Typing watcher already running (PID ${old_pid})"
    exit 0
  fi
fi

export WECHAT_ACP_INSTANCE
nohup node "${SCRIPT_DIR}/typing-watcher.mjs" >> "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"
echo "Typing watcher started (PID $(cat "${PID_FILE}"))"
echo "Log: ${LOG_FILE}"
