#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
renderer="$project_dir/scripts/render_subtitle_cards.swift"
manifest="$project_dir/tests/fixtures/subtitles-with-attribution.json"
test_dir="$(mktemp -d /tmp/zhixia-attribution-test.XXXXXX)"
trap 'rm -rf "$test_dir"' EXIT
export CLANG_MODULE_CACHE_PATH="$test_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$test_dir/swift-module-cache"

swift "$renderer" "$manifest" "$test_dir"
card="$test_dir/attributed-poem.png"
test -f "$card"

main_mean="$(ffmpeg -hide_banner -loglevel error -i "$card" \
  -vf "alphaextract,crop=100:620:120:40,signalstats,metadata=print:file=-" \
  -frames:v 1 -f null - 2>/dev/null | awk -F= '/lavfi.signalstats.YAVG/ {print $2; exit}')"
source_mean="$(ffmpeg -hide_banner -loglevel error -i "$card" \
  -vf "alphaextract,crop=95:430:10:40,signalstats,metadata=print:file=-" \
  -frames:v 1 -f null - 2>/dev/null | awk -F= '/lavfi.signalstats.YAVG/ {print $2; exit}')"

awk -v value="$main_mean" 'BEGIN { exit !(value > 0.1) }'
awk -v value="$source_mean" 'BEGIN { exit !(value > 0.1) }'
rg -q 'attribution' "$renderer"

echo "PASS: rendered poem and attribution in separate vertical zones"
