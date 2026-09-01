#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/assets/video/content-seedance-xianxia-v01.mp4"
renderer="$project_dir/scripts/render_yiwu_yiyuan_restart_12s_cover.swift"
output="$project_dir/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v02.png"
build_dir="$(mktemp -d /tmp/zhixia-yiwu-restart-cover-v02.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT
base="$build_dir/base.png"

[[ -s "$source_video" ]] || { print -u2 "Missing source video: $source_video"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "Missing renderer: $renderer"; exit 1; }

ffmpeg -hide_banner -loglevel error -y \
  -ss 11.900 -i "$source_video" -frames:v 1 \
  -vf "format=rgb24" "$base"

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$base" "$output" 1.12

print -r -- "$output"
