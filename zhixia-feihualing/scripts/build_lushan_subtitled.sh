#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
mix="$project_dir/exports/lushan-waterfall-mix-preview-v01.mp4"
manifest="$project_dir/episodes/lushan/subtitle-plan.json"
cards_dir="$project_dir/assets/subtitles/lushan"
output="$project_dir/exports/lushan-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-lushan-subtitles.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$mix" "$manifest"; do
  test -s "$required"
done

mkdir -p "$cards_dir" "$(dirname "$output")"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_story_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$mix" \
  -loop 1 -framerate 24 -i "$cards_dir/01-ayan-dialogue.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-zhixia-dialogue.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-ayan-dialogue.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-zhixia-dialogue.png" \
  -loop 1 -framerate 24 -i "$cards_dir/05-ayan-poem.png" \
  -filter_complex "\
    [0:v][1:v]overlay=eof_action=pass:enable='between(t,0,2.2)'[v1];\
    [v1][2:v]overlay=eof_action=pass:enable='between(t,2.2,4.0)'[v2];\
    [v2][3:v]overlay=eof_action=pass:enable='between(t,4.0,7.1)'[v3];\
    [v3][4:v]overlay=eof_action=pass:enable='between(t,7.1,9.7)'[v4];\
    [v4][5:v]overlay=eof_action=pass:enable='between(t,9.7,14.8)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
