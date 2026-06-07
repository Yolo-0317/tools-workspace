#!/usr/bin/env bash
# 安装公众号：白名单监控（每小时）+ 每日 18:20 草稿（工作日三篇 / 周末要闻）
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

uninstall_one() {
  local label="$1"
  launchctl bootout "gui/${LAUNCHD_UID}/${label}" 2>/dev/null || true
  rm -f "${HOME}/Library/LaunchAgents/${label}.plist"
}

chmod +x "${ROOT}/scripts/wechat_mp_check_whitelist.sh"
chmod +x "${ROOT}/scripts/wechat_mp_draft_scheduled.sh"

install_one "com.user.wechat-mp-whitelist-check" \
  "${WS}/launchd/com.user.wechat-mp-whitelist-check.plist"

# 移除旧版分时段任务
for legacy in \
  com.user.wechat-mp-daily-draft \
  com.user.wechat-mp-draft-morning \
  com.user.wechat-mp-draft-noon \
  com.user.wechat-mp-draft-evening; do
  uninstall_one "${legacy}"
done

install_one "com.user.wechat-mp-draft-scheduled" \
  "${WS}/launchd/com.user.wechat-mp-draft-scheduled.plist"

echo ""
echo "OK com.user.wechat-mp-whitelist-check（每小时）"
echo "   日志: ${ROOT}/logs/launchd-wechat-mp-check.{out,err}.log"
echo "OK com.user.wechat-mp-draft-scheduled（每日 18:20）"
echo "   交易日: sector + top5 + dragons(eod)"
echo "   周日/法定节假日休市: news 1 篇(72h,个股优先)"
echo "   周六休市: 跳过"
echo "   日志: ${ROOT}/logs/launchd-wechat-mp-draft-scheduled.{out,err}.log"
echo ""
echo "手动: ${ROOT}/scripts/wechat_mp_draft_scheduled.sh"
echo "      ${ROOT}/scripts/wechat_mp_draft_scheduled.sh --dry-run"
echo "      ${ROOT}/scripts/wechat_mp_draft_scheduled.sh weekend --dry-run"
