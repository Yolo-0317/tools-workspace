#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_huxuan_dance_cover.sh"
renderer="$project_dir/scripts/render_huxuan_dance_cover.swift"
source_video="$project_dir/exports/huxuan-15s-voiced-v01.mp4"
output="$project_dir/exports/huxuan-dance-cover-v01.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing Huxuan voiced source"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Huxuan cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Huxuan cover renderer"; exit 1; }

rg -q -- '-ss 1.250' "$build_script" || { print -u2 "FAIL: Huxuan cover must use frame 1.250"; exit 1; }
rg -q 'drawVertical\("栀夏"' "$renderer" || { print -u2 "FAIL: missing Zhixia cover label"; exit 1; }
rg -q 'drawVertical\("回雪胡旋"' "$renderer" || { print -u2 "FAIL: missing Huxuan cover title"; exit 1; }
rg -q 'drawVertical\("唐·白居易《胡旋女》"' "$renderer" || { print -u2 "FAIL: missing Huxuan attribution"; exit 1; }

"$build_script" >/dev/null

[[ -s "$output" ]] || { print -u2 "FAIL: Huxuan cover was not created"; exit 1; }
properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'

ffmpeg -v error -i "$output" -f null -
print "PASS: Huxuan dance cover is ready"
