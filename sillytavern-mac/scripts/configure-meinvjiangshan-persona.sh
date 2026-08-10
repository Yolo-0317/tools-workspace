#!/usr/bin/env bash
# 选美女江山世界书 / 相关角色时：Persona 默认战天风
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS="$ROOT/vendor/SillyTavern/data/default-user/settings.json"

python3 << PY
import json
from pathlib import Path

settings_path = Path("$SETTINGS")
settings = json.loads(settings_path.read_text(encoding="utf-8"))

settings["username"] = "战天风"

persona_text = (
    "我是战天风，《美女江山一锅煮》男主。滑头机变、嘴甜讲义气，江湖武侠口语，偶尔油嘴滑舌。"
    "鬼瑶儿、苏晨、白云裳在场时是别的角色，不是我代写。"
    "用户选 meinvjiangshan 世界书或本系列角色卡时，默认以此身份扮演。"
)

power = settings.setdefault("power_user", {})
personas = power.setdefault("personas", {})
desc = power.setdefault("persona_descriptions", {})
personas["user-default.png"] = persona_text
desc["user-default.png"] = persona_text
power["persona_description"] = persona_text

settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("Persona + username 已设为战天风")
PY

echo "ST: User Settings 确认 Persona 描述已更新；硬刷新后开新聊。"
