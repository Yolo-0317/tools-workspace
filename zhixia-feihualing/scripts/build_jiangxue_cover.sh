#!/bin/zsh
set -euo pipefail

root="${0:A:h:h}"
source="$root/episodes/jiangxue/work/frame-0.5.png"
base="$root/episodes/jiangxue/assets/images/cover-base-v01.png"
final="$root/episodes/jiangxue/assets/images/cover-final-v01.png"
exported="$root/exports/jiangxue-cover.png"

mkdir -p "${base:h}" "${exported:h}"
ditto "$source" "$base"
swift "$root/scripts/render_jiangxue_cover.swift" "$base" "$final"
ditto "$final" "$exported"
