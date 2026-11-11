#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
prompt="$project_dir/episodes/yesu-shansi/prompts/seedance-v02-live-action-oner.md"

if [[ ! -s "$prompt" ]]; then
  echo "FAIL: missing Seedance v02 prompt: $prompt" >&2
  exit 1
fi

python3 - "$prompt" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
start_marker = "<!-- SEEDANCE_PROMPT_START -->"
end_marker = "<!-- SEEDANCE_PROMPT_END -->"

assert text.count(start_marker) == 1, "Seedance prompt must have one start marker"
assert text.count(end_marker) == 1, "Seedance prompt must have one end marker"
start = text.index(start_marker) + len(start_marker)
end = text.index(end_marker)
assert start < end, "Seedance prompt markers are out of order"
seedance = text[start:end]

required = [
    "栀夏角色卡",
    "阿砚角色卡",
    "只锁定身份与造型",
    "真人电影化半写实",
    "真实皮肤微纹理",
    "真实眼球湿润反光",
    "独立发丝",
    "真实丝织衣料",
    "真实幻想生物毛发",
    "前方倒退领飞",
    "停止坠落并反向上升",
    "一镜到底",
    "不生成可辨识人声",
    "不生成字幕、诗句、标题、Logo或水印",
]
for phrase in required:
    assert phrase in seedance, f"missing required Seedance rule: {phrase}"

for time_range in ["0.0—3.0秒", "3.0—9.5秒", "9.5—12.0秒", "12.0—15.0秒"]:
    assert seedance.count(time_range) == 1, f"timeline range must appear once: {time_range}"

for forbidden in [
    "栀夏，跟紧我",
    "明明是你跟紧我",
    "阿砚，那是星星吗",
    "伸手就知道了",
    "危楼高百尺",
    "手可摘星辰",
]:
    assert forbidden not in seedance, f"post-production line leaked into Seedance prompt: {forbidden}"

print("PASS: Seedance v02 prompt keeps identity, live-action texture, oner and voice isolation")
PY
