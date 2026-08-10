#!/usr/bin/env bash
# 调整 SillyTavern 全局字号（power_user.font_scale，默认 1.0）
# 用法: bash scripts/configure-ui-font.sh          # 默认 0.9
#       FONT_SCALE=0.85 bash scripts/configure-ui-font.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS="$ROOT/vendor/SillyTavern/data/default-user/settings.json"
SCALE="${FONT_SCALE:-0.9}"

if [[ ! -f "$SETTINGS" ]]; then
  echo "错误: 未找到 $SETTINGS"
  exit 1
fi

python3 << PY
import json
from pathlib import Path

scale = float("$SCALE")
if not 0.5 <= scale <= 1.5:
    raise SystemExit("FONT_SCALE 须在 0.5～1.5 之间")

path = Path("$SETTINGS")
settings = json.loads(path.read_text(encoding="utf-8"))
settings.setdefault("power_user", {})["font_scale"] = scale
path.write_text(json.dumps(settings, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print(f"font_scale = {scale}（1.0 为默认；越小字越小）")
print("Cmd+Shift+R 硬刷新 ST 后生效")
print("也可在 ST：用户设置 -> 外观 -> Font Scale 微调")
PY
