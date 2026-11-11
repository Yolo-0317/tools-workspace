#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
manifest="$project_dir/episodes/ep01/subtitles-flower.json"
cards_dir="$project_dir/assets/subtitles/ep01-flower"
input_video="${INPUT_VIDEO:-$project_dir/exports/ep01-flower-voiced-v01.mp4}"
output_video="${OUTPUT_VIDEO:-$project_dir/exports/ep01-flower-subtitled-v01.mp4}"
cache_root="$(mktemp -d /tmp/zhixia-subtitle-build.XXXXXX)"
trap 'rm -rf "$cache_root"' EXIT

export CLANG_MODULE_CACHE_PATH="$cache_root/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$cache_root/swift-module-cache"
swift "$project_dir/scripts/render_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$input_video" \
  -loop 1 -t 2.69 -i "$cards_dir/01-opening.png" \
  -loop 1 -t 3.07 -i "$cards_dir/02-poem-01.png" \
  -loop 1 -t 3.86 -i "$cards_dir/03-poem-02.png" \
  -loop 1 -t 5.23 -i "$cards_dir/04-poem-03.png" \
  -loop 1 -t 2.26 -i "$cards_dir/05-outro.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=2.57:d=0.12:alpha=1,setpts=PTS+0.00/TB[s0];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=2.95:d=0.12:alpha=1,setpts=PTS+2.90/TB[s1];\
    [3:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=3.74:d=0.12:alpha=1,setpts=PTS+6.00/TB[s2];\
    [4:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=5.11:d=0.12:alpha=1,setpts=PTS+10.00/TB[s3];\
    [5:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=2.14:d=0.12:alpha=1,setpts=PTS+17.75/TB[s4];\
    [0:v][s0]overlay=eof_action=pass[v1];\
    [v1][s1]overlay=eof_action=pass[v2];\
    [v2][s2]overlay=eof_action=pass[v3];\
    [v3][s3]overlay=eof_action=pass[v4];\
    [v4][s4]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart -shortest "$output_video"

echo "$output_video"
