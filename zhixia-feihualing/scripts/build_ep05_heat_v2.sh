#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/episodes/ep05/assets/video/content-raw-v01.mp4"
outro="$project_dir/assets/generated-video/ep02-wind/新片尾 05s.mp4"
audio_dir="$project_dir/assets/audio/ep05-heat-v2"
cards_dir="$project_dir/assets/subtitles/ep05-heat-v2"
manifest="$project_dir/episodes/ep05/subtitles-heat-v2.json"
output="$project_dir/exports/ep05-heat-v2-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-ep05-heat-v2.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$content" "$outro" "$manifest" \
  "$audio_dir/02-zhixia-poem-01.mp3" \
  "$audio_dir/03-ayan-poem-02.mp3" \
  "$audio_dir/04-zhixia-poem-03.mp3" \
  "$audio_dir/05-ayan-outro.mp3"; do
  test -f "$required"
done

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_subtitle_cards.swift" "$manifest" "$cards_dir"

# 完整保留现有Seedance 15.04秒主内容，不加封面、不变速。
ffmpeg -hide_banner -loglevel error -y \
  -i "$content" -i "$outro" \
  -filter_complex "\
    [0:v]trim=start=0:end=15.041667,setpts=PTS-STARTPTS,fps=24,settb=AVTB,format=yuv420p[main];\
    [1:v]trim=start=0:end=4.680,setpts=PTS-STARTPTS,fps=24,settb=AVTB,format=yuv420p[outro];\
    [main][outro]xfade=transition=fade:duration=0.300:offset=14.741667[picture]" \
  -map "[picture]" -t 19.422 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -an -movflags +faststart "$build_dir/picture.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/picture.mp4" \
  -i "$audio_dir/02-zhixia-poem-01.mp3" \
  -i "$audio_dir/03-ayan-poem-02.mp3" \
  -i "$audio_dir/04-zhixia-poem-03.mp3" \
  -i "$audio_dir/05-ayan-outro.mp3" \
  -filter_complex "\
    [1:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=0:all=1[a1];\
    [2:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=5000:all=1[a2];\
    [3:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=10000:all=1[a3];\
    [4:a]loudnorm=I=-18:TP=-2:LRA=7,adelay=15150:all=1[a4];\
    [a1][a2][a3][a4]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" -t 19.422 \
  -c:v copy -c:a aac -b:a 160k -ar 48000 -ac 1 \
  -movflags +faststart "$build_dir/voiced.mp4"

# 字幕淡入在真实起声点完成，并在各自音频结束时消失。
ffmpeg -hide_banner -loglevel error -y \
  -i "$build_dir/voiced.mp4" \
  -loop 1 -t 2.934 -i "$cards_dir/02-poem-01.png" \
  -loop 1 -t 3.240 -i "$cards_dir/03-poem-02.png" \
  -loop 1 -t 3.727 -i "$cards_dir/04-poem-03.png" \
  -loop 1 -t 4.015 -i "$cards_dir/05-outro.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=2.814:d=0.12:alpha=1,setpts=PTS+0.138/TB[s1];\
    [2:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=3.120:d=0.12:alpha=1,setpts=PTS+5.000/TB[s2];\
    [3:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=3.607:d=0.12:alpha=1,setpts=PTS+10.137/TB[s3];\
    [4:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st=3.895:d=0.12:alpha=1,setpts=PTS+15.407/TB[s4];\
    [0:v][s1]overlay=eof_action=pass[v1];\
    [v1][s2]overlay=eof_action=pass[v2];\
    [v2][s3]overlay=eof_action=pass[v3];\
    [v3][s4]overlay=eof_action=pass[vout]" \
  -map "[vout]" -map 0:a:0 -t 19.422 \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$output"

echo "$output"
