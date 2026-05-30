#!/usr/bin/env bash
# 安装每日战报 launchd（09/12/15/20 点 → wechat-acp 推送）
# 替代已停用的 QClaw daily_briefing_* cron 任务
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
LABEL="com.user.stock-ai-daily-briefing"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

chmod +x "${ROOT}/push_daily_briefing_wechat.sh"

if [[ ! -f "${SRC}" ]]; then
  echo "Error: missing ${SRC}" >&2
  exit 1
fi

mkdir -p "${ROOT}/logs" "${HOME}/Library/LaunchAgents"
cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"

echo "已加载 launchd: ${DST}"
echo "调度: 每天 09:00 / 12:00 / 15:00 / 20:00（slot 由脚本按当前时刻自动识别）"
echo "脚本: ${ROOT}/push_daily_briefing_wechat.sh"
echo "日志: ${ROOT}/logs/launchd-daily-briefing.{out,err}.log"
echo ""
echo "前置:"
echo "  1. stock-ai/.env 配置 DEEPSEEK_API_KEY"
echo "  2. wechat-cursor-acp 已扫码（~/.wechat-acp/instances/tools-workspace/token.json）"
echo ""
echo "手动试跑:"
echo "  FETCH_ONLY=1 ${ROOT}/push_daily_briefing_wechat.sh 09:00"
echo "  ${ROOT}/push_daily_briefing_wechat.sh 15:00"
