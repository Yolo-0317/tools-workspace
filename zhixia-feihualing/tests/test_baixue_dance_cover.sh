#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/baixue/assets/video/content-seedance-v01.mp4"
builder="$project_dir/scripts/build_baixue_dance_cover.sh"
renderer="$project_dir/scripts/render_baixue_dance_cover.swift"
output="$project_dir/exports/baixue-dance-cover-v01.png"

for required in "$source_video" "$builder" "$renderer"; do
  if [[ ! -s "$required" ]]; then
    print -u2 -r -- "FAIL: missing required cover component $required"
    exit 1
  fi
done

zsh "$builder" >/dev/null

if [[ ! -s "$output" ]]; then
  print -u2 -r -- "FAIL: cover was not generated"
  exit 1
fi

dimensions="$(ffprobe -v error -show_entries stream=width,height -of csv=p=0 "$output")"
if [[ "$dimensions" != "1080,1920" ]]; then
  print -u2 -r -- "FAIL: expected 1080,1920, got $dimensions"
  exit 1
fi

ffmpeg -v error -i "$output" -frames:v 1 -f null -
rg -qF "baixue-dance-cover-v01" "$project_dir/assets/inventory.csv"

print -r -- "PASS: Baixue dance cover is valid, 1080x1920, and inventoried"
