#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/jingtao-voiced-v01.mp4"
builder="$project_dir/scripts/build_jingtao_dance_cover.sh"
renderer="$project_dir/scripts/render_jingtao_dance_cover.swift"
output="$project_dir/exports/jingtao-dance-cover-v01.png"
inventory="$project_dir/assets/inventory.csv"

for required in "$source_video" "$builder" "$renderer" "$inventory"; do
  if [[ ! -s "$required" ]]; then
    print -u2 -r -- "FAIL: missing required cover component $required"
    exit 1
  fi
done

if [[ ! -x "$builder" ]]; then
  print -u2 -r -- "FAIL: cover builder is not executable: $builder"
  exit 1
fi

"$builder" >/dev/null

if [[ ! -s "$output" ]]; then
  print -u2 -r -- "FAIL: cover was not generated"
  exit 1
fi

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

rg -qF "jingtao-dance-cover-v01" "$inventory" || {
  print -u2 "FAIL: cover is not registered in asset inventory"
  exit 1
}

print -r -- "PASS: Jingtao dance cover is valid, 1080x1920, and inventoried"
