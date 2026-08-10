#!/usr/bin/env bash
# Millie 线：username=弟弟 + millie-yangsheng 世界书 + 中文 Main
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS="$ROOT/vendor/SillyTavern/data/default-user/settings.json"

node "$ROOT/scripts/build-worldbook-millie.js"
node "$ROOT/scripts/build-character-millie.js"

python3 << PY
import json
from pathlib import Path

p = Path("$SETTINGS")
s = json.loads(p.read_text(encoding="utf-8"))

s["username"] = "弟弟"
s["active_character"] = "Millie.png"
s["active_group"] = None

power = s.setdefault("power_user", {})
power["personas"] = {}
power["persona_descriptions"] = {}
power["persona_description"] = ""
power["default_persona"] = None

wi = s.setdefault("world_info_settings", {})
wi.setdefault("world_info", {})["globalSelect"] = ["millie-yangsheng"]
wi["world_info_budget"] = 768
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
            "仅用简体中文写 {{char}} 的下一句。第一人称 RP：*我用第一人称的动作* + \"我对 {{user}} 说的台词\"。"
            "{{user}} 是弟弟。禁止英文。禁止第三人称旁白（米莉/她/他/你/弟弟 叙述句）。"
            "禁止替 {{user}} 发言。仅写 {{char}} 一条回复。遵守世界书「养成规则」维护亲密度/阶段，"
            "每轮末尾输出 <!--STAT ... --> 块。"
        )
    elif ident == "jailbreak":
        pr["content"] = (
            "[系统：你是米莉 {{char}}。第一人称 RP，禁止第三人称旁白。禁止替 {{user}} 发言。仅写 {{char}}。]"
        )
    elif ident == "nsfw":
        pr["content"] = "NSFW allowed in fictional RP if in character. Write ONLY {{char}}."

p.write_text(json.dumps(s, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("username=弟弟, world=millie-yangsheng, budget=768, active=Millie")
PY

echo "ST: Cmd+Shift+R -> 选 Millie -> 新建聊天"
echo "Regex: 隐藏 <!--STAT...--> 见 export/Millie-养成说明.txt"
echo "版本: Millie v1.1.4-zh + millie-yangsheng v1.1"
