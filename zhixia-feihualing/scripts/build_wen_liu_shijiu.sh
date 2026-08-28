#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/episodes/wen-liu-shijiu/assets/video/content-raw-v01.mp4"
audio_dir="$project_dir/assets/audio/wen-liu-shijiu"
cards_dir="$project_dir/assets/subtitles/wen-liu-shijiu"
manifest="$project_dir/episodes/wen-liu-shijiu/subtitle-plan.json"
output="$project_dir/exports/wen-liu-shijiu-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-wen-liu-shijiu.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$content" "$manifest" \
  "$audio_dir/01-ayan-opening-dialogue.mp3" \
  "$audio_dir/02-ayan-poem-voiceover.mp3"; do
  test -s "$required"
done

mkdir -p "$cards_dir" "$(dirname "$output")"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_story_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$content" \
  -i "$audio_dir/01-ayan-opening-dialogue.mp3" \
  -i "$audio_dir/02-ayan-poem-voiceover.mp3" \
  -filter_complex "\
    [0:v]trim=start=0:end=15.104,setpts=PTS-STARTPTS,fps=24,format=yuv420p[picture];\
    [0:a]aresample=48000,volume='if(between(t,0.4,3.256)+between(t,12.05,14.882),0.55,1)':eval=frame[bed];\
    [1:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=400:all=1[ayan1];\
    [2:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=12050:all=1[ayan2];\
    [bed][ayan1][ayan2]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map "[picture]" -map "[aout]" -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -ac 2 \
  -movflags +faststart "$build_dir/voiced.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/voiced.mp4" \
  -loop 1 -t 2.856 -i "$cards_dir/01-opening-dialogue.png" \
  -loop 1 -t 0.800 -i "$cards_dir/02-original-dialogue.png" \
  -loop 1 -t 2.832 -i "$cards_dir/03-poem-voiceover.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=2.776:d=0.08:alpha=1,setpts=PTS+0.400/TB[s0];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.06:alpha=1,fade=t=out:st=0.740:d=0.06:alpha=1,setpts=PTS+8.700/TB[s1];\
    [3:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=2.752:d=0.08:alpha=1,setpts=PTS+12.050/TB[s2];\
    [0:v][s0]overlay=eof_action=pass[v1];\
    [v1][s1]overlay=eof_action=pass[v2];\
    [v2][s2]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
