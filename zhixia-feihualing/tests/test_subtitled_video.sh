#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
video="${1:-$project_dir/exports/ep01-flower-subtitled-v01.mp4}"

test -f "$video"
width="$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$video")"
height="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$video")"
audio_codec="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$video")"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")"

test "$width" = "720"
test "$height" = "1280"
test "$audio_codec" = "aac"
awk -v value="$duration" 'BEGIN { exit !(value >= 20.1 && value <= 20.3) }'
ffmpeg -v error -i "$video" -f null -

echo "PASS: subtitled video is decodable, 720x1280, AAC, and approximately 20.2 seconds"
