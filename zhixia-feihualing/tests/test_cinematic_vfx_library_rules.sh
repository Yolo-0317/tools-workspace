#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
library="$project_dir/docs/cinematic-vfx-library.md"
style_rules="$project_dir/docs/realistic-visual-style.md"
camera_library="$project_dir/docs/cinematic-15s-oner-camera-library.md"
workflow="$project_dir/docs/production-workflow.md"

test -s "$library"

test "$(rg -c '^### H[0-9]{2} ' "$library")" = "8"
test "$(rg -c '^### S[0-9]{2} ' "$library")" = "7"
test "$(rg -c '^### P[0-9]{2} ' "$library")" = "6"

for phrase in \
  "一个生成期主特效＋最多一个生成期辅助特效＋少量后期增强" \
  "generation-hero" \
  "generation-support" \
  "post-enhancement" \
  "不超过0.5秒" \
  "三张状态卡" \
  "4至5秒低成本测试" \
  "角色共舞方式" \
  "视觉承接物" \
  "身份漂移风险" \
  "全写实提示词" \
  "禁用效果" \
  "动漫速度线" \
  "RGB故障" \
  "特效选型卡"; do
  rg -qF "$phrase" "$library"
done

for entry in "$style_rules" "$camera_library" "$workflow"; do
  rg -qF "cinematic-vfx-library.md" "$entry"
done

if rg -n "😀|🎬|✨" "$library"; then
  exit 1
fi

echo "PASS: cinematic VFX library rules are enforced"
