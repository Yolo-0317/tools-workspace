#!/usr/bin/env bash
# 停用盘中情绪周期 launchd（晚间龙头稿用 Docker eod + 19:00 草稿即可）
set -euo pipefail

LABEL="com.user.stock-emotion-intraday"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
DST="${AGENTS_DIR}/${LABEL}.plist"
UID_GUI="gui/$(id -u)"

launchctl bootout "${UID_GUI}" "${DST}" 2>/dev/null || true
rm -f "${DST}"
echo "已停用: ${LABEL}（plist 已从 LaunchAgents 移除）"
