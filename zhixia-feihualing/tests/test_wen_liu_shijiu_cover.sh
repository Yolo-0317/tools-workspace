#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
output="$project_dir/exports/wen-liu-shijiu-cover-v01.png"
test -s "$output"
dimensions="$(sips -g pixelWidth -g pixelHeight "$output" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w"x"h}')"
test "$dimensions" = "941x1672"
echo "wen-liu-shijiu cover: PASS"
