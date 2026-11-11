#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
output="$project_dir/exports/baidi-subtitled-v03-gibbon-louder.mp4"

test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
ffmpeg -v error -i "$output" -f null -
echo "baidi louder gibbon video: PASS (${duration}s)"
