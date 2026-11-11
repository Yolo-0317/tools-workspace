#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source_video="$project_dir/exports/jingtao-voiced-v01.mp4"
renderer="$project_dir/scripts/render_jingtao_dance_cover.swift"
output="$project_dir/exports/jingtao-dance-cover-v01.png"
build_dir="$(mktemp -d /tmp/zhixia-jingtao-cover.XXXXXX)"
base="$build_dir/base.png"
trap 'rm -rf "$build_dir"' EXIT

for required in "$source_video" "$renderer"; do
  if [[ ! -s "$required" ]]; then
    print -u2 -r -- "missing required cover component: $required"
    exit 1
  fi
done

mkdir -p "$(dirname "$output")"

ffmpeg -hide_banner -loglevel error -y \
  -ss 4.000 -i "$source_video" -frames:v 1 \
  -vf "scale=1080:1920:flags=lanczos,format=rgb24" "$base"

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$base" "$output"

print -r -- "$output"
