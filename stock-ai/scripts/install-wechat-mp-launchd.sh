#!/usr/bin/env bash
# 安装公众号：白名单监控（每小时）
# 草稿：由 Docker scheduler 11:00 影视 / 15:00 股市热点 host-jobs 触发
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
chmod +x "${ROOT}/scripts/wechat_mp_tv_draft_scheduled.sh"
chmod +x "${ROOT}/scripts/wechat_mp_hotspot_draft_scheduled.sh"
chmod +x "${ROOT}/scripts/wechat_mp_guba_scheduled.sh"

install_one "com.user.wechat-mp-whitelist-check" \
  "${WS}/launchd/com.user.wechat-mp-whitelist-check.plist"

# 移除旧版分时段任务
for legacy in \
  com.user.wechat-mp-daily-draft \
  com.user.wechat-mp-draft-morning \
  com.user.wechat-mp-draft-noon \
  com.user.wechat-mp-draft-evening \
  com.user.wechat-mp-draft-scheduled \
  com.user.wechat-mp-growth-remind \
  com.user.wechat-mp-guba-scheduled; do
  uninstall_one "${legacy}"
done

echo ""
echo "OK com.user.wechat-mp-whitelist-check（每小时）"
echo "   日志: ${ROOT}/logs/launchd-wechat-mp-check.{out,err}.log"
echo "已停用 com.user.wechat-mp-draft-scheduled / com.user.wechat-mp-guba-scheduled"
echo "草稿定时: Docker scheduler → host-jobs（热点深评 09:00 / 11:00 / 15:00 / 18:00）"
echo "   09:00: ${ROOT}/logs/host-job-wechat-mp-hotspot-early.log"
echo "   11:00: ${ROOT}/logs/host-job-wechat-mp-hotspot-morning.log"
echo "   15:00: ${ROOT}/logs/host-job-wechat-mp-hotspot-afternoon.log"
echo "   18:00: ${ROOT}/logs/host-job-wechat-mp-hotspot-evening.log"
echo ""
echo "手动:"
echo "  ${ROOT}/scripts/wechat_mp_tv_draft_scheduled.sh --dry-run"
echo "  ${ROOT}/scripts/wechat_mp_hotspot_draft_scheduled.sh --dry-run"
