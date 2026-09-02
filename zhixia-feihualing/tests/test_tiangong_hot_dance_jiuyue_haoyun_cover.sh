#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voiced-v01.mp4"
builder="$project_dir/scripts/build_tiangong_hot_dance_jiuyue_haoyun_cover.sh"
renderer="$project_dir/scripts/render_tiangong_hot_dance_jiuyue_haoyun_cover.swift"
output="$project_dir/exports/tiangong-hot-dance-jiuyue-haoyun-cover-v01.png"
cover_time="9.400"

fail() {
  print -u2 -r -- "FAIL: $1"
  exit 1
}

[[ -s "$source_video" ]] || fail "missing 九月好运无字幕有声成片"
[[ -x "$builder" ]] || fail "missing executable 九月好运封面 builder"
[[ -s "$renderer" ]] || fail "missing 九月好运封面 renderer"

"$builder" >/dev/null
[[ -s "$output" ]] || fail "missing rendered 九月好运封面"
ffmpeg -v error -i "$output" -f null - || fail "cover decode failed"

media_json="$(
  ffprobe -v error \
    -show_entries stream=codec_name,width,height,pix_fmt:format=duration \
    -of json "$output"
)"
print -r -- "$media_json" | jq -e '
  (.streams | length) == 1 and
  .streams[0].codec_name == "png" and
  .streams[0].width == 1080 and
  .streams[0].height == 1920 and
  (.streams[0].pix_fmt | startswith("rgb"))
' >/dev/null || fail "invalid cover media parameters"

test_dir="$(mktemp -d /tmp/zhixia-jiuyue-cover-test.XXXXXX)"
trap 'rm -rf "$test_dir"' EXIT
reference="$test_dir/reference.png"
mobile="$test_dir/mobile.png"
ffmpeg -y -v error -ss "$cover_time" -i "$source_video" \
  -frames:v 1 -vf "scale=1080:1920:flags=lanczos,format=rgb24" "$reference"

reference_hash="$(shasum -a 256 "$reference" | awk '{print $1}')"
output_hash="$(shasum -a 256 "$output" | awk '{print $1}')"
[[ "$reference_hash" != "$output_hash" ]] || fail "cover text was not rendered"

ssim_log="$(
  ffmpeg -hide_banner -i "$reference" -i "$output" \
    -filter_complex "[0:v]crop=800:1150:180:570[a];[1:v]crop=800:1150:180:570[b];[a][b]ssim" \
    -f null - 2>&1
)"
ssim_value="$(print -r -- "$ssim_log" | sed -n 's/.*All:\([0-9.]*\).*/\1/p' | tail -1)"
[[ -n "$ssim_value" ]] || fail "cannot measure character-area fidelity"
awk -v value="$ssim_value" 'BEGIN { exit !(value >= 0.98) }' || \
  fail "character area changed unexpectedly: SSIM $ssim_value"

ffmpeg -y -v error -i "$output" -vf scale=270:480 -frames:v 1 "$mobile"
[[ -s "$mobile" ]] || fail "missing mobile thumbnail preview"
ffmpeg -v error -i "$mobile" -f null - || fail "mobile thumbnail decode failed"

print -r -- "PASS: 九月好运天宫双姝封面已就绪"
