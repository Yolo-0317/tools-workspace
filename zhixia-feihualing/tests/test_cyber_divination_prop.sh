#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
prop="$project_dir/assets/props/ai-divination-disk-v01/master.png"
inventory="$project_dir/assets/inventory.csv"

test -s "$prop"

dimensions="$(
  sips -g pixelWidth -g pixelHeight "$prop" 2>/dev/null \
    | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w" "h}'
)"
read width height <<< "$dimensions"
awk -v w="$width" -v h="$height" \
  'BEGIN { exit !(w >= 720 && h >= 1280 && w / h >= 0.55 && w / h <= 0.57) }'

ffmpeg -v error -i "$prop" -frames:v 1 -f null -
rg -q \
  '^ai-divination-disk-v01,prop,AI卦盘,identity-master,assets/props/ai-divination-disk-v01/master.png,approved,' \
  "$inventory"

echo "cyber divination prop: PASS"
