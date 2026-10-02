#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/liangzhouci-15s/assets/video/content-seedance-v01.mp4"
renderer="$project_dir/scripts/render_liangzhouci_flight_cover.swift"
output="$project_dir/exports/liangzhouci-flight-cover-v01.png"
build_dir="$(mktemp -d /tmp/zhixia-liangzhouci-flight-cover.XXXXXX)"
base="$build_dir/base.png"
rendered="$build_dir/rendered.png"
trap 'rm -rf "$build_dir"' EXIT

for required in "$source_video" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "missing required cover component: $required"; exit 1; }
done

mkdir -p "${output:h}"

ffmpeg -hide_banner -loglevel error -y \
  -ss 12.000 -i "$source_video" -frames:v 1 \
  -vf "scale=1080:1920:flags=lanczos,format=rgb24" "$base"

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$base" "$rendered"

ffmpeg -hide_banner -loglevel error -y \
  -i "$rendered" -frames:v 1 -vf "format=rgb24" "$output"

print -r -- "$output"
