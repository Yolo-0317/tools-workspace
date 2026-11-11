#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md"
history_csv="$project_dir/operations/dance-design-history.csv"

for target in "$prompt" "$history_csv"; do
  [[ -s "$target" ]] || {
    print -u2 -r -- "FAIL: missing required artifact $target"
    exit 1
  }
done

python3 - "$prompt" "$history_csv" <<'PY'
import csv
import re
import sys
from pathlib import Path

prompt_path, history_path = map(Path, sys.argv[1:])
prompt_doc = prompt_path.read_text(encoding="utf-8")

start_marker = "<!-- SEEDANCE_PROMPT_START -->"
end_marker = "<!-- SEEDANCE_PROMPT_END -->"
if prompt_doc.count(start_marker) != 1 or prompt_doc.count(end_marker) != 1:
    raise SystemExit("FAIL: Seedance prompt must expose exactly one copyable block")

start = prompt_doc.index(start_marker) + len(start_marker)
end = prompt_doc.index(end_marker)
if start >= end:
    raise SystemExit("FAIL: Seedance prompt markers are reversed or empty")
body = prompt_doc[start:end].strip()

expected_first_line = (
    "@图片1和@图片2都是本项目原创虚构数字角色栀夏，"
    "不对应任何现实人物、艺人或既有影视动漫角色。"
)
if body.splitlines()[0] != expected_first_line:
    raise SystemExit("FAIL: copyable prompt has the wrong original-character declaration")

image_refs = set(re.findall(r"@图片\d+", body))
if image_refs != {"@图片1", "@图片2"}:
    raise SystemExit(f"FAIL: unexpected upload references: {sorted(image_refs)}")

required_phrases = [
    "15 秒", "9:16", "同一连续镜头",
    "玄武岩海上长台", "两座盐蚀巨石构件", "唯一一面白帆",
    "深侧弓", "横向换重", "斜向探海", "纵向提跃",
    "真实晨光在海面的狭长金色反射", "同一股潮雾",
    "侧前方略低中全景", "沿玄武岩长台外缘斜向后退",
    "不生成任何可辨识人声",
]
for phrase in required_phrases:
    if phrase not in body:
        raise SystemExit(f"FAIL: copyable prompt is missing required instruction: {phrase}")

windows = [
    "0.000—1.800 秒", "1.800—4.800 秒",
    "4.800—7.200 秒", "7.200—10.000 秒",
    "10.000—13.430 秒", "13.430—15.000 秒",
]
for window in windows:
    if body.count(window) != 1:
        raise SystemExit(f"FAIL: timing window must occur exactly once: {window}")

for forbidden in [
    "送给重新出发的你", "这一程或许不轻松",
    "愿你所盼有期", "长风破浪会有时",
    "assets/", ".png", ".jpg", "v03", "v04",
    "视觉指纹", "高潮动作家族", "验收标准",
    "yiwu-yiyuan-qiancheng-01-restart-15s",
]:
    if forbidden in body:
        raise SystemExit(f"FAIL: forbidden production text leaked into prompt: {forbidden}")

with history_path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    rows = list(reader)
    if len(reader.fieldnames or []) != 25:
        raise SystemExit("FAIL: dance history schema must remain 25 columns")

matches = [
    row for row in rows
    if row["episode"] == "yiwu-yiyuan-qiancheng-01-restart-15s"
]
if len(matches) != 1:
    raise SystemExit(f"FAIL: expected exactly one history row, found {len(matches)}")

expected_fields = {
    "poem": "李白《行路难·其一》",
    "climax_family": "三高潮潮雾开路序列",
    "peak_sequence": "横向低位开潮；斜向探海拉开纵深；纵向提跃开云",
    "peak_directions": "横向；斜向纵深；纵向",
    "peak_windows": "0.000—1.800秒；4.800—7.200秒；10.000—13.430秒",
    "status": "designed",
}
for field, expected in expected_fields.items():
    if matches[0][field] != expected:
        raise SystemExit(f"FAIL: unexpected history {field}: {matches[0][field]!r}")

print("PASS: 《重新出发》曜金潮汐圣殿提示词与台账契约完整")
PY
