#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
builder="$project_dir/scripts/build_yunzhongjun_cover.sh"
renderer="$project_dir/scripts/render_yunzhongjun_cover.swift"
base="$project_dir/episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-base-v01.png"
episode_output="$project_dir/episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-v01.png"
export_output="$project_dir/exports/yunzhongjun-cover-v01.png"

[[ -s "$base" ]] || { print -u2 "FAIL: missing Yunzhongjun cover base"; exit 1; }
[[ -x "$builder" ]] || { print -u2 "FAIL: missing executable Yunzhongjun cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Yunzhongjun cover renderer"; exit 1; }

"$builder" >/dev/null
for output in "$episode_output" "$export_output"; do
  [[ -s "$output" ]] || { print -u2 "FAIL: missing output $output"; exit 1; }
  properties=$(sips -g pixelWidth -g pixelHeight -g format "$output")
  print -r -- "$properties" | rg -q 'pixelWidth: 1080'
  print -r -- "$properties" | rg -q 'pixelHeight: 1920'
  print -r -- "$properties" | rg -q 'format: png'
  ffmpeg -v error -i "$output" -f null -
done
cmp -s "$episode_output" "$export_output"
print "PASS: Yunzhongjun cover outputs are ready"
