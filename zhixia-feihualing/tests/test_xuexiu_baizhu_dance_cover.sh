#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_xuexiu_baizhu_dance_cover.sh"
renderer="$project_dir/scripts/render_xuexiu_baizhu_dance_cover.swift"
source_video="$project_dir/exports/xuexiu-baizhu-15s-voiced-v01.mp4"
output="$project_dir/exports/xuexiu-baizhu-dance-cover-v01.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing Xuexiu Baizhu voiced source"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Xuexiu Baizhu cover builder"; exit 1; }
[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Xuexiu Baizhu cover renderer"; exit 1; }

rg -q -- '-ss 0.800' "$build_script" || { print -u2 "FAIL: cover must use frame 0.800"; exit 1; }
rg -q 'drawVertical\("栀夏"' "$renderer" || { print -u2 "FAIL: missing Zhixia label"; exit 1; }
rg -q 'drawVertical\("雪袖白纻"' "$renderer" || { print -u2 "FAIL: missing Xuexiu Baizhu title"; exit 1; }
rg -q 'drawVertical\("唐·李白《白纻辞三首·其三》"' "$renderer" || { print -u2 "FAIL: missing poem attribution"; exit 1; }

"$build_script" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: Xuexiu Baizhu cover was not created"; exit 1; }

properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'
ffmpeg -v error -i "$output" -f null -

print "PASS: Xuexiu Baizhu dance cover is ready"
