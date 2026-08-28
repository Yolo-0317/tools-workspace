#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
output="$project_dir/exports/cyber-divination-ep01-cover-v01.png"

test -s "$output"
dimensions="$(sips -g pixelWidth -g pixelHeight "$output" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w"x"h}')"
test "$dimensions" = "720x1280"
ffmpeg -v error -i "$output" -frames:v 1 -f null -
echo "cyber divination ep01 cover: PASS"
