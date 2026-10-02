#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/quzhong-huteng-15s-voiced-v01.mp4"
build_script="$project_dir/scripts/build_quzhong_huteng_dance_cover.sh"
output="$project_dir/exports/quzhong-huteng-dance-cover-v01.png"
scratch="$(mktemp -d /tmp/zhixia-quzhong-cover-test.XXXXXX)"
trap 'rm -rf "$scratch"' EXIT
plain_frame="$scratch/plain-frame.png"

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing 曲终胡腾 voiced source"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable 曲终胡腾 cover builder"; exit 1; }

"$build_script" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: 曲终胡腾 cover was not created"; exit 1; }

properties="$(sips -g pixelWidth -g pixelHeight -g format "$output")"
print -r -- "$properties" | rg -q 'pixelWidth: 1080'
print -r -- "$properties" | rg -q 'pixelHeight: 1920'
print -r -- "$properties" | rg -q 'format: png'
ffmpeg -v error -i "$output" -f null -

ffmpeg -hide_banner -loglevel error -y \
  -ss 7.250 -i "$source_video" -frames:v 1 -vf "format=rgb24" "$plain_frame"
[[ "$(shasum -a 256 "$output" | awk '{print $1}')" != "$(shasum -a 256 "$plain_frame" | awk '{print $1}')" ]] || {
  print -u2 "FAIL: cover typography was not rendered"
  exit 1
}

print "PASS: 曲终胡腾 dance cover is ready"
