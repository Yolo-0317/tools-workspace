#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
output="$project_dir/exports/cyber-divination-ep01-voiced-v03.mp4"

test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
ffmpeg -v error -i "$output" -f null -

# 2.2—3.5秒已删除“起卦”且不含其他TTS；弃用Seedance原音后应保持数字静音。
silence_log="$(ffmpeg -hide_banner -nostats -ss 2.2 -t 1.3 -i "$output" -map 0:a:0 -af silencedetect=noise=-70dB:d=1.0 -f null - 2>&1)"
print -r -- "$silence_log" | rg -q 'silence_duration: 1\.[0-9]'
echo "cyber divination ep01 voiced video: PASS (${duration}s)"
