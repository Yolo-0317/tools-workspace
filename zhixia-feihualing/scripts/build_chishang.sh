#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/episodes/chishang/assets/video/content-raw-v01.mp4"
audio_dir="$project_dir/assets/audio/chishang"
cards_dir="$project_dir/assets/subtitles/chishang"
manifest="$project_dir/episodes/chishang/subtitle-plan.json"
output="$project_dir/exports/chishang-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-chishang.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

dialogue_01="$audio_dir/01-ayan-ayan-dialogue.mp3"
dialogue_02="$audio_dir/02-zhixia-zhixia-dialogue.mp3"
dialogue_03="$audio_dir/03-ayan-ayan-dialogue.mp3"
poem="$audio_dir/04-ayan-ayan-poem-voiceover.mp3"

for required in "$content" "$manifest" "$dialogue_01" "$dialogue_02" "$dialogue_03" "$poem"; do
  test -s "$required"
done

mkdir -p "$cards_dir" "$(dirname "$output")"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_story_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$content" -i "$dialogue_01" -i "$dialogue_02" -i "$dialogue_03" -i "$poem" \
  -filter_complex "\
    [0:v]trim=start=0:end=15.104,setpts=PTS-STARTPTS,fps=24,format=yuv420p[picture];\
    [0:a]aresample=48000,volume='if(between(t,0,2.4)+between(t,2.5,4.1)+between(t,4.3,6.34)+between(t,9.5,14.755),0.56,1)':eval=frame[bed];\
    [1:a]aresample=48000,atempo=1.11,loudnorm=I=-18:TP=-2:LRA=7[dialogue1];\
    [2:a]aresample=48000,atempo=1.17,loudnorm=I=-18:TP=-2:LRA=7,adelay=2500:all=1[dialogue2];\
    [3:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=4300:all=1[dialogue3];\
    [4:a]aresample=48000,atempo=0.58,loudnorm=I=-18:TP=-2:LRA=7,adelay=9500:all=1[poem];\
    [bed][dialogue1][dialogue2][dialogue3][poem]amix=inputs=5:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map "[picture]" -map "[aout]" -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -ac 2 -movflags +faststart "$build_dir/voiced.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/voiced.mp4" \
  -loop 1 -t 2.4 -i "$cards_dir/01-ayan-dialogue.png" \
  -loop 1 -t 1.6 -i "$cards_dir/02-zhixia-dialogue.png" \
  -loop 1 -t 2.04 -i "$cards_dir/03-ayan-dialogue.png" \
  -loop 1 -t 5.255 -i "$cards_dir/04-ayan-poem-voiceover.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=2.32:d=0.08:alpha=1[s0];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=1.52:d=0.08:alpha=1,setpts=PTS+2.5/TB[s1];\
    [3:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=1.96:d=0.08:alpha=1,setpts=PTS+4.3/TB[s2];\
    [4:v]format=rgba,fade=t=in:st=0:d=0.08:alpha=1,fade=t=out:st=5.175:d=0.08:alpha=1,setpts=PTS+9.5/TB[s3];\
    [0:v][s0]overlay=eof_action=pass[v1];\
    [v1][s1]overlay=eof_action=pass[v2];\
    [v2][s2]overlay=eof_action=pass[v3];\
    [v3][s3]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.104 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
