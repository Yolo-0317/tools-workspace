#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
final_image="$project_root/assets/characters/阿砚角色母板高写实CG-v01-最终版.png"
renderer="$project_root/scripts/render_ayan_profile_masterboard_v01.swift"

if [[ ! -s "$final_image" ]]; then
  echo "missing final Ayan masterboard: $final_image" >&2
  exit 1
fi

if [[ ! -s "$renderer" ]]; then
  echo "missing Ayan masterboard renderer: $renderer" >&2
  exit 1
fi

width="$(sips -g pixelWidth "$final_image" | awk '/pixelWidth:/ {print $2}')"
height="$(sips -g pixelHeight "$final_image" | awk '/pixelHeight:/ {print $2}')"

if (( width < 1024 || height < 1536 )); then
  echo "Ayan masterboard is too small: ${width}x${height}" >&2
  exit 1
fi

ffmpeg -v error -i "$final_image" -frames:v 1 -f null -

if rg -Fq 'draw("额间朱砂印\n肩胸暖金云纹\n无铃铛与项圈"' "$renderer"; then
  echo "fixed-mark copy must not cover the cinnabar and gold motifs" >&2
  exit 1
fi

if ! rg -Fq 'draw("阿砚", x: 895' "$renderer"; then
  echo "signature must be positioned to the right of the paw-print safe area" >&2
  exit 1
fi

echo "Ayan masterboard verified: ${width}x${height}"
