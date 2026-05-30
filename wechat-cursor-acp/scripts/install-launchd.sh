#!/usr/bin/env bash
# 安装 wechat-cursor-acp 登录自启（launchd）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
LABEL="com.user.wechat-cursor-acp"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${AGENTS_DIR}/${LABEL}.plist"

chmod +x "${ROOT}/scripts/wechat-acp-autostart.sh" "${ROOT}/scripts/start.sh"
mkdir -p "${ROOT}/logs" "${AGENTS_DIR}"

if [[ ! -f "${SRC}" ]]; then
  echo "Error: missing ${SRC}" >&2
  exit 1
fi

cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"
echo "已加载 launchd: ${DST}"
echo "日志: ${ROOT}/logs/launchd-autostart.{out,err}.log"
echo ""
echo "说明:"
echo "  - 登录后自动拉起守护进程（需已有 token，首次请手动 ./scripts/start.sh --login）"
echo "  - 每 600 秒检查一次，进程退出会尝试重启"
echo "  - 卸载: launchctl bootout gui/$(id -u) ${DST} && rm ${DST}"
