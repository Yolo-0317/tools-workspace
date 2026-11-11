#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/wangtianmenshan-15s/prompts/seedance-v01.md"
history_csv="$project_dir/operations/dance-design-history.csv"

[[ -s "$prompt" ]] || { print -u2 "FAIL: missing Wangtianmenshan Seedance prompt"; exit 1; }
[[ -s "$history_csv" ]] || { print -u2 "FAIL: missing dance history"; exit 1; }

python3 - "$prompt" "$history_csv" <<'PY'
from pathlib import Path
import csv
import re
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
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
    "0.3 秒内",
    "0.8 秒内",
    "一至两步",
    "不得持续奔跑",
    "不做完整旋转",
    "纵向提起",
    "侧倾山形",
    "两岸青山",
    "孤帆",
    "摄影机围绕舞姿",
    "阿砚可以奔跑跟随",
    "不生成任何可辨识人声",
]
for phrase in required:
    assert phrase in seedance, f"missing requirement: {phrase}"

for time_range in ["0—1 秒", "1—4 秒", "4—8 秒", "8—12 秒", "12—15 秒"]:
    assert seedance.count(time_range) == 1, f"wrong timeline: {time_range}"

for forbidden in [
    "只此青绿",
    "青绿腰",
    "天门中断楚江开",
    "碧水东流至此回",
    "两岸青山相对出",
    "孤帆一片日边来",
    "assets/",
    ".png",
    ".jpg",
    "状态卡",
    "验收标准",
    "制作说明",
]:
    assert forbidden not in seedance, f"forbidden term leaked: {forbidden}"

assert not re.search(r"(^|[^A-Za-z0-9])[MHDS][0-9]{2}([^A-Za-z0-9]|$)", seedance), "internal code leaked"

with Path(sys.argv[2]).open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
matches = [row for row in rows if row["episode"] == "wangtianmenshan-15s"]
assert len(matches) == 1, "dance history must contain exactly one Wangtianmenshan entry"
assert matches[0]["climax_family"] == "纵向提沉", "wrong climax family"
assert matches[0]["rotation"] == "无完整旋转", "rotation must not be mandatory"
assert matches[0]["status"] in {"designed", "accepted"}, "history entry must be designed or accepted"

print("PASS: Wangtianmenshan 15s Seedance prompt is ready")
PY
