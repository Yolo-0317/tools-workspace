#!/usr/bin/env bash
# 安装工作日 17:30 综合选股战报 → 微信（wechat-acp）launchd 任务
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
LABEL="com.user.stock-ai-daily-selection"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${AGENTS_DIR}/${LABEL}.plist"

chmod +x "${ROOT}/push_selection_wechat.sh" "${ROOT}/run_selection_daily.sh"

if [[ ! -f "${SRC}" ]]; then
  echo "Error: missing ${SRC}" >&2
  exit 1
fi

mkdir -p "${ROOT}/logs" "${AGENTS_DIR}"
cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"

echo "已加载 launchd: ${DST}"
echo "调度: 周一至周五 17:30（Asia/Shanghai 系统时区）"
echo "脚本: ${ROOT}/push_selection_wechat.sh"
echo "日志: ${ROOT}/logs/launchd-daily-selection.{out,err}.log"
echo ""
echo "建议: 在 QClaw 中关闭 cron 任务 daily_stock_selection_17:30，避免重复推送。"
echo "手动试跑: ${ROOT}/push_selection_wechat.sh"
