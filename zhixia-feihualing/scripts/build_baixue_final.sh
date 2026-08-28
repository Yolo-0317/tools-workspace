#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source_video="$project_dir/episodes/baixue/assets/video/content-seedance-v01.mp4"
audio_dir="$project_dir/assets/audio/baixue"
manifest="$project_dir/episodes/baixue/subtitle-plan.json"
cards_dir="$project_dir/assets/subtitles/baixue"
output="$project_dir/exports/baixue-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-baixue-final.XXXXXX)"
mixed_audio="$build_dir/mixed-audio.m4a"
trap 'rm -rf "$build_dir"' EXIT

voice_files=(
  "$audio_dir/01-ayan-ayan-dialogue.mp3"
  "$audio_dir/02-zhixia-zhixia-dialogue.mp3"
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
    [0:a]aresample=48000,volume='if(between(t,0.500,1.724)+between(t,1.850,3.482)+between(t,3.600,6.048)+between(t,6.200,9.032),0.562341,1)'[bed];\
    [1:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=500:all=1[v1];\
    [2:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=1850:all=1[v2];\
    [3:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=3600:all=1[v3];\
    [4:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=6200:all=1[v4];\
    [bed][v1][v2][v3][v4]amix=inputs=5:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.891251:level=false[aout]" \
  -map "[aout]" -t 10.100 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 "$mixed_audio"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$mixed_audio" \
  -loop 1 -framerate 24 -i "$cards_dir/01-ayan-dialogue.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-zhixia-dialogue.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-zhixia-poem-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-zhixia-poem-two.png" \
  -filter_complex "\
    [0:v]scale=1080:1920:flags=lanczos,fps=24,format=yuv420p[base];\
    [2:v]scale=1080:1920:flags=lanczos[card1];\
    [3:v]scale=1080:1920:flags=lanczos[card2];\
    [4:v]scale=1080:1920:flags=lanczos[card3];\
    [5:v]scale=1080:1920:flags=lanczos[card4];\
    [base][card1]overlay=eof_action=pass:enable='between(t,0.500,1.724)'[v1];\
    [v1][card2]overlay=eof_action=pass:enable='between(t,1.850,3.482)'[v2];\
    [v2][card3]overlay=eof_action=pass:enable='between(t,3.600,6.048)'[v3];\
    [v3][card4]overlay=eof_action=pass:enable='between(t,6.200,9.032)',format=yuv420p[vout]" \
  -map "[vout]" -map 1:a:0 -t 10.100 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
