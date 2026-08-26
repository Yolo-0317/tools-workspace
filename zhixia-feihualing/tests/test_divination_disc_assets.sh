#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
vector="$project_dir/assets/props/ai-divination-disk-v01/vector/disc-master.svg"
preview="$project_dir/assets/props/ai-divination-disk-v01/previews/disc-master.png"
board="$project_dir/assets/props/ai-divination-disk-v01/master.png"
partial="$project_dir/assets/props/ai-divination-disk-v01/vector/state-partial-3.svg"
complete="$project_dir/assets/props/ai-divination-disk-v01/vector/state-shanlei-yi.svg"

test -s "$vector"
test -s "$preview"
test -s "$board"
test -s "$partial"
test -s "$complete"
python3 -m unittest "$project_dir/tests/test_divination_disc_vectors.py" -v

dimensions="$(
  sips -g pixelWidth -g pixelHeight "$preview" 2>/dev/null \
    | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w" "h}'
)"
test "$dimensions" = "2048 2048"
ffmpeg -v error -i "$preview" -frames:v 1 -f null -

board_dimensions="$(
  sips -g pixelWidth -g pixelHeight "$board" 2>/dev/null \
    | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w" "h}'
)"
test "$board_dimensions" = "1920 1080"
ffmpeg -v error -i "$board" -frames:v 1 -f null -

yang_luma="$(
  ffmpeg -v error -i "$board" \
    -vf 'crop=300:60:800:950,signalstats,metadata=print:file=-' \
    -frames:v 1 -f null - 2>&1 \
    | awk -F= '/lavfi.signalstats.YMAX/{print $2; exit}'
)"
yin_luma="$(
  ffmpeg -v error -i "$board" \
    -vf 'crop=300:60:1270:950,signalstats,metadata=print:file=-' \
    -frames:v 1 -f null - 2>&1 \
    | awk -F= '/lavfi.signalstats.YMAX/{print $2; exit}'
)"
awk -v value="$yang_luma" 'BEGIN { exit !(value >= 100) }'
awk -v value="$yin_luma" 'BEGIN { exit !(value >= 100) }'

echo "divination disc vector assets: PASS"
