#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/feimei-lvyao-15s-voiced-v01.mp4"
build_script="$project_dir/scripts/build_feimei_lvyao_dance_cover.sh"
renderer="$project_dir/scripts/render_feimei_lvyao_dance_cover.swift"
output="$project_dir/exports/feimei-lvyao-dance-cover-v01.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing Feimei Lvyao voiced source"; exit 1; }
source_hash="$(shasum -a 256 "$source_video" | awk '{print $1}')"
[[ "$source_hash" == "9935399575bdc9ed648a12ecaf62c42b9f01ea9160e2cf5484918ac5febee071" ]] || {
  print -u2 "FAIL: Feimei Lvyao voiced source hash changed"
  exit 1
}
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Feimei Lvyao cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Feimei Lvyao cover renderer"; exit 1; }

rg -q -- '-ss 13.000' "$build_script" || { print -u2 "FAIL: cover must use frame 13.000"; exit 1; }
rg -q 'drawVertical\("栀夏"' "$renderer" || { print -u2 "FAIL: missing Zhixia label"; exit 1; }
rg -q 'drawVertical\("飞袂绿腰"' "$renderer" || { print -u2 "FAIL: missing Feimei Lvyao title"; exit 1; }
rg -q 'drawVertical\("唐·李群玉《长沙九日登东楼观舞》"' "$renderer" || {
  print -u2 "FAIL: missing poem attribution"
  exit 1
}

"$build_script" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: Feimei Lvyao cover was not created"; exit 1; }

properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'
ffmpeg -v error -i "$output" -f null -

print "PASS: Feimei Lvyao dance cover is ready"
