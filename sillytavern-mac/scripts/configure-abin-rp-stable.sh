#!/usr/bin/env bash
# 少年阿宾 RP：username=阿宾 + shaonianabin 世界书（LORE + 第一篇 chunk）+ 房东太太
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ST_DATA="$ROOT/vendor/SillyTavern/data/default-user"
SETTINGS="$ST_DATA/settings.json"
WORLDBOOK="$ST_DATA/worlds/shaonianabin.json"
SECRETS="$ST_DATA/secrets.json"
OPENROUTER_MODEL="${OPENROUTER_MODEL:-nousresearch/hermes-4-70b}"
BUDGET="${WORLD_INFO_BUDGET:-1024}"

echo "==> 重建房东太太角色卡"
node "$ROOT/scripts/build-character-fangdong.js"

if [[ -f "$SECRETS" ]]; then
  KEY=$(python3 -c "import json; print(json.load(open('$SECRETS'))['api_key_openrouter'][0]['value'])")
  OPENROUTER_PROFILE=nsfw \
  OPENROUTER_MODEL="$OPENROUTER_MODEL" \
  OPENROUTER_API_KEY="$KEY" \
  bash "$ROOT/scripts/configure-openrouter.sh"
fi

python3 << PY
import json
from pathlib import Path

LORE = {"世界观", "阿宾", "钰慧", "篇章索引", "RP格式"}
CHAPTER_ONE_PREFIX = "（一）房东太太"  # RP 模式不注入篇块（第三人称原文会带偏模型）
model = "$OPENROUTER_MODEL"
budget = int("$BUDGET")

RP_FORMAT = """[聊天 RP 格式 · 房东太太回复时遵守]
你是胡太太本人，用第一人称与租客阿宾（{{user}}）对话。
- 动作用 *星号* 写「我」：*从冰箱拿出可乐*
- 台词用引号直接说：\"小弟，谢谢。\"
- 语言：仅简体中文，禁止任何英文单词或英文句子。
- 禁止小说旁白：不要写「胡太太」「她」「阿宾」「他」作叙述者；不要写阿宾的动作或心理。
- 禁止一次写长篇第三人称故事。"""

settings_path = Path("$SETTINGS")
world_path = Path("$WORLDBOOK")

settings = json.loads(settings_path.read_text(encoding="utf-8"))

# {{user}} 宏 = username
settings["username"] = "阿宾"
settings["active_character"] = "房东太太.png"
settings["active_group"] = None
settings["max_context"] = 8192

oai = settings.setdefault("oai_settings", {})
oai["openrouter_model"] = model
oai["chat_completion_source"] = "openrouter"
oai["temp_openai"] = 0.78
oai["top_p_openai"] = 0.9
oai["repetition_penalty_openai"] = 1.12
oai["freq_pen_openai"] = 0.3
oai["openai_max_context"] = 8192
oai["openai_max_tokens"] = 320
oai["openrouter_middleout"] = "off"
oai["openrouter_allow_fallbacks"] = False

JAIL = (
    "[系统：仅简体中文输出，禁止任何英文。"
    "第一人称 chat RP，不是小说旁白。"
    "只写 {{char}}（胡太太）：*我的动作* + \"对 {{user}} 说的台词\"。"
    "{{user}}=阿宾（小弟）。禁止第三人称旁白；禁止写 {{user}} 的动作心理。"
    "禁止：英文、武侠、日语、出戏。台湾90年代口语。80～220字。]"
)

