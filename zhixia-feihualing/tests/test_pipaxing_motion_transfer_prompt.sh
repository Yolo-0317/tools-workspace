#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/pipaxing-empty-hand-15s/prompts/seedance-motion-transfer-v01.md"
readme="$project_dir/episodes/pipaxing-empty-hand-15s/README.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$prompt" "$readme" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing motion-transfer component $required"; exit 1; }
done

python3 - "$prompt" "$readme" "$history_file" <<'PY'
from pathlib import Path
import csv
import sys

prompt_text = Path(sys.argv[1]).read_text(encoding="utf-8")
readme = Path(sys.argv[2]).read_text(encoding="utf-8")
start = "<!-- SEEDANCE_PROMPT_START -->"
end = "<!-- SEEDANCE_PROMPT_END -->"
assert prompt_text.count(start) == 1
assert prompt_text.count(end) == 1
seedance = prompt_text.split(start, 1)[1].split(end, 1)[0]

required_prompt = [
    "@图片1与@视频1均为AI生成素材",
    "@图片1只提供栀夏的身份与敦煌服化道",
    "@视频1只提供完整动作顺序",
    "落脚、换重、胸腰方向、高低层次、手臂大轨迹、转身、抬腿和节奏",
    "尽量保持@视频1从开场到结尾的动作先后关系",
    "不继承@视频1中的人物",
    "双手全程清楚空置",
    "画面内不出现琵琶或其他乐器",
    "左右上臂后外侧",
    "不生成任何可辨识人声",
]
for phrase in required_prompt:
    assert phrase in seedance, f"missing transfer requirement: {phrase}"

for forbidden in [
    "38be6f1db204d8c478a61ae7a042229a",
    "/Users/",
    "0.000—1.800秒",
    "纵向惊弦",
    "横向回澜",
    "斜向裂帛",
]:
    assert forbidden not in seedance, f"pure-text or local detail leaked: {forbidden}"

assert "当前生成方案：迁移级" in readme
assert "motion-reference-v01.mp4" in readme
assert "seedance-v01.md` 保留为基础级历史方案" in readme

with Path(sys.argv[3]).open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
matches = [row for row in rows if row["episode"] == "pipaxing-empty-hand-15s"]
assert len(matches) == 1
row = matches[0]
assert row["climax_family"] == "参考视频整段动作迁移"
assert "迁移级当前方案" in row["notes"]
print("PASS: Pipaxing motion-transfer prompt is ready")
PY
