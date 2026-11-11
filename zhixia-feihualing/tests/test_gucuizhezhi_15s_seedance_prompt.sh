#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/gucuizhezhi-15s/prompts/seedance-v01.md"
readme="$project_dir/episodes/gucuizhezhi-15s/README.md"
history_csv="$project_dir/operations/dance-design-history.csv"

for target in "$prompt" "$readme" "$history_csv"; do
  [[ -s "$target" ]] || {
    print -u2 -r -- "FAIL: missing required pilot artifact $target"
    exit 1
  }
done

python3 - "$prompt" "$readme" "$history_csv" <<'PY'
import csv
import re
import sys
from pathlib import Path

prompt_path, readme_path, history_path = map(Path, sys.argv[1:])
prompt_doc = prompt_path.read_text(encoding="utf-8")
readme = readme_path.read_text(encoding="utf-8")

start_marker = "<!-- SEEDANCE_PROMPT_START -->"
end_marker = "<!-- SEEDANCE_PROMPT_END -->"
if prompt_doc.count(start_marker) != 1 or prompt_doc.count(end_marker) != 1:
    raise SystemExit("FAIL: Seedance prompt must expose exactly one copyable block")

start = prompt_doc.index(start_marker) + len(start_marker)
end = prompt_doc.index(end_marker)
if start >= end:
    raise SystemExit("FAIL: Seedance prompt markers are reversed or empty")
body = prompt_doc[start:end].strip()

expected_first_line = "@图片1是本项目原创虚构数字角色栀夏，不对应任何现实人物、艺人或既有影视动漫角色。本次只上传图片1。"
if body.splitlines()[0] != expected_first_line:
    raise SystemExit("FAIL: copyable prompt does not start with the approved original-character declaration")

image_refs = set(re.findall(r"@图片\d+", body))
if image_refs != {"@图片1"}:
    raise SystemExit(f"FAIL: copyable prompt references unexpected uploads: {sorted(image_refs)}")

required_phrases = [
    "15 秒", "9:16", "一镜到底",
    "双环望仙式敦煌高髻", "孔雀蓝织锦短胸衣",
    "外层琥珀橙、内层浅青蓝", "手中无道具",
    "不得持续奔跑", "一次且仅一次", "真实金色细沙",
    "纵向", "横向", "纵深", "一条低位斜向后退主路径",
    "不生成任何可辨识人声",
]
for phrase in required_phrases:
    if phrase not in body:
        raise SystemExit(f"FAIL: copyable prompt is missing required generation instruction: {phrase}")

windows = [
    "0.000—1.800 秒", "1.800—4.800 秒", "4.800—7.000 秒",
    "7.000—10.000 秒", "10.000—13.000 秒", "13.000—15.000 秒",
]
for window in windows:
    if body.count(window) != 1:
        raise SystemExit(f"FAIL: timing window must occur exactly once: {window}")

poem_lines = [
    "平铺一合锦筵开", "连击三声画鼓催",
    "红蜡烛移桃叶起", "紫罗衫动柘枝来",
]
for line in poem_lines:
    if line in body:
        raise SystemExit(f"FAIL: poem line leaked into the Seedance generation block: {line}")
    if line not in readme:
        raise SystemExit(f"FAIL: README is missing the post-production poem line: {line}")

for forbidden in [
    "@图片2", "阿砚", "assets/", ".jpg", ".png", "状态卡",
    "验收标准", "制作说明", "高潮动作家族", "gucuizhezhi-15s",
]:
    if forbidden in body:
        raise SystemExit(f"FAIL: internal or forbidden term leaked into copyable prompt: {forbidden}")

for required_readme in [
    "首轮视频已复盘，v02 修正提示词完成；v02 视频尚未生成",
    "prompts/seedance-v01.md",
    "2026-08-29-gucuizhezhi-15s-pilot-design.md",
]:
    if required_readme not in readme:
        raise SystemExit(f"FAIL: README is missing delivery information: {required_readme}")

with history_path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    rows = list(reader)
    if len(reader.fieldnames or []) != 25:
        raise SystemExit("FAIL: dance history schema must remain 25 columns")

matches = [row for row in rows if row["episode"] == "gucuizhezhi-15s"]
if len(matches) != 1:
    raise SystemExit(f"FAIL: expected exactly one pilot history row, found {len(matches)}")
row = matches[0]
expected_fields = {
    "poem": "白居易《柘枝妓》",
    "climax_family": "三高潮序列",
    "rotation": "一次快速改面翻身；结尾只允许不完整半转",
    "peak_directions": "纵向；横向；纵深",
    "peak_windows": "0.000—1.800秒；4.800—7.000秒；10.000—13.000秒",
    "status": "designed",
}
for field, expected in expected_fields.items():
    if row[field] != expected:
        raise SystemExit(f"FAIL: unexpected pilot history {field}: {row[field]!r}")

print("PASS: 《鼓催柘枝》Seedance prompt, post-production boundary, and unique history row are valid")
PY
