#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source_video="$project_dir/exports/huanghe-voiced-v01.mp4"
manifest="$project_dir/episodes/huanghe/subtitle-plan.json"
renderer="$project_dir/scripts/render_story_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/huanghe"
output="$project_dir/exports/huanghe-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-huanghe-subtitled.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$source_video" "$manifest" "$renderer"; do
  if [[ ! -s "$required" ]]; then
    print -u2 "missing required input: $required"
    exit 1
  fi
done

mkdir -p "$cards_dir" "$(dirname "$output")"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -loop 1 -framerate 24 -i "$cards_dir/01-ayan-dialogue.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-poem-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem-two.png" \
  -filter_complex "\
    [0:v]scale=1080:1920:flags=lanczos,fps=24,format=yuv420p[base];\
    [1:v]scale=1080:1920:flags=lanczos[card1];\
    [2:v]scale=1080:1920:flags=lanczos[card2];\
    [3:v]scale=1080:1920:flags=lanczos[card3];\
    [base][card1]overlay=x=0:y=120:eof_action=pass:enable='between(t,0.000,3.456)'[v1];\
    [v1][card2]overlay=x=0:y=0:eof_action=pass:enable='between(t,4.368,6.064)'[v2];\
    [v2][card3]overlay=x=0:y=0:eof_action=pass:enable='between(t,6.447,8.152)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -t 10.054 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
