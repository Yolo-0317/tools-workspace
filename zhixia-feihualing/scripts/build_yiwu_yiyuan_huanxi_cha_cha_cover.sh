#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
reference="$project_dir/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/assets/cover/cover-reference-v01.png"
renderer="$project_dir/scripts/render_yiwu_yiyuan_huanxi_cha_cha_cover.swift"
output="$project_dir/exports/yiwu-yiyuan-huanxi-cha-cha-10s-cover-v01.png"
build_dir="$(mktemp -d /private/tmp/zhixia-cha-cha-cover.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT
temporary_output="$build_dir/cover.png"

[[ -s "$reference" ]] || { print -u2 -r -- "missing cover reference: $reference"; exit 1; }
[[ -x "$renderer" ]] || { print -u2 -r -- "missing executable cover renderer: $renderer"; exit 1; }

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$reference" "$temporary_output"

mkdir -p "${output:h}"
mv "$temporary_output" "$output"
print -r -- "$output"
