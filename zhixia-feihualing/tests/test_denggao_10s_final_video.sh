#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
output="$project_dir/exports/denggao-10s-subtitled-v01.mp4"
cards_dir="$project_dir/assets/subtitles/denggao-10s"

test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "1080x1920"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of csv=p=0 "$output")" = "48000"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of csv=p=0 "$output")" = "2"

duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 10.05 && d <= 10.15) }'

for card in \
  01-ayan-hook.png \
  02-zhixia-hook.png \
  03-zhixia-poem-one.png \
  04-zhixia-poem-two.png; do
  test -s "$cards_dir/$card"
  test "$(sips -g pixelWidth -g pixelHeight "$cards_dir/$card" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w "x" h}')" = "720x1280"
done

ffmpeg -v error -i "$output" -f null -

max_volume="$(ffmpeg -hide_banner -i "$output" -af volumedetect -f null - 2>&1 | awk '/max_volume/{print $5}')"
awk -v peak="$max_volume" 'BEGIN { exit !(peak <= -1.0) }'

echo "denggao 10s final video: PASS (${duration}s, max ${max_volume}dB)"
