#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
builder="$project_dir/scripts/build_huanghe_dance_cover.sh"
renderer="$project_dir/scripts/render_huanghe_dance_cover.swift"
output="$project_dir/exports/huanghe-dance-cover-v01.png"

[[ -x "$builder" ]] || { print -u2 "FAIL: missing executable builder: $builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing renderer: $renderer"; exit 1; }

"$builder"

[[ -s "$output" ]] || { print -u2 "FAIL: missing output cover: $output"; exit 1; }

spec="$(ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,pix_fmt \
  -of default=noprint_wrappers=1 "$output")"

[[ "$spec" == *"codec_name=png"* ]] || { print -u2 "FAIL: output is not PNG"; exit 1; }
[[ "$spec" == *"width=1080"* ]] || { print -u2 "FAIL: output width is not 1080"; exit 1; }
[[ "$spec" == *"height=1920"* ]] || { print -u2 "FAIL: output height is not 1920"; exit 1; }

ffmpeg -v error -i "$output" -f null -

rg -qF "huanghe-dance-cover-v01" "$project_dir/assets/inventory.csv" || {
  print -u2 "FAIL: cover is not inventoried"
  exit 1
}

print "PASS: Huanghe dance cover is valid, 1080x1920, and inventoried"
