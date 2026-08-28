#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source_video="$project_dir/episodes/yesu-shansi/assets/video/content-seedance-v03.mp4"
audio_dir="$project_dir/assets/audio/yesu-shansi-oner-lingling-full"
manifest="$project_dir/episodes/yesu-shansi/subtitle-plan-oner-lingling-full.json"
cards_dir="$project_dir/assets/subtitles/yesu-shansi-oner-lingling-full"
output="$project_dir/exports/yesu-shansi-oner-lingling-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-yesu-shansi-final.XXXXXX)"
voiced_video="$build_dir/voiced.mp4"
trap 'rm -rf "$build_dir"' EXIT

voice_files=(
  "$audio_dir/01-ayan-ayan-lead.mp3"
  "$audio_dir/02-zhixia-lingling-test-zhixia-reply.mp3"
  "$audio_dir/03-zhixia-lingling-test-zhixia-stars.mp3"
  "$audio_dir/04-ayan-ayan-reach.mp3"
  "$audio_dir/05-zhixia-lingling-test-zhixia-poem-one.mp3"
  "$audio_dir/06-zhixia-lingling-test-zhixia-poem-two.mp3"
)

for required in "$source_video" "$manifest" "${voice_files[@]}"; do
  test -s "$required"
done

mkdir -p "$cards_dir" "$(dirname "$output")"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_story_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "${voice_files[1]}" \
  -i "${voice_files[2]}" \
  -i "${voice_files[3]}" \
  -i "${voice_files[4]}" \
  -i "${voice_files[5]}" \
  -i "${voice_files[6]}" \
  -filter_complex "\
    [0:v]scale=720:1280:flags=lanczos,fps=24,format=yuv420p[vout];\
    [0:a]aresample=48000,volume='if(between(t,0,2.04)+between(t,2.10,4.764)+between(t,5.70,8.364)+between(t,8.40,10.032)+between(t,10.05,12.474)+between(t,12.50,14.780),0.562341,1)'[bg];\
    [1:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=0|0[v1];\
    [2:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=2100|2100[v2];\
    [3:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=5700|5700[v3];\
    [4:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=8400|8400[v4];\
    [5:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=10050|10050[v5];\
    [6:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=12500|12500[v6];\
    [bg][v1][v2][v3][v4][v5][v6]amix=inputs=7:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map "[vout]" -map "[aout]" -t 15.093 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart "$voiced_video"

ffmpeg -hide_banner -loglevel error -y \
  -i "$voiced_video" \
  -loop 1 -framerate 24 -i "$cards_dir/01-ayan-lead.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-zhixia-reply.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-zhixia-stars.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-ayan-reach.png" \
  -loop 1 -framerate 24 -i "$cards_dir/05-zhixia-poem-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/06-zhixia-poem-two.png" \
  -filter_complex "\
    [0:v][1:v]overlay=eof_action=pass:enable='between(t,0,2.04)'[v1];\
    [v1][2:v]overlay=eof_action=pass:enable='between(t,2.10,4.764)'[v2];\
    [v2][3:v]overlay=eof_action=pass:enable='between(t,5.70,8.364)'[v3];\
    [v3][4:v]overlay=eof_action=pass:enable='between(t,8.40,10.032)'[v4];\
    [v4][5:v]overlay=eof_action=pass:enable='between(t,10.05,12.474)'[v5];\
    [v5][6:v]overlay=eof_action=pass:enable='between(t,12.50,14.780)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.093 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
