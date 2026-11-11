#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/gucuizhezhi-15s-voiced-v01.mp4"
renderer="$project_dir/scripts/render_gucuizhezhi_dance_cover.swift"
output="$project_dir/exports/gucuizhezhi-dance-cover-v01.png"
build_dir="$(mktemp -d /tmp/zhixia-gucuizhezhi-cover.XXXXXX)"
base="$build_dir/base.png"
trap 'rm -rf "$build_dir"' EXIT

for required in "$source_video" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "missing required Gucuizhezhi cover component: $required"; exit 1; }
done

mkdir -p "${output:h}"
ffmpeg -hide_banner -loglevel error -y \
  -ss 7.500 -i "$source_video" -frames:v 1 \
  -vf "format=rgb24" "$base"

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$base" "$output"

print -r -- "$output"
