#!/usr/bin/env bash
# Restart HarryPutter launchd service (reload serve.py / dict API).
set -euo pipefail
LABEL="com.user.harryputter"
OLD_LABEL="com.user.readalong"
UID_NUM="$(id -u)"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
OLD_PLIST="${HOME}/Library/LaunchAgents/${OLD_LABEL}.plist"

launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null || {
  launchctl bootout "gui/${UID_NUM}" "${OLD_PLIST}" 2>/dev/null || true
  launchctl bootout "gui/${UID_NUM}" "${PLIST}" 2>/dev/null || true
  launchctl bootstrap "gui/${UID_NUM}" "${PLIST}"
  echo "已 bootstrap ${LABEL}"
}
