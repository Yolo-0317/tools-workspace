#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
renderer="$project_dir/scripts/render_jiuge_vertical_subtitle_cards.swift"
manifest="$project_dir/episodes/jiuge-donghuang-taiyi-15s/subtitle-plan.json"
output_dir=$(mktemp -d /tmp/zhixia-jiuge-cards.XXXXXX)
trap 'rm -rf "$output_dir"' EXIT

[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Jiuge subtitle renderer"; exit 1; }
export CLANG_MODULE_CACHE_PATH="$output_dir/clang-cache"
export SWIFT_MODULECACHE_PATH="$output_dir/swift-cache"
swift "$renderer" "$manifest" "$output_dir"
[[ "$(find "$output_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]]
for card in "$output_dir"/*.png; do
  properties=$(sips -g pixelWidth -g pixelHeight -g format "$card")
  print -r -- "$properties" | rg -q 'pixelWidth: 1080'
  print -r -- "$properties" | rg -q 'pixelHeight: 1920'
  print -r -- "$properties" | rg -q 'format: png'
  ffmpeg -v error -i "$card" -f null -
done
print "PASS: Donghuang Taiyi subtitle cards are ready"
