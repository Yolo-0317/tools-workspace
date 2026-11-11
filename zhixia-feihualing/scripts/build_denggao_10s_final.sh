#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source_video="$project_dir/episodes/denggao-10s/assets/video/content-seedance-v01.mp4"
audio_dir="$project_dir/assets/audio/denggao-10s"
manifest="$project_dir/episodes/denggao-10s/subtitle-plan.json"
cards_dir="$project_dir/assets/subtitles/denggao-10s"
output="$project_dir/exports/denggao-10s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-denggao-final.XXXXXX)"
mixed_audio="$build_dir/mixed-audio.m4a"
trap 'rm -rf "$build_dir"' EXIT

voice_files=(
  "$audio_dir/01-ayan-ayan-hook.mp3"
  "$audio_dir/02-zhixia-zhixia-hook.mp3"
  "$audio_dir/03-zhixia-zhixia-poem-one.mp3"
  "$audio_dir/04-zhixia-zhixia-poem-two.mp3"
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
  -filter_complex "\
    [0:a]aresample=48000,volume='if(between(t,0.600,2.064)+between(t,2.160,3.624)+between(t,3.740,6.572)+between(t,6.690,8.946),0.562341,1)'[bg];\
    [1:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=600|600[v1];\
    [2:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=2160|2160[v2];\
    [3:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=3740|3740[v3];\
    [4:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=6690|6690[v4];\
    [bg][v1][v2][v3][v4]amix=inputs=5:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.891251:level=false[aout]" \
  -map "[aout]" -t 10.100 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 "$mixed_audio"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$mixed_audio" \
  -loop 1 -framerate 24 -i "$cards_dir/01-ayan-hook.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-zhixia-hook.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-zhixia-poem-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-zhixia-poem-two.png" \
  -filter_complex "\
    [0:v]scale=1080:1920:flags=lanczos,fps=24,format=yuv420p[base];\
    [2:v]scale=1080:1920:flags=lanczos[card1];\
    [3:v]scale=1080:1920:flags=lanczos[card2];\
    [4:v]scale=1080:1920:flags=lanczos[card3];\
    [5:v]scale=1080:1920:flags=lanczos[card4];\
    [base][card1]overlay=eof_action=pass:enable='between(t,0.600,2.064)'[v1];\
    [v1][card2]overlay=eof_action=pass:enable='between(t,2.160,3.624)'[v2];\
    [v2][card3]overlay=eof_action=pass:enable='between(t,3.740,6.572)'[v3];\
    [v3][card4]overlay=eof_action=pass:enable='between(t,6.690,8.946)',format=yuv420p[vout]" \
  -map "[vout]" -map 1:a:0 -t 10.100 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