for p in oai.get("prompts", []):
    ident = p.get("identifier")
    if ident == "main":
        p["content"] = (
            "仅用简体中文写 {{char}} 的下一句回复。"
            "第一人称 chat RP：*我的动作* + \"台词\"。{{user}} 是阿宾。"
            "禁止英文。禁止第三人称旁白。禁止替 {{user}} 发言。"
        )
    elif ident == "jailbreak":
        p["content"] = JAIL
    elif ident == "nsfw":
        p["content"] = (
            "允许成人向虚构 RP。{{user}}=阿宾。"
            "仅简体中文写 {{char}}（胡太太），禁止英文。"
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
wi.setdefault("world_info", {})["globalSelect"] = ["shaonianabin"]
# 去掉美女江山，避免串台
wi["world_info_budget"] = budget
wi["world_info_recursive"] = False
wi["world_info_depth"] = 2
wi["world_info_include_names"] = True
wi["world_info_match_whole_words"] = False
wi["world_info_character_strategy"] = 1
wi["world_info_max_recursion_steps"] = 0

persona = (
    "我是阿宾，《少年阿宾》男主。台北私立专校学生，租住在胡太太家顶楼学生房。"
    "第一人称「我」思考，对话用台湾口语。"
    "当前篇目：（一）房东太太；关系：房东与租客，渐趋暧昧。"
    "勿混钰慧、学姐等未出场人物。"
)
power = settings.setdefault("power_user", {})
power.setdefault("personas", {})["user-default.png"] = persona
power.setdefault("persona_descriptions", {})["user-default.png"] = persona
power["persona_description"] = persona

settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print(f"settings: user=阿宾, active=房东太太.png, model={model}, budget={budget}")

if not world_path.exists():
    raise SystemExit(f"缺少世界书: {world_path}（先运行 python3 scripts/build-worldbook-shaonianabin.py）")

data = json.loads(world_path.read_text(encoding="utf-8"))
entries = data.setdefault("entries", {})

# 注入/更新 RP格式 LORE（constant）
rp_uid = None
for k, entry in entries.items():
    if entry.get("comment") == "RP格式":
        rp_uid = k
        break
if rp_uid is None:
    rp_uid = str(max((int(k) for k in entries), default=-1) + 1)
entries[rp_uid] = {
    "uid": int(rp_uid),
    "key": ["RP", "格式", "第一人称", "房东太太", "聊天"],
    "keysecondary": [],
    "comment": "RP格式",
    "content": RP_FORMAT,
    "constant": True,
    "selective": False,
    "order": 50,
    "position": 0,
    "disable": False,
    "displayIndex": int(rp_uid),
    "addMemo": True,
    "group": "少年阿宾",
    "groupOverride": False,
    "groupWeight": 100,
    "sticky": 0,
    "cooldown": 0,
    "delay": 0,
    "probability": 100,
    "depth": 4,
    "useProbability": True,
    "role": None,
    "vectorized": False,
    "excludeRecursion": False,
    "preventRecursion": False,
    "delayUntilRecursion": False,
    "scanDepth": None,
    "caseSensitive": None,
    "matchWholeWords": None,
    "useGroupScoring": None,
    "automationId": "",
}

lore_on = ch1_on = off = 0
for entry in entries.values():
    comment = entry.get("comment", "")
    if comment in LORE:
        entry["disable"] = False
        lore_on += 1
    else:
        entry["disable"] = True
        off += 1
        if comment.startswith(CHAPTER_ONE_PREFIX):
            ch1_on += 1

world_path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print(f"worldbook: LORE={lore_on} (含 RP格式), 篇块已禁用={off} (含房东太太 {ch1_on} 条)")
PY

rm -f "$ST_DATA/thumbnails/avatar/房东太太.png" 2>/dev/null || true

echo ""
echo "==> 少年阿宾 · 房东太太 就绪"
echo "  1. Cmd+Shift+R 硬刷新 ST"
echo "  2. 确认 User name = 阿宾，World Info 仅 shaonianabin"
echo "  3. 选角色「房东太太」-> 新建聊天（勿用旧聊）"
echo "  4. 开场可切换：扫除后可乐 / 楼梯初遇 / 人字梯春光"
echo "  5. 若仍第三人称旁白：确认新建聊天（旧记录已被污染）"
echo "  6. 恢复美女江山: bash scripts/configure-meinvjiangshan-rp-stable.sh"
