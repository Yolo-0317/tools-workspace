#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

AGENT_CWD_RESOLVED="$(resolve_agent_cwd)"

echo "Instance:  ${WECHAT_ACP_INSTANCE}"
echo "Agent cwd: ${AGENT_CWD_RESOLVED}"
echo ""

npx -y wechat-acp@latest --instance "${WECHAT_ACP_INSTANCE}" --agent cursor status
