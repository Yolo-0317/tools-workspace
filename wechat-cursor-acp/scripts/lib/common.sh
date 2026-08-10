#!/usr/bin/env bash
# Shared helpers for wechat-cursor-acp scripts.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -f "${PROJECT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_DIR}/.env"
  set +a
fi

: "${WECHAT_ACP_INSTANCE:=tools-workspace}"
: "${WECHAT_ACP_TELEMETRY:=0}"
: "${WECHAT_FORWARD_THOUGHTS:=0}"
: "${WECHAT_AGENT_MODEL:=composer-2.5}"

prepare_wechat_acp_config() {
  local src="${PROJECT_DIR}/config/wechat-acp.json"
  local dst="${PROJECT_DIR}/config/wechat-acp.runtime.json"
  if [[ ! -f "${src}" ]]; then
    echo "Error: missing ${src}" >&2
    return 1
  fi
  WECHAT_ACP_CONFIG="${dst}"
  python3 - "${src}" "${dst}" "${WECHAT_AGENT_MODEL}" <<'PY'
import json
import sys

src, dst, model = sys.argv[1:4]
with open(src, encoding="utf-8") as f:
    cfg = json.load(f)
cfg.setdefault("agents", {}).setdefault("cursor", {})["args"] = ["--model", model, "acp"]
with open(dst, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}

# True for 1, true, yes, on (case-insensitive). POSIX-safe (macOS /bin/sh).
is_truthy() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    1 | true | yes | on) return 0 ;;
    *) return 1 ;;
  esac
}

resolve_agent_cwd() {
  local raw="${AGENT_CWD:-${PROJECT_DIR}}"
  if [[ "${raw}" != /* ]]; then
    raw="${PROJECT_DIR}/${raw}"
  fi
  cd "${raw}" && pwd
}

require_agent_cli() {
  if ! command -v agent >/dev/null 2>&1; then
    echo "Error: Cursor CLI (agent) not found. Install: https://cursor.com/docs/cli" >&2
    exit 1
  fi
}

export WECHAT_ACP_TELEMETRY

instance_dir() {
  printf '%s/.wechat-acp/instances/%s\n' "${HOME}" "${WECHAT_ACP_INSTANCE}"
}

daemon_pid_file() {
  printf '%s/daemon.pid\n' "$(instance_dir)"
}

read_daemon_pid() {
  local pid_file
  pid_file="$(daemon_pid_file)"
  [[ -f "${pid_file}" ]] || return 1
  tr -d '[:space:]' < "${pid_file}"
}

daemon_running() {
  local pid
  pid="$(read_daemon_pid 2>/dev/null)" || return 1
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

wechat_acp() {
  npx -y wechat-acp@latest \
    --instance "${WECHAT_ACP_INSTANCE}" \
    --agent cursor \
    "$@"
}
