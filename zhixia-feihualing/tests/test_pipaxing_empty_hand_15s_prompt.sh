#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/pipaxing-empty-hand-15s/README.md"
prompt="$project_dir/episodes/pipaxing-empty-hand-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing Pipaxing component $required"; exit 1; }
done

python3 - "$readme" "$prompt" "$history_file" <<'PY'
from pathlib import Path
import csv
import sys

readme = Path(sys.argv[1]).read_text(encoding="utf-8")
text = Path(sys.argv[2]).read_text(encoding="utf-8")
start_marker = "<!-- SEEDANCE_PROMPT_START -->"
end_marker = "<!-- SEEDANCE_PROMPT_END -->"

assert text.count(start_marker) == 1, "prompt must contain one start marker"
assert text.count(end_marker) == 1, "prompt must contain one end marker"
seedance = text.split(start_marker, 1)[1].split(end_marker, 1)[0]

required_prompt = [
    "原创虚构角色栀夏",
    "15秒、9:16竖屏、一镜到底",
    "左右上臂后外侧",
    "双手全程清楚空置",
    "0.000—1.800秒",
    "0.300秒内踏步换重",
    "1.800—4.800秒",
    "4.800—7.000秒",
    "7.000—10.000秒",
    "10.000—13.200秒",
    "13.200—15.000秒",
    "纵向提展",
    "横向反向弧",
    "前低后高的斜向纵深长线",
    "真实长影",
    "画面内不出现琵琶或其他乐器",
    "不生成任何可辨识人声",
]
for phrase in required_prompt:
    assert phrase in seedance, f"missing requirement: {phrase}"

required_readme = [
    "唐·白居易《琵琶行》",
    "大弦嘈嘈如急雨",
    "大珠小珠落玉盘",
    "敦煌十六舞 v03",
    "双手全程空着",
    "画面零乐器",
]
for phrase in required_readme:
    assert phrase in readme, f"README missing requirement: {phrase}"

for forbidden in [
    "38be6f1db204d8c478a61ae7a042229a",
    "微信视频号",
    "复刻热门舞蹈",
    "照着参考视频跳",
    "@视频1",
    "assets/characters/",
    ".jpg",
    ".png",
]:
    assert forbidden not in seedance, f"reference or internal detail leaked: {forbidden}"

with Path(sys.argv[3]).open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
matches = [row for row in rows if row["episode"] == "pipaxing-empty-hand-15s"]
assert len(matches) == 1, "dance history must contain one Pipaxing entry"
row = matches[0]
assert row["status"] == "designed", "Pipaxing status must be designed"
assert row["carrier"] == "蓝橙双层飘带与真实长影"

print("PASS: Pipaxing prompt package is complete")
PY
