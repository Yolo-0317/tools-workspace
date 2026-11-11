#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/assets/video/content-seedance-xianxia-v01.mp4"
renderer="$project_dir/scripts/render_yiwu_yiyuan_restart_12s_cover.swift"
scratch="$(mktemp -d /tmp/zhixia-yiwu-restart-cover-zoom-test.XXXXXX)"
trap 'rm -rf "$scratch"' EXIT
base="$scratch/base.png"
output="$scratch/output.png"
stderr_file="$scratch/stderr.txt"

ffmpeg -hide_banner -loglevel error -y \
  -ss 11.900 -i "$source_video" -frames:v 1 -vf "format=rgb24" "$base"

export CLANG_MODULE_CACHE_PATH="$scratch/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$scratch/swift-module-cache"

if swift "$renderer" "$base" "$output" 1.0 2>"$stderr_file"; then
  print -u2 "FAIL: renderer accepted a non-enlarging zoom"
  exit 1
fi

rg -q 'zoom must be greater than 1' "$stderr_file" || {
  print -u2 "FAIL: renderer did not explain the invalid zoom"
  exit 1
}

print "PASS: 一舞一愿 restart cover zoom validation is ready"
