#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
vector="$project_dir/assets/props/ai-divination-disk-v01/vector/disc-master.svg"
preview="$project_dir/assets/props/ai-divination-disk-v01/previews/disc-master.png"

test -s "$vector"
test -s "$preview"
python3 -m unittest "$project_dir/tests/test_divination_disc_vectors.py" -v

dimensions="$(
  sips -g pixelWidth -g pixelHeight "$preview" 2>/dev/null \
    | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w" "h}'
)"
test "$dimensions" = "2048 2048"
ffmpeg -v error -i "$preview" -frames:v 1 -f null -

echo "divination disc vector assets: PASS"
