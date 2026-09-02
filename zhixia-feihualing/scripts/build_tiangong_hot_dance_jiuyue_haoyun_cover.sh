#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voiced-v01.mp4"
renderer="$project_dir/scripts/render_tiangong_hot_dance_jiuyue_haoyun_cover.swift"
output="$project_dir/exports/tiangong-hot-dance-jiuyue-haoyun-cover-v01.png"
cover_time="9.400"
build_dir="$(mktemp -d /tmp/zhixia-jiuyue-cover.XXXXXX)"
base="$build_dir/base.png"
temporary_output="$build_dir/cover.png"
rgb_output="$build_dir/cover-rgb.png"
trap 'rm -rf "$build_dir"' EXIT

[[ -s "$source_video" ]] || {
  print -u2 -r -- "Missing source video: $source_video"
  exit 1
}
[[ -s "$renderer" ]] || {
  print -u2 -r -- "Missing cover renderer: $renderer"
  exit 1
}

ffmpeg -hide_banner -loglevel error -y \
  -ss "$cover_time" -i "$source_video" -frames:v 1 \
  -vf "scale=1080:1920:flags=lanczos,format=rgb24" "$base"

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$base" "$temporary_output"

ffmpeg -hide_banner -loglevel error -y \
  -i "$temporary_output" -frames:v 1 -vf format=rgb24 "$rgb_output"

mkdir -p "${output:h}"
mv "$rgb_output" "$output"
print -r -- "$output"
