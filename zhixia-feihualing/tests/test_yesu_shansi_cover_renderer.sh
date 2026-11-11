#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
base="$project_dir/episodes/yesu-shansi/assets/cover/yesu-shansi-cover-base-v01.png"
renderer="$project_dir/scripts/render_yesu_shansi_cover.swift"
test_dir="$(mktemp -d /tmp/zhixia-cover-test.XXXXXX)"
output="$test_dir/cover.png"
scaled_base="$test_dir/base-1080x1920.png"
trap 'rm -rf "$test_dir"' EXIT
export CLANG_MODULE_CACHE_PATH="$test_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$test_dir/swift-module-cache"

test -s "$base"
swift "$renderer" "$base" "$output"

test -s "$output"
test "$(sips -g pixelWidth -g pixelHeight "$output" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w "x" h}')" = "1080x1920"

ffmpeg -hide_banner -loglevel error -y -i "$base" -vf scale=1080:1920 "$scaled_base"
base_title_md5="$(ffmpeg -v error -i "$scaled_base" -vf crop=260:850:45:180 -f md5 - | sed 's/^MD5=//')"
cover_title_md5="$(ffmpeg -v error -i "$output" -vf crop=260:850:45:180 -f md5 - | sed 's/^MD5=//')"
base_credit_md5="$(ffmpeg -v error -i "$scaled_base" -vf crop=900:120:90:1740 -f md5 - | sed 's/^MD5=//')"
cover_credit_md5="$(ffmpeg -v error -i "$output" -vf crop=900:120:90:1740 -f md5 - | sed 's/^MD5=//')"

test "$base_title_md5" != "$cover_title_md5"
test "$base_credit_md5" != "$cover_credit_md5"

echo "yesu shansi cover renderer: PASS"
