#!/usr/bin/env bash
# 停用东财快讯 15 分钟 launchd（com.user.stock-macro-news-sync）
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AGENTS="${HOME}/Library/LaunchAgents"
UID_GUI="gui/$(id -u)"
LABEL="com.user.stock-macro-news-sync"
PLIST_SRC="${WORKSPACE}/launchd/${LABEL}.plist"
PLIST_DST="${AGENTS}/${LABEL}.plist"

for plist in "${PLIST_DST}" "${PLIST_SRC}"; do
  launchctl bootout "${UID_GUI}" "${plist}" 2>/dev/null || true
done
if [[ -f "${PLIST_DST}" ]]; then
  rm -f "${PLIST_DST}"
  echo "已移除 ${PLIST_DST}"
fi

echo "已停用 ${LABEL}（不再每 15 分钟 sync_macro_news）"
echo "手动同步（可选）: cd ${WORKSPACE}/stock-ai && ./sync_macro_news.sh --skip-ai"
