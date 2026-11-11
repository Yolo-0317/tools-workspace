#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
opening="$project_dir/assets/generated-video/ep01-flower/opening-raw.mp4"
content="$project_dir/assets/generated-video/ep3-moon/ep03-内容.mp4"
outro="$project_dir/assets/generated-video/ep02-wind/新片尾 05s.mp4"
audio_dir="$project_dir/assets/audio/ep3-moon"
cards_dir="$project_dir/assets/subtitles/ep03-moon"
manifest="$project_dir/episodes/ep03/subtitles-moon.json"
output="$project_dir/exports/ep03-moon-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-ep03-moon.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_subtitle_cards.swift" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$opening" -i "$content" -i "$outro" \
  -filter_complex "\
    [0:v]trim=start=0:end=2.8,setpts=PTS-STARTPTS,fps=24,settb=AVTB,format=yuv420p[opening];\
    [1:v]trim=start=0:end=15.04,setpts=PTS-STARTPTS,fps=24,settb=AVTB,format=yuv420p[main];\
    [2:v]trim=start=0:end=4.596,setpts=PTS-STARTPTS,fps=24,settb=AVTB,format=yuv420p[outro];\
    [opening][main]xfade=transition=fade:duration=0.3:offset=2.5[x1];\
    [x1][outro]xfade=transition=fade:duration=0.3:offset=17.24[picture]" \
  -map "[picture]" -t 21.836 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -an -movflags +faststart "$build_dir/picture.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/picture.mp4" \
  -i "$audio_dir/阿砚-月-开头.mp3" \
  -i "$audio_dir/栀夏-月-1.mp3" \
  -i "$audio_dir/阿砚-月-2.mp3" \
  -i "$audio_dir/栀夏-月-3.mp3" \
  -i "$audio_dir/阿砚-月-结尾.mp3" \
  -filter_complex "\
    [1:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=0:all=1[a0];\
    [2:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=2500:all=1[a1];\
    [3:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=6604:all=1[a2];\
    [4:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=12380:all=1[a3];\
    [5:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=17540:all=1[a4];\
    [a0][a1][a2][a3][a4]amix=inputs=5:duration=longest:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" -t 21.836 \
  -c:v copy -c:a aac -b:a 160k -ar 48000 -ac 1 \
  -movflags +faststart "$build_dir/voiced.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/voiced.mp4" \
  -loop 1 -t 2.400 -i "$cards_dir/01-opening.png" \
  -loop 1 -t 4.104 -i "$cards_dir/02-poem-01.png" \
  -loop 1 -t 3.264 -i "$cards_dir/03-poem-02.png" \
  -loop 1 -t 5.160 -i "$cards_dir/04-poem-03.png" \
  -loop 1 -t 4.296 -i "$cards_dir/05-outro.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=2.28:d=0.12:alpha=1,setpts=PTS+0.000/TB[s0];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=3.984:d=0.12:alpha=1,setpts=PTS+2.500/TB[s1];\
    [3:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=3.144:d=0.12:alpha=1,setpts=PTS+6.604/TB[s2];\
    [4:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=5.040:d=0.12:alpha=1,setpts=PTS+12.380/TB[s3];\
    [5:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=4.176:d=0.12:alpha=1,setpts=PTS+17.540/TB[s4];\
    [0:v][s0]overlay=eof_action=pass[v1];\
    [v1][s1]overlay=eof_action=pass[v2];\
    [v2][s2]overlay=eof_action=pass[v3];\
    [v3][s3]overlay=eof_action=pass[v4];\
    [v4][s4]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 21.836 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
