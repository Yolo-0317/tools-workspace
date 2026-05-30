#!/bin/sh
# 兼容入口：宏观快讯已并入 daily_briefing 战报，本脚本转发到统一战报推送。
set -eu
ROOT="$(cd "$(dirname "$0")" && pwd)"
SLOT="${BRIEFING_SLOT:-$(date '+%H:00')}"
exec "${ROOT}/push_daily_briefing_wechat.sh" "$SLOT"
