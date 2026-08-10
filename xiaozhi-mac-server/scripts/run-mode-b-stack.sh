#!/usr/bin/env bash
# Mode B: xiaozhi.me MCP pipe + local gateway for Quark Opus push.
#
# Required:
#   1) MCP_ENDPOINT in .env  (xiaozhi.me 智能体 → 配置角色 → MCP 接入点)
#   2) Local gateway running (this script starts it)
#   3) Device on local WS for playback  →  bash ../xiaozhi-atoms3r/scripts/flash-local-ota.sh
#
# Note: 设备若只连官方云、不连本地 WS，MCP 能搜夸克但喇叭播不出长音频。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Run bash scripts/install.sh first" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source .env
set +a

if [[ -z "${MCP_ENDPOINT:-}" ]]; then
  cat >&2 <<'EOF'
缺少 MCP_ENDPOINT。

请打开 https://xiaozhi.me → 控制台 → 你的智能体 → 配置角色
右下角复制「MCP 接入点」完整 URL（含 token），写入 .env：

  MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...

然后重新执行: bash scripts/run-mode-b-stack.sh
EOF
  exit 1
fi

LAN_IP="$(python -c 'from server.config import settings; print(settings.lan_ip)')"
HTTP_PORT="${HTTP_PORT:-8766}"
export XIAOZHI_GATEWAY="${XIAOZHI_GATEWAY:-http://${LAN_IP}:${HTTP_PORT}}"
# Mode B: 对话由云端智能体 + MCP 工具完成；本地网关负责推流
export USE_MCP_TOOLS="${USE_MCP_TOOLS:-false}"

echo "=== Mode B stack ==="
echo "MCP_ENDPOINT : ${MCP_ENDPOINT:0:48}..."
echo "XIAOZHI_GATEWAY: $XIAOZHI_GATEWAY"
echo "USE_MCP_TOOLS  : $USE_MCP_TOOLS (Mode B 建议 false)"
echo
echo "Checklist:"
echo "  [1] 网关 HTTP/WS     → 本脚本会启动"
echo "  [2] MCP pipe         → 本脚本会启动"
echo "  [3] 设备本地 OTA/WS  → cd ../xiaozhi-atoms3r && bash scripts/flash-local-ota.sh"
echo "  [4] 智能体已绑定该 MCP 接入点对应的角色"
echo

if ! curl -sS -m 1 "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
  echo "Starting local gateway..."
  nohup env USE_MCP_TOOLS="$USE_MCP_TOOLS" python server/main.py \
    >/tmp/xiaozhi-mode-b-gateway.log 2>&1 &
  echo "Gateway PID $!  log: /tmp/xiaozhi-mode-b-gateway.log"
  for _ in $(seq 1 30); do
    if curl -sS -m 1 "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
else
  echo "Gateway already up on :${HTTP_PORT}"
fi

curl -sS "http://127.0.0.1:${HTTP_PORT}/api/mcp/status" || true
echo
echo
echo "Starting MCP pipe (Ctrl+C stops pipe; gateway keeps running)..."
echo "Doctor: bash scripts/check-quark-mcp.sh"
echo

exec python scripts/mcp_pipe.py quark-audio
