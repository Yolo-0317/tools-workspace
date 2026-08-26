#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
asset_dir="$project_dir/assets/props/ai-divination-disk-v01"
vector_dir="$asset_dir/vector"
preview_dir="$asset_dir/previews"
build_dir="$(mktemp -d /tmp/zhixia-divination-disc.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

mkdir -p "$vector_dir" "$preview_dir"

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"

python3 "$project_dir/scripts/generate_divination_disc_vectors.py" "$vector_dir"
swift "$project_dir/scripts/rasterize_svg.swift" \
  "$vector_dir/disc-master.svg" \
  "$preview_dir/disc-master.png" \
  2048 \
  2048
