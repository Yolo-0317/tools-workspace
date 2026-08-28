#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
output="$project_dir/exports/ep06-autumn-subtitled-v03.mp4"
cards_dir="$project_dir/assets/subtitles/ep06-autumn-v3"

test -f "$output"
for card in 01-poem-00 02-poem-01 03-poem-02; do
  test -f "$cards_dir/$card.png"
done

width="$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$output")"
height="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$output")"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
audio_codec="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")"

test "$width" = "720"
test "$height" = "1280"
test "$audio_codec" = "aac"
awk -v value="$duration" 'BEGIN { exit !(value >= 15.0 && value <= 15.1) }'
ffmpeg -v error -i "$output" -f null -

echo "PASS: EP06 autumn v3 is a decodable 15-second three-poem video"
