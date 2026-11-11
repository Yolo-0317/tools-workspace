#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_jingci_lotus_cover.sh"
renderer="$project_dir/scripts/render_jingci_lotus_cover.swift"
output="$project_dir/exports/jingci-lotus-dance-cover-v01.png"

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Jingci lotus cover build script"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Jingci lotus cover renderer"; exit 1; }

"$build_script" >/dev/null

[[ -s "$output" ]] || { print -u2 "FAIL: Jingci lotus cover was not created"; exit 1; }

properties="$(sips -g format -g pixelWidth -g pixelHeight -g space -g hasAlpha "$output" 2>/dev/null)"
print -r -- "$properties" | rg -q 'format: png' || { print -u2 "FAIL: cover is not PNG"; exit 1; }
print -r -- "$properties" | rg -q 'pixelWidth: 1080' || { print -u2 "FAIL: cover width is not 1080"; exit 1; }
print -r -- "$properties" | rg -q 'pixelHeight: 1920' || { print -u2 "FAIL: cover height is not 1920"; exit 1; }
print -r -- "$properties" | rg -q 'space: RGB' || { print -u2 "FAIL: cover is not RGB"; exit 1; }
print -r -- "$properties" | rg -q 'hasAlpha: no' || { print -u2 "FAIL: cover unexpectedly has transparency"; exit 1; }

print "PASS: Jingci lotus dance cover is ready"
