#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
base="$project_dir/episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-base-v01.png"
renderer="$project_dir/scripts/render_yunzhongjun_cover.swift"
episode_output="$project_dir/episodes/jiuge-yunzhongjun-15s/assets/cover/yunzhongjun-cover-v01.png"
export_output="$project_dir/exports/yunzhongjun-cover-v01.png"
build_dir=$(mktemp -d /tmp/zhixia-yunzhongjun-cover.XXXXXX)
trap 'rm -rf "$build_dir"' EXIT

for required in "$base" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "missing required Yunzhongjun cover component: $required"; exit 1; }
done

mkdir -p "${episode_output:h}" "${export_output:h}"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$base" "$episode_output"
cp "$episode_output" "$export_output"

print -r -- "$export_output"
