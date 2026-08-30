#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/gucuizhezhi-15s-voiced-v01.mp4"
builder="$project_dir/scripts/build_gucuizhezhi_dance_cover.sh"
renderer="$project_dir/scripts/render_gucuizhezhi_dance_cover.swift"
output="$project_dir/exports/gucuizhezhi-dance-cover-v01.png"
inventory="$project_dir/assets/inventory.csv"

for required in "$source_video" "$builder" "$renderer" "$inventory"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Gucuizhezhi cover component $required"; exit 1; }
done

[[ -x "$builder" ]] || { print -u2 -r -- "FAIL: Gucuizhezhi cover builder is not executable"; exit 1; }

rg -qF 'drawVertical("栀夏"' "$renderer" || { print -u2 "FAIL: renderer lacks 栀夏 label"; exit 1; }
rg -qF 'drawVertical("鼓催柘枝"' "$renderer" || { print -u2 "FAIL: renderer lacks 鼓催柘枝 title"; exit 1; }
rg -qF 'drawVertical("唐·白居易《柘枝妓》"' "$renderer" || { print -u2 "FAIL: renderer lacks poem attribution"; exit 1; }

"$builder" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: Gucuizhezhi cover was not generated"; exit 1; }

media_spec="$(ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height \
  -of default=noprint_wrappers=1 "$output")"
[[ "$media_spec" == *"codec_name=png"* ]] || { print -u2 "FAIL: cover codec is not PNG"; exit 1; }
[[ "$media_spec" == *"width=1080"* ]] || { print -u2 "FAIL: cover width is not 1080"; exit 1; }
[[ "$media_spec" == *"height=1920"* ]] || { print -u2 "FAIL: cover height is not 1920"; exit 1; }

ffmpeg -v error -i "$output" -frames:v 1 -f null -
alpha_min="$(ffmpeg -hide_banner -loglevel error -i "$output" \
  -vf "alphaextract,signalstats,metadata=print:file=-" -frames:v 1 -f null - \
  | awk -F= '/lavfi.signalstats.YMIN/ { print $2; exit }')"
[[ "$alpha_min" == "255" ]] || { print -u2 "FAIL: cover contains transparent pixels"; exit 1; }

rg -qF "gucuizhezhi-dance-cover-v01" "$inventory" || {
  print -u2 "FAIL: Gucuizhezhi cover is not registered in asset inventory"
  exit 1
}

print -r -- "PASS: Gucuizhezhi dance cover is valid, 1080x1920, and inventoried"
