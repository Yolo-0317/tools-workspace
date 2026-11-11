#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
output="$project_dir/exports/yesu-shansi-oner-lingling-subtitled-v01.mp4"
cards_dir="$project_dir/assets/subtitles/yesu-shansi-oner-lingling-full"

test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of csv=p=0 "$output")" = "2"

duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'

for card in \
  01-ayan-lead.png \
  02-zhixia-reply.png \
  03-zhixia-stars.png \
  04-ayan-reach.png \
  05-zhixia-poem-one.png \
  06-zhixia-poem-two.png; do
  test -s "$cards_dir/$card"
  test "$(sips -g pixelWidth -g pixelHeight "$cards_dir/$card" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w "x" h}')" = "720x1280"
done

ffmpeg -v error -i "$output" -f null -

echo "yesu shansi lingling subtitled video: PASS (${duration}s)"
