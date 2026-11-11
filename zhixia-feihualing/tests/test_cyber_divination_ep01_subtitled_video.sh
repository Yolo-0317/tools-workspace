#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
base="$project_dir/exports/cyber-divination-ep01-voiced-v03.mp4"
output="$project_dir/exports/cyber-divination-ep01-subtitled-v01.mp4"

test -s "$base"
test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
ffmpeg -v error -i "$output" -f null -
echo "cyber divination ep01 subtitled video: PASS (${duration}s)"
