#!/usr/bin/env bash
# 安装 2026-06-01 09:00 一次性股票关注提醒（wechat-acp）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
LABEL="com.user.stock-watch-reminder-20260601"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${AGENTS_DIR}/${LABEL}.plist"

chmod +x "${ROOT}/push_stock_watch_reminder_wechat.sh"

if [[ ! -f "${SRC}" ]]; then
  echo "Error: missing ${SRC}" >&2
  exit 1
fi

mkdir -p "${ROOT}/logs" "${AGENTS_DIR}"
cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"

echo "已加载 launchd: ${DST}"
echo "调度: 2026-06-01 09:00（脚本内幂等，仅推送一次）"
echo "脚本: ${ROOT}/push_stock_watch_reminder_wechat.sh"
echo "日志: ${ROOT}/logs/launchd-stock-watch-reminder.{out,err}.log"
echo ""
echo "手动试跑（需设置日期）: STOCK_WATCH_REMINDER_DATE=2026-06-01 ${ROOT}/push_stock_watch_reminder_wechat.sh"
