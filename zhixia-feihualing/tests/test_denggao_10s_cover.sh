#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
base="$project_dir/exports/denggao-10s-cover-base-v01.png"
output="$project_dir/exports/denggao-10s-cover-v01.png"

for image in "$base" "$output"; do
  test -s "$image"
  dimensions="$(sips -g pixelWidth -g pixelHeight "$image" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w "x" h}')"
  test "$dimensions" = "1080x1920"
  test "$(file -b --mime-type "$image")" = "image/png"
  ffmpeg -v error -i "$image" -f null -
done

base_hash="$(shasum -a 256 "$base" | awk '{print $1}')"
output_hash="$(shasum -a 256 "$output" | awk '{print $1}')"
test "$base_hash" != "$output_hash"

echo "denggao 10s cover: PASS"
