#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/exports/cyber-divination-ep01-voiced-v03.mp4"
manifest="$project_dir/episodes/cyber-divination-ep01/subtitle-plan.json"
output="$project_dir/exports/cyber-divination-ep01-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-cyber-subtitles.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$content" "$manifest"; do
  test -s "$required"
done

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_story_subtitle_cards.swift" \
  "$manifest" "$build_dir/cards"

ffmpeg -hide_banner -loglevel error -y \
  -i "$content" \
  -loop 1 -t 1.248 -i "$build_dir/cards/01-ayan-question.png" \
  -loop 1 -t 1.190 -i "$build_dir/cards/03-zhixia-hexagram.png" \
  -loop 1 -t 3.568 -i "$build_dir/cards/04-zhixia-reading.png" \
  -loop 1 -t 1.592 -i "$build_dir/cards/05-ayan-hope.png" \
  -loop 1 -t 1.848 -i "$build_dir/cards/06-zhixia-reveal.png" \
  -loop 1 -t 2.040 -i "$build_dir/cards/07-ayan-excuse.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=1.168:d=0.08:alpha=1[s1];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=1.110:d=0.08:alpha=1,setpts=PTS+3.7/TB[s2];\
    [3:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=3.488:d=0.08:alpha=1,setpts=PTS+4.9/TB[s3];\
    [4:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=1.512:d=0.08:alpha=1,setpts=PTS+8.5/TB[s4];\
    [5:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=1.768:d=0.08:alpha=1,setpts=PTS+10.1/TB[s5];\
    [6:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=1.960:d=0.08:alpha=1,setpts=PTS+12.1/TB[s6];\
    [0:v][s1]overlay=eof_action=pass[v1];\
    [v1][s2]overlay=eof_action=pass[v2];\
    [v2][s3]overlay=eof_action=pass[v3];\
    [v3][s4]overlay=eof_action=pass[v4];\
    [v4][s5]overlay=eof_action=pass[v5];\
    [v5][s6]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
