#!/usr/bin/env bash
# 《美女江山》群聊推荐设置：Pooled 轮流一人一句，关双世界书冲突
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ST_DATA="$ROOT/vendor/SillyTavern/data/default-user"
SETTINGS="$ST_DATA/settings.json"
GROUPS_DIR="$ST_DATA/groups"

python3 << 'PY'
import json
from pathlib import Path

root = Path("/Users/yolo/dev/yolo/tools-workspace/sillytavern-mac/vendor/SillyTavern/data/default-user")
settings_path = root / "settings.json"
groups_dir = root / "groups"

# 1) 全局世界书：群聊只留 meinvjiangshan（去掉 shaonianabin 避免串台）
settings = json.loads(settings_path.read_text(encoding="utf-8"))
wi = settings.setdefault("world_info_settings", {}).setdefault("world_info", {})
sel = wi.get("globalSelect", [])
new_sel = [x for x in sel if x != "shaonianabin"]
if "meinvjiangshan" not in new_sel:
    new_sel.append("meinvjiangshan")
wi["globalSelect"] = new_sel
wi_settings = settings["world_info_settings"]
wi_settings["world_info_budget"] = min(wi_settings.get("world_info_budget", 25), 12)
wi_settings["world_info_recursive"] = False
wi_settings["world_info_depth"] = 2
settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("settings: globalSelect =", new_sel)
print("settings: world_info_budget=12, recursive=false")

# 2) 找到含鬼瑶儿+战天风+苏晨的群，改 Pooled order (3)
targets = {"鬼瑶儿.png", "战天风.png", "苏晨.png"}
for gf in groups_dir.glob("*.json"):
    g = json.loads(gf.read_text(encoding="utf-8"))
    members = set(g.get("members") or [])
    if not targets.issubset(members):
        continue
    g["name"] = g.get("name") or "美女江山"
    if g["name"].startswith("Group:"):
        g["name"] = "美女江山·三美"
    g["activation_strategy"] = 3  # Pooled order：每轮只一人开口
    g["generation_mode"] = 0      # Swap character cards
    g["allow_self_responses"] = False
    gf.write_text(json.dumps(g, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"group {gf.name}: activation_strategy=Pooled(3), name={g['name']}")
PY

echo ""
echo "完成。请："
echo "  1. 硬刷新 ST"
echo "  2. 新建群聊（旧聊天记录 prompt 已乱，建议 Group -> View past chats -> 新建）"
echo "  3. 更佳：群成员只加鬼瑶儿+苏晨，Persona 扮演战天风（User Settings 写身份）"
