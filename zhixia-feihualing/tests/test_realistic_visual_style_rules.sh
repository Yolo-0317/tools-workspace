#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
rules="$project_dir/docs/realistic-visual-style.md"
camera_library="$project_dir/docs/cinematic-15s-oner-camera-library.md"
workflow="$project_dir/docs/production-workflow.md"

test -s "$rules"
test -s "$camera_library"
test -s "$workflow"

for phrase in \
  "角色卡只锁定身份设计" \
  "电影级全写实" \
  "运动可以不遵循现实物理" \
  "超现实镜头舞蹈" \
  "角色持续清楚可辨" \
  "第一秒视觉钩子" \
  "持续运动" \
  "方向变化" \
  "景别变化" \
  "不得以动漫化换取动感" \
  "付费生成前门禁"; do
  rg -qF "$phrase" "$rules"
done

for phrase in \
  "15秒梦境长镜头" \
  "镜头牵引" \
  "视觉连续性" \
  "电影级全写实外观"; do
  rg -qF "$phrase" "$camera_library"
done

rg -qF "电影级全写实东方幻想角色" "$workflow"

echo "PASS: cinematic style and hook camera rules are enforced"
