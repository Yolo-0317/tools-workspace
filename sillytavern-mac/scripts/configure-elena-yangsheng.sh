#!/usr/bin/env bash
# 艾琳娜养成线：username=侄子 + 开 elena-yangsheng 世界书 + 中文 Main
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ST_DATA="$ROOT/vendor/SillyTavern/data/default-user"
SETTINGS="$ST_DATA/settings.json"

node "$ROOT/scripts/build-worldbook-elena.js"
node "$ROOT/scripts/build-character-elena.js"

python3 << PY
import json
from pathlib import Path

p = Path("$SETTINGS")
s = json.loads(p.read_text(encoding="utf-8"))

s["username"] = "侄子"
s["active_character"] = "艾琳娜.png"
s["active_group"] = None

power = s.setdefault("power_user", {})
power["personas"] = {}
power["persona_descriptions"] = {}
power["persona_description"] = ""
power["default_persona"] = None

wi = s.setdefault("world_info_settings", {})
wi.setdefault("world_info", {})["globalSelect"] = []
wi["world_info_budget"] = 256
wi["world_info_recursive"] = False
wi["world_info_depth"] = 2

oai = s.setdefault("oai_settings", {})
for block in oai.get("prompt_order", []):
    for item in block.get("order", []):
        if item.get("identifier") == "personaDescription":
            item["enabled"] = False
        if item.get("identifier") == "worldInfoBefore":
            item["enabled"] = True
        if item.get("identifier") == "worldInfoAfter":
            item["enabled"] = False

for pr in oai.get("prompts", []):
    ident = pr.get("identifier")
    if ident == "main":
        pr["content"] = (
            "【接话优先】先回应 {{user}} 最新一条，再写剧情。禁止复制上一轮句子。禁止无视用户输入。"
            "仅用简体中文写 {{char}} 的下一句。第一人称 RP：*我用第一人称的动作* + \"我对 {{user}} 说的台词\"。"
            "{{user}} 是侄子。禁止英文。禁止第三人称旁白。禁止替 {{user}} 发言。只写 {{char}} 一条回复。"
            "聊久后勿再写撞见/假阳具开场。"
        )
    elif ident == "jailbreak":
        pr["content"] = (
            "[系统：你是艾琳娜 {{char}}。第一人称 RP，禁止第三人称旁白。禁止替 {{user}} 发言。仅写 {{char}}。]"
        )
    elif ident == "nsfw":
        pr["content"] = "NSFW allowed in fictional RP if in character. Write ONLY {{char}}."

p.write_text(json.dumps(s, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("username=侄子, world=embedded-only(勿global), budget=256, active=艾琳娜")
PY

echo "ST: Cmd+Shift+R -> 选 艾琳娜 -> 新建聊天"
echo "世界书已嵌入 PNG，勿再 globalSelect elena-yangsheng"
echo "版本: 艾琳娜 v3.0.0-zh + elena-yangsheng v2.0"
