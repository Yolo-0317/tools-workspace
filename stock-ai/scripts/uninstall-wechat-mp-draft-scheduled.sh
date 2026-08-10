#!/usr/bin/env bash
# 停用公众号 18:20 launchd（改由 18:00 eod 完成后 host-jobs 链式触发）
set -euo pipefail

AGENTS="${HOME}/Library/LaunchAgents"
UID_GUI="gui/$(id -u)"
LABEL="com.user.wechat-mp-draft-scheduled"
PLIST_DST="${AGENTS}/${LABEL}.plist"

launchctl bootout "${UID_GUI}" "${PLIST_DST}" 2>/dev/null || true
launchctl bootout "${UID_GUI}/${LABEL}" 2>/dev/null || true
if [[ -f "${PLIST_DST}" ]]; then
  rm -f "${PLIST_DST}"
  echo "已移除 ${PLIST_DST}"
fi

echo "已停用 ${LABEL}（草稿改由 scheduler：工作日 eod 后 / 周日 18:00 host-jobs）"
