#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
builder="$project_dir/scripts/build_donghuang_taiyi_cover.sh"
renderer="$project_dir/scripts/render_donghuang_taiyi_cover.swift"
base="$project_dir/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-base-v01.png"
episode_output="$project_dir/episodes/jiuge-donghuang-taiyi-15s/assets/cover/donghuang-taiyi-cover-v01.png"
export_output="$project_dir/exports/donghuang-taiyi-cover-v01.png"

[[ -s "$base" ]] || { print -u2 "FAIL: missing Donghuang Taiyi cover base"; exit 1; }
[[ -x "$builder" ]] || { print -u2 "FAIL: missing executable cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing cover renderer"; exit 1; }

"$builder" >/dev/null
for output in "$episode_output" "$export_output"; do
  [[ -s "$output" ]] || { print -u2 "FAIL: missing output $output"; exit 1; }
  properties=$(sips -g pixelWidth -g pixelHeight -g format "$output")
  print -r -- "$properties" | rg -q 'pixelWidth: 1080'
  print -r -- "$properties" | rg -q 'pixelHeight: 1920'
  print -r -- "$properties" | rg -q 'format: png'
  ffmpeg -v error -i "$output" -f null -
done
print "PASS: Donghuang Taiyi cover outputs are ready"
