#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/assets/video/content-seedance-xianxia-v01.mp4"
build_script="$project_dir/scripts/build_yiwu_yiyuan_restart_12s_cover.sh"
output="$project_dir/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v01.png"
scratch="$(mktemp -d /tmp/zhixia-yiwu-restart-cover-test.XXXXXX)"
trap 'rm -rf "$scratch"' EXIT
expected_frame="$scratch/expected-frame.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing 一舞一愿 restart source video"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable 一舞一愿 restart cover builder"; exit 1; }

"$build_script" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: 一舞一愿 restart cover was not created"; exit 1; }

properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'
ffmpeg -v error -i "$output" -f null -

ffmpeg -hide_banner -loglevel error -y \
  -ss 11.500 -i "$source_video" -frames:v 1 \
  -vf "scale=1242:2208,crop=1080:1920,format=rgb24" \
  "$expected_frame"

ssim_output="$(ffmpeg -hide_banner -i "$output" -i "$expected_frame" \
  -lavfi "[0:v]crop=1080:1000:0:900[a];[1:v]crop=1080:1000:0:900[b];[a][b]ssim" \
  -f null - 2>&1)"
ssim_value="$(print -r -- "$ssim_output" | sed -n 's/.* All:\([0-9.]*\) .*/\1/p' | tail -1)"
[[ -n "$ssim_value" ]] || { print -u2 "FAIL: unable to measure cover frame similarity"; exit 1; }
awk -v value="$ssim_value" 'BEGIN { exit !(value >= 0.94) }' || {
  print -u2 "FAIL: cover does not use the approved 11.500-second frame"
  exit 1
}

print "PASS: 一舞一愿 restart cover is ready"
