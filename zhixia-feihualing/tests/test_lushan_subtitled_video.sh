#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
mix="$project_dir/exports/lushan-waterfall-mix-preview-v01.mp4"
output="$project_dir/exports/lushan-subtitled-v01.mp4"

test -s "$mix"
test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"

duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'

mix_audio_md5="$(ffmpeg -v error -i "$mix" -map 0:a:0 -c copy -f md5 - | sed 's/^MD5=//')"
output_audio_md5="$(ffmpeg -v error -i "$output" -map 0:a:0 -c copy -f md5 - | sed 's/^MD5=//')"
test "$mix_audio_md5" = "$output_audio_md5"

mix_video_md5="$(ffmpeg -v error -i "$mix" -map 0:v:0 -f md5 - | sed 's/^MD5=//')"
output_video_md5="$(ffmpeg -v error -i "$output" -map 0:v:0 -f md5 - | sed 's/^MD5=//')"
test "$mix_video_md5" != "$output_video_md5"

ffmpeg -v error -i "$output" -f null -

inventory="$project_dir/assets/inventory.csv"
python3 - "$inventory" <<'PY'
import csv
import sys

with open(sys.argv[1], encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))

matches = [row for row in rows if row["asset_id"] == "lushan-subtitled-v01"]
assert len(matches) == 1, f"expected one lushan-subtitled-v01 inventory row, got {len(matches)}"
assert matches[0]["path_or_url"] == "exports/lushan-subtitled-v01.mp4"
assert matches[0]["status"] == "final"
PY

echo "lushan subtitled video: PASS (${duration}s)"
