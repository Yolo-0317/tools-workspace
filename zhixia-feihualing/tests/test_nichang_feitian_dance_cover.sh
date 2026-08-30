#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_nichang_feitian_dance_cover.sh"
renderer="$project_dir/scripts/render_nichang_feitian_dance_cover.swift"
source_video="$project_dir/exports/nichang-feitian-15s-voiced-v01.mp4"
output="$project_dir/exports/nichang-feitian-dance-cover-v01.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing Nichang Feitian voiced source"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Nichang Feitian cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Nichang Feitian cover renderer"; exit 1; }

rg -q -- '-ss 1.450' "$build_script" || { print -u2 "FAIL: Nichang Feitian cover must use frame 1.450"; exit 1; }
rg -q 'drawVertical\("栀夏"' "$renderer" || { print -u2 "FAIL: missing Zhixia cover label"; exit 1; }
rg -q 'drawVertical\("霓裳飞天"' "$renderer" || { print -u2 "FAIL: missing Nichang Feitian cover title"; exit 1; }
rg -q 'drawVertical\("唐·李白《古风·其十九》"' "$renderer" || { print -u2 "FAIL: missing Nichang Feitian attribution"; exit 1; }

"$build_script" >/dev/null

[[ -s "$output" ]] || { print -u2 "FAIL: Nichang Feitian cover was not created"; exit 1; }
properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'

ffmpeg -v error -i "$output" -f null -
print "PASS: Nichang Feitian dance cover is ready"
