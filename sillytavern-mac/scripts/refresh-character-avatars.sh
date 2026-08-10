#!/usr/bin/env bash
# 重建角色卡 PNG + 清除 SillyTavern 头像缩略图/角色缓存（否则 UI 仍显示旧 default_Assistant）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ST_DATA="$ROOT/vendor/SillyTavern/data/default-user"
THUMB="$ST_DATA/thumbnails/avatar"
CACHE="$ROOT/vendor/SillyTavern/data/_cache/characters"
NAMES=(鬼瑶儿 战天风 苏晨)

echo "==> 确保头像源图存在"
if [[ ! -f "$ROOT/assets/characters/avatars/鬼瑶儿.png" ]]; then
  bash "$ROOT/scripts/fetch-character-avatars.sh"
else
  python3 "$ROOT/scripts/prepare-character-avatars.py"
fi

echo "==> 重建角色卡 PNG"
node "$ROOT/scripts/build-character-guiyaer.js"
node "$ROOT/scripts/build-character-zhantianfeng.js"
node "$ROOT/scripts/build-character-suchen.js"

echo "==> 清除 ST 缩略图缓存"
mkdir -p "$THUMB"
for n in "${NAMES[@]}"; do
  f="$THUMB/${n}.png"
  rm -f "$f"
done

echo "==> 预生成 ST 缩略图 (96x144)"
python3 << PY
from pathlib import Path
from PIL import Image

ROOT = Path("$ROOT")
chars = ROOT / "vendor/SillyTavern/data/default-user/characters"
thumb = ROOT / "vendor/SillyTavern/data/default-user/thumbnails/avatar"
thumb.mkdir(parents=True, exist_ok=True)
for name in ["鬼瑶儿", "战天风", "苏晨"]:
    src = chars / f"{name}.png"
    im = Image.open(src).convert("RGB")
    w, h = 96, 144
    scale = max(w / im.width, h / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    x0 = (nw - w) // 2
    y0 = (nh - h) // 2
    im = im.crop((x0, y0, x0 + w, y0 + h))
    dest = thumb / f"{name}.png"
    im.save(dest, format="PNG", optimize=True)
    print(f"  {dest.name} {dest.stat().st_size} bytes")
PY

echo "==> 清除角色 disk cache（避免旧 metadata）"
if [[ -d "$CACHE" ]]; then
  rm -f "$CACHE"/*
  echo "  cleared $CACHE"
fi

echo "==> 更新群头像引用"
python3 << PY
import json
from pathlib import Path
groups = Path("$ST_DATA/groups")
for gf in groups.glob("*.json"):
    g = json.loads(gf.read_text(encoding="utf-8"))
    if "鬼瑶儿.png" in (g.get("members") or []):
        g["avatar_url"] = "/thumbnail?type=avatar&file=鬼瑶儿.png"
        gf.write_text(json.dumps(g, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        print(f"  group {gf.name} avatar -> 鬼瑶儿.png")
PY

echo ""
echo "完成。请："
echo "  1. 重启 ST: launchctl kickstart -k gui/\$(id -u)/com.user.sillytavern"
echo "  2. 浏览器 Cmd+Shift+R 硬刷新"
echo "  3. 角色管理 -> 刷新（Force refresh）"
