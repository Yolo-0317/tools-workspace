#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
base="$project_dir/episodes/ep06/assets/images/cover-base-v01.png"
final="$project_dir/episodes/ep06/assets/images/cover-final-v01.png"
exported="$project_dir/exports/ep06-autumn-cover.png"

for file in "$base" "$final" "$exported"; do
  [[ -f "$file" ]] || { echo "缺少文件：$file"; exit 1; }
done

for file in "$final" "$exported"; do
  width="$(sips -g pixelWidth "$file" | awk '/pixelWidth/ {print $2}')"
  height="$(sips -g pixelHeight "$file" | awk '/pixelHeight/ {print $2}')"
  [[ "$width" == "941" ]]
  [[ "$height" == "1672" ]]
done

cmp -s "$final" "$exported"
echo "EP06秋字封面验证通过"
