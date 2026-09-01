#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/assets/video/content-seedance-xianxia-v01.mp4"
build_script="$project_dir/scripts/build_yiwu_yiyuan_restart_12s_cover_v03.sh"
v01="$project_dir/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v01.png"
v02="$project_dir/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v02.png"
v03="$project_dir/exports/yiwu-yiyuan-qiancheng-01-restart-12s-cover-v03.png"
scratch="$(mktemp -d /tmp/zhixia-yiwu-restart-cover-v03-test.XXXXXX)"
trap 'rm -rf "$scratch"' EXIT
expected_frame="$scratch/expected-frame.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing 一舞一愿 restart source video"; exit 1; }
[[ -s "$v01" ]] || { print -u2 "FAIL: missing preserved 一舞一愿 restart cover v01"; exit 1; }
[[ -s "$v02" ]] || { print -u2 "FAIL: missing preserved 一舞一愿 restart cover v02"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable 一舞一愿 restart cover v03 builder"; exit 1; }

"$build_script" >/dev/null
[[ -s "$v03" ]] || { print -u2 "FAIL: 一舞一愿 restart cover v03 was not created"; exit 1; }

properties="$(sips -g pixelWidth -g pixelHeight -g format "$v03")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'
ffmpeg -v error -i "$v03" -f null -

ffmpeg -hide_banner -loglevel error -y \
  -ss 12.300 -i "$source_video" -frames:v 1 \
  -vf "scale=1234:2150,crop=1080:1920,format=rgb24" \
  "$expected_frame"

ssim_output="$(ffmpeg -hide_banner -i "$v03" -i "$expected_frame" \
  -lavfi "[0:v]crop=1080:1000:0:900[a];[1:v]crop=1080:1000:0:900[b];[a][b]ssim" \
  -f null - 2>&1)"
ssim_value="$(print -r -- "$ssim_output" | sed -n 's/.* All:\([0-9.]*\) .*/\1/p' | tail -1)"
[[ -n "$ssim_value" ]] || { print -u2 "FAIL: unable to measure cover v03 frame similarity"; exit 1; }
awk -v value="$ssim_value" 'BEGIN { exit !(value >= 0.94) }' || {
  print -u2 "FAIL: cover v03 does not use the approved 12.300-second frame"
  exit 1
}

for previous in "$v01" "$v02"; do
  cmp -s "$previous" "$v03" && {
    print -u2 "FAIL: cover v03 must not duplicate an earlier cover"
    exit 1
  }
done

print "PASS: 一舞一愿 restart cover v03 is ready"
