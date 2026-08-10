#!/usr/bin/env bash
# 美女江山 RP 稳定配置：username=战天风 + LORE 轻量 worldInfo + 关 middle-out + 群 Manual
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ST_DATA="$ROOT/vendor/SillyTavern/data/default-user"
SETTINGS="$ST_DATA/settings.json"
WORLDBOOK="$ST_DATA/worlds/meinvjiangshan.json"
SECRETS="$ST_DATA/secrets.json"
GROUPS="$ST_DATA/groups"
OPENROUTER_MODEL="${OPENROUTER_MODEL:-nousresearch/hermes-4-70b}"
BUDGET="${WORLD_INFO_BUDGET:-1024}"

# OpenRouter 模型
if [[ -f "$SECRETS" ]]; then
  KEY=$(python3 -c "import json; print(json.load(open('$SECRETS'))['api_key_openrouter'][0]['value'])")
  OPENROUTER_PROFILE=nsfw \
  OPENROUTER_MODEL="$OPENROUTER_MODEL" \
  OPENROUTER_API_KEY="$KEY" \
  bash "$ROOT/scripts/configure-openrouter.sh"
fi

python3 << PY
import json
import re
from pathlib import Path

LORE = {
    "世界观", "战天风", "鬼瑶儿", "苏晨", "白云裳", "九鬼门",
    "七大灾星", "煮天锅", "马横刀", "玄信", "假天子", "玩家身份",
}
CHUNK_RE = re.compile(r"^(序-\d+|第.+章(-\d+)?)$")
model = "$OPENROUTER_MODEL"
budget = int("$BUDGET")

settings_path = Path("$SETTINGS")
settings = json.loads(settings_path.read_text(encoding="utf-8"))

# {{user}} 宏 = username，不是 Persona 文本
settings["username"] = "战天风"

oai = settings.setdefault("oai_settings", {})
oai["openrouter_model"] = model
oai["chat_completion_source"] = "openrouter"
oai["temp_openai"] = 0.75
oai["top_p_openai"] = 0.9
oai["repetition_penalty_openai"] = 1.15
oai["freq_pen_openai"] = 0.35
oai["openai_max_context"] = 8192
oai["openai_max_tokens"] = 280
oai["openrouter_middleout"] = "off"
oai["openrouter_allow_fallbacks"] = False
settings["max_context"] = 8192

JAIL = (
    "[系统：严格扮演 {{char}}。仅用中文武侠口语写 {{char}} 的动作（*星号*）与台词（引号）。"
    "{{user}} 即战天风，勿写 User 或路人。"
    "禁止：替战天风/苏晨/鬼瑶儿/他人发言、日语、本宫、现代梗、动漫游戏、科技、英文大段、"
    "tool_call、、<|im_start|>、元评论、出戏、茶道/东瀛等非本书设定。"
    "群聊只输出 {{char}} 一人，80～200 字。成人向虚构 RP 允许，勿拒绝说教。]"
)

for p in oai.get("prompts", []):
    ident = p.get("identifier")
    if ident == "main":
        p["content"] = (
            "Write ONLY {{char}}'s next reply in Chinese wuxia novel "
            "《美女江山一锅煮》. {{user}} is 战天风. Fictional RP."
        )
    elif ident == "jailbreak":
        p["content"] = JAIL
    elif ident == "nsfw":
        p["content"] = (
            "NSFW/Smut allowed in fictional wuxia RP. {{user}}=战天风. "
            "Stay in character. Write ONLY {{char}} in Chinese."
        )

for block in oai.get("prompt_order", []):
    for item in block.get("order", []):
        ident = item.get("identifier")
        if ident == "worldInfoBefore":
            item["enabled"] = True
        elif ident == "worldInfoAfter":
            item["enabled"] = False
        elif ident == "personaDescription":
            item["enabled"] = True

wi = settings.setdefault("world_info_settings", {})
wi.setdefault("world_info", {})["globalSelect"] = ["meinvjiangshan"]
wi["world_info_budget"] = budget
wi["world_info_recursive"] = False
wi["world_info_depth"] = 2

persona = (
    "我是战天风，《美女江山一锅煮》男主。滑头机变、嘴甜讲义气，江湖武侠口语。"
    "鬼瑶儿、苏晨在场时是不同角色，不是我代写。"
)
power = settings.setdefault("power_user", {})
power.setdefault("personas", {})["user-default.png"] = persona
power.setdefault("persona_descriptions", {})["user-default.png"] = persona
power["persona_description"] = persona

settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print(f"settings: user=战天风, model={model}, budget={budget}, middleout=off, temp=0.75")

# 世界书 chunk 禁、LORE 开
world_path = Path("$WORLDBOOK")
data = json.loads(world_path.read_text(encoding="utf-8"))
for entry in data.get("entries", {}).values():
    entry["disable"] = entry.get("comment") not in LORE
world_path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("worldbook: 12 LORE on, chunks off")

# 群 Manual
groups_dir = Path("$GROUPS")
for gf in groups_dir.glob("*.json"):
    g = json.loads(gf.read_text(encoding="utf-8"))
    if not {"鬼瑶儿.png", "苏晨.png"}.intersection(g.get("members") or []):
        continue
    g["members"] = [m for m in g["members"] if m != "战天风.png"]
    g["activation_strategy"] = 2
    g["allow_self_responses"] = False
    gf.write_text(json.dumps(g, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"group: Manual, members={g['members']}")
PY

echo ""
echo "==> 完成。必做（否则仍会乱）："
echo "  1. Cmd+Shift+R 硬刷新"
echo "  2. 删除旧聊 / 新建聊天（旧记录已 tainted，勿继续）"
echo "  3. User Settings 确认：User name=战天风，World Info budget=1024，Middle-out=Off"
echo "  4. 群聊 Manual：点气泡指定角色；勿只发「继续」"
echo "  5. 勿在 ST 里把 World Info budget 拖成 25（会再次截断 LORE）"
