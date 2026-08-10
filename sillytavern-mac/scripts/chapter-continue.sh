#!/usr/bin/env bash
# 指定一章或预设场景 -> 续写助手 v2 + 写作向 API 设置
# 用法: bash scripts/chapter-continue.sh 70
#       bash scripts/chapter-continue.sh --scene 西风行宫奶问
#       CONTINUE_NEXT_HINT=0 bash scripts/chapter-continue.sh --scene 西风行宫奶问
#       bash scripts/chapter-continue.sh --list
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS="$ROOT/vendor/SillyTavern/data/default-user/settings.json"
TOKENS="${CONTINUE_MAX_TOKENS:-1500}"
CTX="${CONTINUE_MAX_CONTEXT:-24576}"

if [[ "${1:-}" == "--list" ]] || [[ "${1:-}" == "-l" ]]; then
  echo "==> 章节"
  python3 "$ROOT/scripts/extract-chapter.py" --list
  echo ""
  echo "==> 预设场景"
  python3 "$ROOT/scripts/extract-scene.py" --list
  exit 0
fi

if [[ "${1:-}" == "--scene" ]] || [[ "${1:-}" == "-s" ]]; then
  if [[ -z "${2:-}" ]]; then
    echo "用法: bash scripts/chapter-continue.sh --scene <场景id>"
    echo "示例: bash scripts/chapter-continue.sh --scene 西风行宫奶问"
    echo "说明: 只更新/注册该场景，主开场仍为破庙70（或 current.json 里的 primary_id）"
    python3 "$ROOT/scripts/extract-scene.py" --list
    exit 1
  fi
  python3 "$ROOT/scripts/extract-scene.py" "$2"
else
  if [[ -z "${1:-}" ]]; then
    echo "用法: bash scripts/chapter-continue.sh <章序或章名>"
    echo "      bash scripts/chapter-continue.sh --scene <场景id>"
    echo ""
    echo "示例: bash scripts/chapter-continue.sh 70          # 破庙线"
    echo "      bash scripts/chapter-continue.sh --scene 西风行宫奶问"
    echo "      bash scripts/chapter-continue.sh --list"
    exit 1
  fi
  python3 "$ROOT/scripts/extract-chapter.py" "$1"
fi

node "$ROOT/scripts/build-character-xuxie-assistant.js"

python3 << PY
import json
from pathlib import Path

settings_path = Path("$SETTINGS")
settings = json.loads(settings_path.read_text(encoding="utf-8"))

settings["username"] = "作者"
settings["active_character"] = "续写助手.png"
settings["active_group"] = None
settings["max_context"] = int("$CTX")

oai = settings.setdefault("oai_settings", {})
oai["openai_max_context"] = int("$CTX")
oai["openai_max_tokens"] = int("$TOKENS")
oai["temp_openai"] = 0.68
oai["top_p_openai"] = 0.9
oai["freq_pen_openai"] = 0.35
oai["openrouter_middleout"] = "off"

wi = settings.setdefault("world_info_settings", {})
wi.setdefault("world_info", {})["globalSelect"] = []
wi["world_info_budget"] = 0
for block in oai.get("prompt_order", []):
    for item in block.get("order", []):
        if item.get("identifier") in ("worldInfoBefore", "worldInfoAfter"):
            item["enabled"] = False

for p in oai.get("prompts", []):
    if p.get("identifier") == "main":
        p["content"] = (
            "Continue the Chinese wuxia novel 《美女江山一锅煮》 "
            "using LORE, author style rules, and the chapter in {{char}}'s description. "
            "Output ONLY new prose; fictional creative writing."
        )
    elif p.get("identifier") == "jailbreak":
        p["content"] = (
            "[系统：续写助手 v2。遵循角色卡内 LORE、笔法要点与本章原文衔接续写。"
            "仅输出中文小说正文。禁止出戏、现代梗、日语、重复原文、一次写穿下一章全文。]"
        )

settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print(f"settings: 续写 v2 ctx={settings['max_context']} max_tokens={oai['openai_max_tokens']}")
PY

rm -f "$ROOT/vendor/SillyTavern/data/default-user/thumbnails/avatar/续写助手.png" 2>/dev/null || true

echo ""
echo "==> 续写助手 v2 完成"
echo "  · 12 条 LORE + 笔法要点已写入角色卡"
echo "  · 若 data/xuxie/next-chapter-hints.json 有本章条目，已附带下一章走向"
echo ""
echo "  1. Cmd+Shift+R 硬刷新 ST"
echo "  2. 角色「续写助手」-> 新建聊天"
echo "  3. 发：「从本章末尾续写约 800 字」或「继续」"
echo "  4. 恢复 RP: bash scripts/configure-meinvjiangshan-rp-stable.sh"
echo ""
echo "破庙线: bash scripts/chapter-continue.sh 69|70|71"
echo "追加场景: bash scripts/chapter-continue.sh --scene 西风行宫奶问  # 不替换主开场"
echo "改主开场: XUXIE_PRIMARY=破庙70 bash scripts/chapter-continue.sh  # 或 extract 70 后自动设 primary_id"
