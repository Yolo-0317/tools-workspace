#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/gucuizhezhi-15s/prompts/seedance-v02.md"
readme="$project_dir/episodes/gucuizhezhi-15s/README.md"

for target in "$prompt" "$readme"; do
  [[ -s "$target" ]] || {
    print -u2 -r -- "FAIL: missing required v02 correction artifact $target"
    exit 1
  }
done

python3 - "$prompt" "$readme" <<'PY'
import re
import sys
from pathlib import Path

prompt_path, readme_path = map(Path, sys.argv[1:])
document = prompt_path.read_text(encoding="utf-8")
readme = readme_path.read_text(encoding="utf-8")

start_marker = "<!-- SEEDANCE_PROMPT_START -->"
end_marker = "<!-- SEEDANCE_PROMPT_END -->"
if document.count(start_marker) != 1 or document.count(end_marker) != 1:
    raise SystemExit("FAIL: v02 prompt must expose exactly one copyable block")
start = document.index(start_marker) + len(start_marker)
end = document.index(end_marker)
if start >= end:
    raise SystemExit("FAIL: v02 prompt markers are reversed or empty")
body = document[start:end].strip()

image_refs = set(re.findall(r"@图片\d+", body))
if image_refs != {"@图片1"}:
    raise SystemExit(f"FAIL: v02 prompt references unexpected uploads: {sorted(image_refs)}")

windows = [
    "0.000—1.800 秒", "1.800—4.800 秒", "4.800—7.000 秒",
    "7.000—10.000 秒", "10.000—13.000 秒", "13.000—15.000 秒",
]
for window in windows:
    if body.count(window) != 1:
        raise SystemExit(f"FAIL: v02 timing window must occur exactly once: {window}")

required = [
    "从动作中段直接截入",
    "第一可见帧",
    "髋部明显低于正常站姿",
    "0.000—0.200 秒",
    "一次且仅一次快速改面翻身",
    "7.000 秒之后零次完整旋转",
    "骨盆和胸口不得完成 180 度转向",
    "第三次强动作全程零旋转",
    "深弓步",
    "前后轴强力提展",
    "2.000 秒后不得再次出现垂直沙柱",
    "只向画面右侧扫出",
    "贴地直线薄沙带",
    "贴地纵深楔形沙痕",
    "从画面下方近景",
    "指向后侧画鼓",
    "手掌、手指与飘带之间始终保留清楚可见的空气间隙",
    "全身高度约占画面 70%",
    "全身高度不低于画面 65%",
    "全身高度不低于画面 60%",
    "全身高度始终不低于画面 55%",
    "总后撤距离减半",
    "不生成任何可辨识人声",
]
for phrase in required:
    if phrase not in body:
        raise SystemExit(f"FAIL: v02 prompt is missing corrective instruction: {phrase}")

for poem_line in [
    "平铺一合锦筵开", "连击三声画鼓催",
    "红蜡烛移桃叶起", "紫罗衫动柘枝来",
]:
    if poem_line in body:
        raise SystemExit(f"FAIL: poem line leaked into v02 generation block: {poem_line}")

for forbidden in [
    "@图片2", "不完整半转", "gucuizhezhi-15s", "assets/",
    ".jpg", ".png", "验收标准", "高潮动作家族",
]:
    if forbidden in body:
        raise SystemExit(f"FAIL: forbidden term leaked into v02 prompt: {forbidden}")

for readme_phrase in [
    "首轮成片复盘",
    "第一帧偏直立",
    "第三次高潮",
    "手抓飘带",
    "人物缩得过小",
    "prompts/seedance-v02.md",
    "v02 视频尚未生成",
]:
    if readme_phrase not in readme:
        raise SystemExit(f"FAIL: README is missing v02 correction record: {readme_phrase}")

print("PASS: 《鼓催柘枝》v02 corrects opening, peak strength, rotation, sand, ribbons, and framing")
PY
