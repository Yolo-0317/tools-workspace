#!/usr/bin/env bash
# 盘中龙头/情绪周期 → MySQL（OpenCLI 东财涨停池，每 15 分钟；非交易时段脚本内跳过）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
LABEL="com.user.stock-emotion-intraday"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
SRC="${WORKSPACE}/launchd/${LABEL}.plist"
DST="${AGENTS_DIR}/${LABEL}.plist"

mkdir -p "${AGENTS_DIR}"
cp "${SRC}" "${DST}"
launchctl bootout "gui/$(id -u)" "${DST}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${DST}"

echo "已加载 launchd: ${DST}"
echo "任务: 每 5 分钟 ./sync_emotion_cycle.sh intraday（交易时段内生效）→ export → push dragons.json"
echo "日志: ${ROOT}/logs/launchd-emotion-intraday.{out,err}.log"
