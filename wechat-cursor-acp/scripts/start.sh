#!/usr/bin/env bash
# Start WeChat bridge → Cursor CLI (agent acp).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

require_agent_cli
AGENT_CWD_RESOLVED="$(resolve_agent_cwd)"
prepare_wechat_acp_config
CONFIG_FILE="${WECHAT_ACP_CONFIG}"

echo "Bridge project: ${PROJECT_DIR}"
echo "Agent cwd:      ${AGENT_CWD_RESOLVED}"
echo "Instance:       ${WECHAT_ACP_INSTANCE}"
echo "Agent model:    ${WECHAT_AGENT_MODEL} (agent acp)"
if is_truthy "${WECHAT_FORWARD_THOUGHTS}"; then
  echo "Thoughts:   forward to WeChat (WECHAT_FORWARD_THOUGHTS=1)"
else
  echo "Thoughts:   hidden (set WECHAT_FORWARD_THOUGHTS=1 in .env to enable)"
fi
echo ""
echo "Note: Disable QClaw openclaw-weixin before starting to avoid iLink conflicts."
echo "Mode:    login then daemon (pass --foreground to stay in this terminal)"
echo ""

daemon_args=(--daemon)
extra_args=()
for arg in "$@"; do
  case "${arg}" in
    --foreground) daemon_args=() ;;
    *) extra_args+=("${arg}") ;;
  esac
done

start_args=(
  --instance "${WECHAT_ACP_INSTANCE}"
  --agent cursor
  --config "${CONFIG_FILE}"
  --cwd "${AGENT_CWD_RESOLVED}"
)
if ! is_truthy "${WECHAT_FORWARD_THOUGHTS}"; then
  start_args+=(--hide-thoughts)
fi
if ((${#daemon_args[@]} > 0)); then
  start_args+=("${daemon_args[@]}")
fi
if ((${#extra_args[@]} > 0)); then
  start_args+=("${extra_args[@]}")
fi

if ((${#daemon_args[@]} > 0)); then
  npx -y wechat-acp@latest "${start_args[@]}"
  "${SCRIPT_DIR}/start-typing-watcher.sh"
else
  "${SCRIPT_DIR}/start-typing-watcher.sh"
  exec npx -y wechat-acp@latest "${start_args[@]}"
fi
