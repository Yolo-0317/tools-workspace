#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
builder="$project_dir/scripts/build_yiwu_yiyuan_huanxi_cha_cha_cover.sh"
renderer="$project_dir/scripts/render_yiwu_yiyuan_huanxi_cha_cha_cover.swift"
output="$project_dir/exports/yiwu-yiyuan-huanxi-cha-cha-10s-cover-v01.png"

fail() {
  print -u2 -r -- "FAIL: $1"
  exit 1
}

[[ -x "$builder" ]] || fail "missing executable heavenly cha-cha cover builder"
[[ -x "$renderer" ]] || fail "missing executable heavenly cha-cha cover renderer"

"$builder" >/dev/null

[[ -s "$output" ]] || fail "missing rendered cover"
ffmpeg -v error -i "$output" -f null -

dimensions="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$output")"
[[ "$dimensions" == "1080x1920" ]] || fail "unexpected dimensions: $dimensions"

codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$output")"
[[ "$codec" == "png" ]] || fail "unexpected codec: $codec"

rg -q '步步生风' "$renderer" || fail "missing revised main title"
rg -q '一舞一愿' "$renderer" || fail "missing revised series label"
if rg -q 'drawVerticalTitle\("欢喜"' "$renderer"; then
  fail "rejected old main title remains"
fi

print -r -- "PASS: heavenly cha-cha 1080x1920 cover is ready"
