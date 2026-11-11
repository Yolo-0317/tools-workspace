#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/episodes/qiusi/assets/video/content-raw-v01.mp4"
voice="$project_dir/assets/audio/qiusi/01-ayan-poem-voiceover.mp3"
manifest="$project_dir/episodes/qiusi/subtitle-plan.json"
cards_dir="$project_dir/assets/subtitles/qiusi"
output="$project_dir/exports/qiusi-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-qiusi.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$content" "$voice" "$manifest"; do
  test -s "$required"
done

mkdir -p "$cards_dir" "$(dirname "$output")"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_story_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$content" -i "$voice" \
  -filter_complex "\
    [0:v]trim=start=0:end=15.104,setpts=PTS-STARTPTS,fps=24,format=yuv420p[picture];\
    [0:a]aresample=48000,volume='if(between(t,11.2,15.064),0.55,1)':eval=frame[bed];\
    [1:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=11200:all=1[voice];\
    [bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map "[picture]" -map "[aout]" -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -ac 2 -movflags +faststart "$build_dir/voiced.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/voiced.mp4" \
  -loop 1 -t 3.864 -i "$cards_dir/01-poem-voiceover.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=3.784:d=0.08:alpha=1,setpts=PTS+11.200/TB[card];\
    [0:v][card]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
