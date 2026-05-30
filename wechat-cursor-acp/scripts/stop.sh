#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

PID_FILE="${PROJECT_DIR}/logs/typing-watcher.pid"
if [[ -f "${PID_FILE}" ]]; then
  tw_pid="$(tr -d '[:space:]' < "${PID_FILE}")"
  if [[ -n "${tw_pid}" ]]; then
    kill "${tw_pid}" 2>/dev/null || true
  fi
  rm -f "${PID_FILE}"
fi

# v0.5.0: stop subcommand still requires --agent on the CLI
npx -y wechat-acp@latest --instance "${WECHAT_ACP_INSTANCE}" --agent cursor stop
