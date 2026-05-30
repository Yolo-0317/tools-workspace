#!/usr/bin/env bash
# 向运行中的守护进程注入一条消息（模拟用户发言 → Agent 回复到微信）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

text="${1:-}"
if [[ -z "${text}" ]]; then
  echo "Usage: $0 \"消息内容\"" >&2
  exit 1
fi

exec npx -y wechat-acp@latest inject \
  --instance "${WECHAT_ACP_INSTANCE}" \
  --text "${text}"
