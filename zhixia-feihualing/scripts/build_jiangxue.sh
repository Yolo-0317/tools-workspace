#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/episodes/jiangxue/assets/video/content-raw-v01.mp4"
audio_dir="$project_dir/assets/audio/jiangxue"
cards_dir="$project_dir/assets/subtitles/jiangxue"
manifest="$project_dir/episodes/jiangxue/subtitle-plan.json"
output="$project_dir/exports/jiangxue-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-jiangxue.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

dialogue="$audio_dir/01-ayan-ayan-dialogue.mp3"
poem="$audio_dir/02-ayan-ayan-poem-voiceover.mp3"

for required in "$content" "$manifest" "$dialogue" "$poem"; do
  test -s "$required"
done

mkdir -p "$cards_dir" "$(dirname "$output")"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_story_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$content" -i "$dialogue" -i "$poem" \
  -filter_complex "\
    [0:v]trim=start=0:end=15.104,setpts=PTS-STARTPTS,fps=24,format=yuv420p[picture];\
    [0:a]aresample=48000,volume='if(between(t,9.224,10.856)+between(t,11.556,14.604),0.55,1)':eval=frame[bed];\
    [1:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=9224:all=1[dialogue];\
    [2:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=11556:all=1[poem];\
    [bed][dialogue][poem]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map "[picture]" -map "[aout]" -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -ac 2 -movflags +faststart "$build_dir/voiced.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/voiced.mp4" \
  -loop 1 -t 1.632 -i "$cards_dir/01-ayan-dialogue.png" \
  -loop 1 -t 3.048 -i "$cards_dir/02-ayan-poem-voiceover.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=1.552:d=0.08:alpha=1,setpts=PTS+9.224/TB[s0];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=2.968:d=0.08:alpha=1,setpts=PTS+11.556/TB[s1];\
    [0:v][s0]overlay=eof_action=pass[v1];\
    [v1][s1]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
