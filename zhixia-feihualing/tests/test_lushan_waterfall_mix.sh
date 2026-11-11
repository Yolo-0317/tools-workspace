#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
raw="$project_dir/episodes/lushan/assets/video/content-raw-v01.mp4"
output="$project_dir/exports/lushan-waterfall-mix-preview-v01.mp4"

test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate,channels -of csv=s=x:p=0 "$output")" = "48000x2"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'

raw_video_md5="$(ffmpeg -v error -i "$raw" -map 0:v:0 -c copy -f md5 - | sed 's/^MD5=//')"
output_video_md5="$(ffmpeg -v error -i "$output" -map 0:v:0 -c copy -f md5 - | sed 's/^MD5=//')"
test "$raw_video_md5" = "$output_video_md5"

raw_audio_md5="$(ffmpeg -v error -i "$raw" -map 0:a:0 -f md5 - | sed 's/^MD5=//')"
output_audio_md5="$(ffmpeg -v error -i "$output" -map 0:a:0 -f md5 - | sed 's/^MD5=//')"
test "$raw_audio_md5" != "$output_audio_md5"

max_volume="$(ffmpeg -hide_banner -i "$output" -af volumedetect -f null - 2>&1 | awk '/max_volume:/ {print $(NF-1)}' | tail -1)"
awk -v v="$max_volume" 'BEGIN { exit !(v <= -0.3) }'
ffmpeg -v error -i "$output" -f null -
echo "lushan waterfall mix: PASS (${duration}s, max ${max_volume} dB)"
