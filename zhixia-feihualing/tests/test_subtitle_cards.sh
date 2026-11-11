#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
renderer="$project_dir/scripts/render_subtitle_cards.swift"
manifest="$project_dir/episodes/ep01/subtitles-flower.json"
test_dir="$(mktemp -d /tmp/zhixia-subtitle-test.XXXXXX)"
trap 'rm -rf "$test_dir"' EXIT
export CLANG_MODULE_CACHE_PATH="$test_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$test_dir/swift-module-cache"

rg -q 'size: 70' "$renderer"
rg -q 'strokeWidth: -1.6' "$renderer"
rg -q 'calibratedRed: 1.0, green: 0.10, blue: 0.035' "$renderer"

swift "$renderer" "$manifest" "$test_dir"

expected=(
  01-opening.png
  02-poem-01.png
  03-poem-02.png
  04-poem-03.png
  05-outro.png
)

for name in "${expected[@]}"; do
  file="$test_dir/$name"
  test -f "$file"
  width="$(sips -g pixelWidth "$file" | awk '/pixelWidth/ {print $2}')"
  height="$(sips -g pixelHeight "$file" | awk '/pixelHeight/ {print $2}')"
  test "$width" = "720"
  test "$height" = "1280"

  top_left_mean="$(ffmpeg -hide_banner -loglevel error -i "$file" \
    -vf "alphaextract,crop=230:620:0:0,signalstats,metadata=print:file=-" \
    -frames:v 1 -f null - 2>/dev/null | awk -F= '/lavfi.signalstats.YAVG/ {print $2; exit}')"
  bottom_mean="$(ffmpeg -hide_banner -loglevel error -i "$file" \
    -vf "alphaextract,crop=720:400:0:880,signalstats,metadata=print:file=-" \
    -frames:v 1 -f null - 2>/dev/null | awk -F= '/lavfi.signalstats.YAVG/ {print $2; exit}')"
  awk -v value="$top_left_mean" 'BEGIN { exit !(value > 0.1) }'
  awk -v value="$bottom_mean" 'BEGIN { exit !(value == 0) }'
done

if SUBTITLE_FONT="/tmp/definitely-missing-songti.ttc" swift "$renderer" "$manifest" "$test_dir/missing-font"; then
  echo "FAIL: missing font should return a non-zero status"
  exit 1
fi

echo "PASS: rendered five top-left vertical 720x1280 subtitle cards and rejected a missing font"
