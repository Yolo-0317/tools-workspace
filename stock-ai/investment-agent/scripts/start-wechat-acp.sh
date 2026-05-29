#!/usr/bin/env bash
# 启动 wechat-acp，将微信消息桥接到 Cursor CLI Agent
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v agent >/dev/null 2>&1; then
  echo "Error: Cursor CLI (agent) not found. Install from https://cursor.com/docs/cli"
  exit 1
fi

echo "Project: ${PROJECT_DIR}"
echo "Agent:   agent acp (Cursor CLI)"
echo ""
echo "Note: Stop QClaw openclaw-weixin first to avoid iLink login conflict."
echo ""

export WECHAT_ACP_TELEMETRY=0

exec npx -y wechat-acp@latest \
  --agent "agent acp" \
  --cwd "${PROJECT_DIR}" \
  --hide-thoughts \
  "$@"
