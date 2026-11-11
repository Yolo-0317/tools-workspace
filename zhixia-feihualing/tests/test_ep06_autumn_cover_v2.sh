#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
base="$project_dir/episodes/ep06/assets/images/cover-base-v02.png"
final="$project_dir/episodes/ep06/assets/images/cover-final-v02.png"
exported="$project_dir/exports/ep06-autumn-cover-v02.png"
renderer="$project_dir/scripts/render_ep06_comment_cover.swift"

for file in "$base" "$final" "$exported" "$renderer"; do
  [[ -f "$file" ]] || { echo "缺少文件：$file"; exit 1; }
done

for file in "$base" "$final" "$exported"; do
  width="$(sips -g pixelWidth "$file" | awk '/pixelWidth/ {print $2}')"
  height="$(sips -g pixelHeight "$file" | awk '/pixelHeight/ {print $2}')"
  [[ "$width" == "941" ]]
  [[ "$height" == "1672" ]]
done

cmp -s "$final" "$exported"
! cmp -s "$base" "$final"

rg -q '秋字飞花令' "$renderer"
rg -q '第四句等你' "$renderer"
echo "EP06秋字评论挑战封面v2验证通过"
