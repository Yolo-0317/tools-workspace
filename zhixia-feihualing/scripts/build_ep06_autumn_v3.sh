#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/episodes/ep06/assets/video/content-raw-v02.mp4"
audio_dir="$project_dir/assets/audio/ep06-autumn"
cards_dir="$project_dir/assets/subtitles/ep06-autumn-v3"
manifest="$project_dir/episodes/ep06/subtitles-autumn.json"
output="$project_dir/exports/ep06-autumn-subtitled-v03.mp4"
build_dir="$(mktemp -d /tmp/zhixia-ep06-autumn-v3.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$content" "$manifest" \
  "$audio_dir/01-ayan-poem-00.mp3" \
  "$audio_dir/02-zhixia-poem-01.mp3" \
  "$audio_dir/03-ayan-poem-02.mp3"; do
  test -f "$required"
done

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$content" \
  -i "$audio_dir/01-ayan-poem-00.mp3" \
  -i "$audio_dir/02-zhixia-poem-01.mp3" \
  -i "$audio_dir/03-ayan-poem-02.mp3" \
  -filter_complex "\
    [0:v]trim=start=0:end=15.041667,setpts=PTS-STARTPTS,fps=24,format=yuv420p[picture];\
    [1:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=300:all=1[a0];\
    [2:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=5000:all=1[a1];\
    [3:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=11800:all=1[a2];\
    [a0][a1][a2]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0,\
      apad=whole_dur=15.041667,alimiter=limit=0.95[aout]" \
  -map "[picture]" -map "[aout]" -t 15.041667 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -ac 1 \
  -movflags +faststart "$build_dir/voiced.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/voiced.mp4" \
  -loop 1 -t 3.072 -i "$cards_dir/01-poem-00.png" \
  -loop 1 -t 3.864 -i "$cards_dir/02-poem-01.png" \
  -loop 1 -t 3.048 -i "$cards_dir/03-poem-02.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.10:alpha=1,fade=t=out:st=2.972:d=0.10:alpha=1,setpts=PTS+0.300/TB[s0];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.10:alpha=1,fade=t=out:st=3.764:d=0.10:alpha=1,setpts=PTS+5.000/TB[s1];\
    [3:v]format=rgba,fade=t=in:st=0:d=0.10:alpha=1,fade=t=out:st=2.948:d=0.10:alpha=1,setpts=PTS+11.800/TB[s2];\
    [0:v][s0]overlay=eof_action=pass[v1];\
    [v1][s1]overlay=eof_action=pass[v2];\
    [v2][s2]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.041667 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
