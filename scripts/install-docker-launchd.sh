#!/usr/bin/env bash
# 安装 Docker 开机自启相关：Docker Desktop AutoStart + launchd 拉起 compose 栈
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
SETTINGS="$HOME/Library/Group Containers/group.com.docker/settings-store.json"

chmod +x "$ROOT/scripts/docker-autostart.sh"

if [ -f "$SETTINGS" ]; then
  python3 <<'PY'
import json
from pathlib import Path
p = Path.home() / "Library/Group Containers/group.com.docker/settings-store.json"
data = json.loads(p.read_text())
if not data.get("AutoStart"):
    data["AutoStart"] = True
    p.write_text(json.dumps(data, indent=2) + "\n")
    print("已开启 Docker Desktop AutoStart（登录时启动 Docker）")
else:
    print("Docker Desktop AutoStart 已是开启状态")
PY
else
  echo "WARN: 未找到 $SETTINGS，请在 Docker Desktop → Settings → General 勾选「Start Docker Desktop when you sign in」"
fi

mkdir -p "$AGENTS_DIR" "$ROOT/logs"
dst="$AGENTS_DIR/com.user.docker-stacks.plist"
cp "$ROOT/launchd/com.user.docker-stacks.plist" "$dst"
launchctl bootout "gui/$(id -u)" "$dst" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$dst"
echo "已加载 launchd: $dst"
echo "日志: $ROOT/logs/docker-autostart.log"
