#!/usr/bin/env bash
# 停用公众号增长提醒 launchd（com.user.wechat-mp-growth-remind）
set -euo pipefail

AGENTS="${HOME}/Library/LaunchAgents"
UID_GUI="gui/$(id -u)"
LABEL="com.user.wechat-mp-growth-remind"
PLIST_DST="${AGENTS}/${LABEL}.plist"

launchctl bootout "${UID_GUI}" "${PLIST_DST}" 2>/dev/null || true
launchctl bootout "${UID_GUI}/${LABEL}" 2>/dev/null || true
if [[ -f "${PLIST_DST}" ]]; then
  rm -f "${PLIST_DST}"
  echo "已移除 ${PLIST_DST}"
fi

echo "已停用 ${LABEL}（不再周二/五 19:25 转群提醒）"
