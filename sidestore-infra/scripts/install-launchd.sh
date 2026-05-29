#!/usr/bin/env bash
# 安装 launchd 自启动任务（Docker 栈 + DDNS）
set -euo pipefail

AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS_DIR"

for plist in sidestore-infra aliyun-ddns sidestore-certs; do
  src="$(cd "$(dirname "$0")/.." && pwd)/launchd/com.user.${plist}.plist"
  dst="$AGENTS_DIR/com.user.${plist}.plist"
  cp "$src" "$dst"
  launchctl bootout "gui/$(id -u)" "$dst" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$dst"
  echo "已加载: $dst"
done
