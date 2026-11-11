#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
video="${1:-$project_dir/exports/ep03-moon-subtitled-v01.mp4}"

test -f "$video"
width="$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$video")"
height="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$video")"
video_codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$video")"
audio_codec="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$video")"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")"

test "$width" = "720"
test "$height" = "1280"
test "$video_codec" = "h264"
test "$audio_codec" = "aac"
awk -v value="$duration" 'BEGIN { exit !(value >= 21.7 && value <= 21.9) }'
ffmpeg -v error -i "$video" -f null -

echo "PASS: EP03 moon video is decodable, 720x1280, H.264/AAC, and approximately 21.8 seconds"
