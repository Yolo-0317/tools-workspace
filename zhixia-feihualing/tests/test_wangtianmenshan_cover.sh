#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
build="$project_dir/scripts/build_wangtianmenshan_cover.sh"
renderer="$project_dir/scripts/render_wangtianmenshan_cover.swift"
output="$project_dir/exports/wangtianmenshan-dance-cover-v01.png"
[[ -x "$build" ]] || { print -u2 "FAIL: missing executable Wangtianmenshan cover build script"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Wangtianmenshan cover renderer"; exit 1; }
"$build" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: cover was not created"; exit 1; }
props="$(sips -g format -g pixelWidth -g pixelHeight -g space -g hasAlpha "$output" 2>/dev/null)"
print -r -- "$props" | rg -q 'format: png'
print -r -- "$props" | rg -q 'pixelWidth: 1080'
print -r -- "$props" | rg -q 'pixelHeight: 1920'
print -r -- "$props" | rg -q 'space: RGB'
print -r -- "$props" | rg -q 'hasAlpha: no'
print "PASS: Wangtianmenshan cover is ready"
