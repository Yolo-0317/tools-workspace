#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
raw="$project_dir/episodes/lushan/assets/video/content-raw-v01.mp4"
waterfall="$project_dir/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3"
source_note="$project_dir/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149-source.md"

test -s "$raw"
test -s "$waterfall"
test -s "$source_note"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$raw")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$raw")" = "24/1"
raw_duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$raw")"
waterfall_duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$waterfall")"
awk -v d="$raw_duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
awk -v d="$waterfall_duration" 'BEGIN { exit !(d >= 15.104) }'
rg -q "Alex_Jauk" "$source_note"
rg -q "Pixabay Content License" "$source_note"
rg -q "https://pixabay.com/sound-effects/large-waterfall-sound-196149/" "$source_note"
echo "lushan waterfall assets: PASS"
