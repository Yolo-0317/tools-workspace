#!/usr/bin/env bash
# 轻量世界书：开 worldInfo 注入，budget=1024，仅 LORE+玩家身份（章节 chunk 默认禁用）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ST_DATA="$ROOT/vendor/SillyTavern/data/default-user"
SETTINGS="$ST_DATA/settings.json"
WORLDBOOK="$ST_DATA/worlds/meinvjiangshan.json"
BUDGET="${WORLD_INFO_BUDGET:-1024}"

python3 << PY
import json
import re
from pathlib import Path

LORE_COMMENTS = {
    "世界观", "战天风", "鬼瑶儿", "苏晨", "白云裳", "九鬼门",
    "七大灾星", "煮天锅", "马横刀", "玄信", "假天子", "玩家身份",
}
CHUNK_RE = re.compile(r"^(序-\d+|第.+章(-\d+)?)$")

settings_path = Path("$SETTINGS")
world_path = Path("$WORLDBOOK")
budget = int("$BUDGET")

# --- settings: 开 worldInfo 注入 ---
settings = json.loads(settings_path.read_text(encoding="utf-8"))
wi = settings.setdefault("world_info_settings", {})
wi.setdefault("world_info", {})["globalSelect"] = ["meinvjiangshan"]
wi["world_info_budget"] = budget
wi["world_info_recursive"] = False
wi["world_info_depth"] = 2
wi["world_info_include_names"] = True
wi["world_info_match_whole_words"] = True
wi["world_info_character_strategy"] = 1
wi["world_info_max_recursion_steps"] = 0

oai = settings.setdefault("oai_settings", {})
for block in oai.get("prompt_order", []):
    for item in block.get("order", []):
        ident = item.get("identifier")
        if ident == "worldInfoBefore":
            item["enabled"] = True
        elif ident == "worldInfoAfter":
            item["enabled"] = False  # Before 足够；After 易挤占 jailbreak 前空间

# 全局 prompts 列表里若有 marker 项，保持不动
settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print(f"settings: globalSelect=meinvjiangshan, budget={budget}, worldInfoBefore=ON")

# --- 世界书：禁 chunk，留 LORE ---
if not world_path.exists():
    raise SystemExit(f"缺少世界书: {world_path}（先运行 build-worldbook-meinvjiangshan.py）")

data = json.loads(world_path.read_text(encoding="utf-8"))
entries = data.get("entries", {})
lore_on = chunk_off = 0
for entry in entries.values():
    comment = entry.get("comment", "")
    if comment in LORE_COMMENTS:
        entry["disable"] = False
        lore_on += 1
    elif CHUNK_RE.match(comment):
        entry["disable"] = True
        chunk_off += 1
    else:
        # 未知条目：保守禁用
        entry["disable"] = True
        chunk_off += 1

world_path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print(f"worldbook: LORE enabled={lore_on}, chunks disabled={chunk_off}")
PY

echo ""
echo "==> 完成。必做："
echo "  1. Cmd+Shift+R 硬刷新"
echo "  2. 群聊/单聊 -> 新建聊天（旧记录 prompt 已污染）"
echo "  3. Manual 模式：点气泡指定鬼瑶儿/苏晨回复"
echo "  budget=${BUDGET}，仅 12 条 LORE 注入；要某章原文可在世界书 UI 手动启用对应 chunk"
