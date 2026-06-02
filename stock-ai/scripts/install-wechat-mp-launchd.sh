#!/usr/bin/env bash
# 安装公众号：白名单监控（每小时）+ 工作日 17:40 三篇草稿
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WS="$(cd "${ROOT}/.." && pwd)"
LAUNCHD_UID="$(id -u)"

install_one() {
  local label="$1"
  local plist_src="$2"
  local plist_dst="${HOME}/Library/LaunchAgents/${label}.plist"
  if [[ ! -f "${plist_src}" ]]; then
    echo "❌ 未找到 ${plist_src}" >&2
    return 1
  fi
  cp "${plist_src}" "${plist_dst}"
  echo "已安装 ${plist_dst}"
  launchctl bootout "gui/${LAUNCHD_UID}/${label}" 2>/dev/null || true
  launchctl bootstrap "gui/${LAUNCHD_UID}" "${plist_dst}"
  launchctl enable "gui/${LAUNCHD_UID}/${label}" 2>/dev/null || true
  launchctl kickstart -k "gui/${LAUNCHD_UID}/${label}" 2>/dev/null || true
}

chmod +x "${ROOT}/scripts/wechat_mp_check_whitelist.sh"
chmod +x "${ROOT}/scripts/wechat_mp_draft_daily.sh"

install_one "com.user.wechat-mp-whitelist-check" \
  "${WS}/launchd/com.user.wechat-mp-whitelist-check.plist"

install_one "com.user.wechat-mp-daily-draft" \
  "${WS}/launchd/com.user.wechat-mp-daily-draft.plist"

echo ""
echo "OK com.user.wechat-mp-whitelist-check（每小时）"
echo "   日志: ${ROOT}/logs/launchd-wechat-mp-check.{out,err}.log"
echo "   告警: ${ROOT}/logs/wechat_mp_alerts.log"
echo "OK com.user.wechat-mp-daily-draft（工作日 17:40，三篇草稿）"
echo "   日志: ${ROOT}/logs/launchd-wechat-mp-draft.{out,err}.log"
echo "手动草稿: ${ROOT}/scripts/wechat_mp_draft_daily.sh"
