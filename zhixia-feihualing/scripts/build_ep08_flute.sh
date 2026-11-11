#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/episodes/ep08/assets/video/content-raw-v01.mp4"
audio_dir="$project_dir/assets/audio/ep08-flute"
cards_dir="$project_dir/assets/subtitles/ep08-flute"
manifest="$project_dir/episodes/ep08/subtitles-flute.json"
output="$project_dir/exports/ep08-flute-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-ep08-flute.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$content" "$manifest" \
  "$audio_dir/01-ayan-poem-01.mp3" \
  "$audio_dir/02-zhixia-poem-02.mp3" \
  "$audio_dir/03-ayan-poem-03.mp3"; do
  test -f "$required"
done

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$content" \
  -i "$audio_dir/01-ayan-poem-01.mp3" \
  -i "$audio_dir/02-zhixia-poem-02.mp3" \
  -i "$audio_dir/03-ayan-poem-03.mp3" \
  -filter_complex "\
    [0:v]trim=start=0:end=15.041667,setpts=PTS-STARTPTS,fps=24,format=yuv420p[picture];\
    [1:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=300:all=1[a0];\
    [2:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=5100:all=1[a1];\
    [3:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=12050:all=1[a2];\
    [a0][a1][a2]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0,\
      apad=whole_dur=15.041667,alimiter=limit=0.95[aout]" \
  -map "[picture]" -map "[aout]" -t 15.041667 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -ac 1 \
  -movflags +faststart "$build_dir/voiced.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/voiced.mp4" \
  -loop 1 -t 2.664 -i "$cards_dir/01-poem-01.png" \
  -loop 1 -t 2.424 -i "$cards_dir/02-poem-02.png" \
  -loop 1 -t 2.832 -i "$cards_dir/03-poem-03.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.10:alpha=1,fade=t=out:st=2.564:d=0.10:alpha=1,setpts=PTS+0.300/TB[s0];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.10:alpha=1,fade=t=out:st=2.324:d=0.10:alpha=1,setpts=PTS+5.100/TB[s1];\
    [3:v]format=rgba,fade=t=in:st=0:d=0.10:alpha=1,fade=t=out:st=2.732:d=0.10:alpha=1,setpts=PTS+12.050/TB[s2];\
    [0:v][s0]overlay=eof_action=pass[v1];\
    [v1][s1]overlay=eof_action=pass[v2];\
    [v2][s2]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 15.041667 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
