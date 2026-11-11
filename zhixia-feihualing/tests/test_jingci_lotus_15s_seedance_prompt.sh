#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/jingci-lotus-15s/prompts/seedance-v01.md"
dance_history="$project_dir/operations/dance-design-history.csv"

[[ -s "$prompt" ]] || { print -u2 "FAIL: missing Jingci lotus Seedance prompt: $prompt"; exit 1; }
[[ -s "$dance_history" ]] || { print -u2 "FAIL: missing dance history: $dance_history"; exit 1; }

python3 - "$prompt" "$dance_history" <<'PY'
from pathlib import Path
import csv
import re
import sys

prompt_path = Path(sys.argv[1])
history_path = Path(sys.argv[2])
text = prompt_path.read_text(encoding="utf-8")
start_marker = "<!-- SEEDANCE_PROMPT_START -->"
end_marker = "<!-- SEEDANCE_PROMPT_END -->"

assert text.count(start_marker) == 1, "prompt must contain one start marker"
assert text.count(end_marker) == 1, "prompt must contain one end marker"
start = text.index(start_marker) + len(start_marker)
end = text.index(end_marker)
assert start < end, "prompt markers are out of order"
seedance = text[start:end]

required = [
    "@图片1与@图片2均为本项目原创虚拟角色",
    "@图片1是原创虚拟角色栀夏",
    "@图片2是原创虚拟东方墨灵阿砚",
    "15 秒",
    "9:16",
    "一镜到底",
    "尚未完成但可发力",
    "低位扫展",
    "一至两步",
    "不得持续奔跑",
    "水纹",
    "荷叶",
    "红荷",
    "摄影机围绕舞姿",
    "阿砚可以奔跑跟随",
    "不生成任何可辨识人声",
]
for phrase in required:
    assert phrase in seedance, f"missing Seedance requirement: {phrase}"

for time_range in ["0—1 秒", "1—5 秒", "5—10 秒", "10—15 秒"]:
    assert seedance.count(time_range) == 1, f"timeline range must appear once: {time_range}"

for poem_line in [
    "毕竟西湖六月中",
    "风光不与四时同",
    "接天莲叶无穷碧",
    "映日荷花别样红",
]:
    assert poem_line not in seedance, f"post-production poem leaked into Seedance prompt: {poem_line}"

for forbidden in ["assets/", ".png", ".jpg", "状态卡", "验收标准", "制作说明"]:
    assert forbidden not in seedance, f"production-only term leaked into Seedance prompt: {forbidden}"

assert not re.search(r"(^|[^A-Za-z0-9])[MHDS][0-9]{2}([^A-Za-z0-9]|$)", seedance), "internal code leaked into prompt"

with history_path.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
matches = [row for row in rows if row["episode"] == "jingci-lotus-15s"]
assert len(matches) == 1, "dance history must contain exactly one Jingci lotus entry"
entry = matches[0]
assert entry["climax_family"] == "低位扫展", "wrong climax family"
assert entry["rotation"] == "无完整旋转", "rotation must not be mandatory"
assert entry["status"] == "designed", "history entry must be designed"

print("PASS: Jingci lotus 15s Seedance prompt is ready")
PY
