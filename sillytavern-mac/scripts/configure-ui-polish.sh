#!/usr/bin/env bash
# 应用 Hub Polished 主题：更干净的聊天区、圆角气泡、弱化杂项 UI
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
THEME_SRC="$ROOT/themes/Hub Polished.json"
ST_DATA="$ROOT/vendor/SillyTavern/data/default-user"
SETTINGS="$ST_DATA/settings.json"
THEME_DST="$ST_DATA/themes/Hub Polished.json"

if [[ ! -f "$THEME_SRC" ]]; then
  echo "错误: 未找到 $THEME_SRC"
  exit 1
fi

if [[ ! -f "$SETTINGS" ]]; then
  echo "错误: 未找到 $SETTINGS（请先启动过一次 SillyTavern）"
  exit 1
fi

mkdir -p "$ST_DATA/themes"
cp "$THEME_SRC" "$THEME_DST"

python3 - "$THEME_SRC" "$SETTINGS" <<'PY'
import json
import sys
from pathlib import Path

theme_path, settings_path = map(Path, sys.argv[1:3])
theme = json.loads(theme_path.read_text(encoding="utf-8"))
settings = json.loads(settings_path.read_text(encoding="utf-8"))

pu = settings.setdefault("power_user", {})
for key, value in theme.items():
    if key == "name":
        continue
    pu[key] = value
pu["theme"] = theme["name"]

settings["background"] = {
    "name": "_black.jpg",
    "url": 'url("backgrounds/_black.jpg")',
    "fitting": "classic",
    "animation": False,
    "sortOrder": settings.get("background", {}).get("sortOrder", "az"),
    "thumbnailColumns": settings.get("background", {}).get("thumbnailColumns", 5),
}

settings_path.write_text(
    json.dumps(settings, ensure_ascii=False, indent=4) + "\n",
    encoding="utf-8",
)
print(f"已应用主题: {theme['name']}")
print("  - 背景: _black.jpg（纯色，替代 bedroom cyberpunk）")
print("  - 圆角气泡 + 顶栏毛玻璃 + 字号略小于默认（font_scale 0.92）")
print("硬刷新浏览器: Cmd+Shift+R")
PY
