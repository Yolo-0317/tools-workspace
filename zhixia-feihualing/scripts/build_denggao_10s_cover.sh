#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source_video="$project_dir/episodes/denggao-10s/assets/video/content-seedance-v01.mp4"
base="$project_dir/exports/denggao-10s-cover-base-v01.png"
output="$project_dir/exports/denggao-10s-cover-v01.png"
build_dir="$(mktemp -d /tmp/zhixia-denggao-cover.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

test -s "$source_video"
mkdir -p "$(dirname "$output")"

ffmpeg -hide_banner -loglevel error -y \
  -ss 2.300 -i "$source_video" -frames:v 1 \
  -vf "scale=1080:1920:flags=lanczos,format=rgb24" "$base"

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$project_dir/scripts/render_denggao_10s_cover.swift" "$base" "$output"

echo "$output"
