#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"

zhixia_source="$project_root/assets/characters/归档/栀夏角色母板高写实CG-v04-完整档案增彩版.png"
ayan_source="$project_root/assets/characters/归档/阿砚角色母板高写实CG-v01-最终版.png"
zhixia_output="$project_root/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-高清2x.png"
ayan_output="$project_root/assets/characters/阿砚角色母板高写实CG-v01-最终版-高清2x.png"
zhixia_seedance="$project_root/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance高清版.png"
ayan_seedance="$project_root/assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance高清版.png"
ayan_upload="$project_root/assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg"
zhixia_upload="$project_root/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg"

for input in "$zhixia_source" "$ayan_source"; do
  if [[ ! -s "$input" ]]; then
    echo "missing source masterboard: $input" >&2
    exit 1
  fi
done

zhixia_hash_before="$(shasum -a 256 "$zhixia_source" | awk '{print $1}')"
ayan_hash_before="$(shasum -a 256 "$ayan_source" | awk '{print $1}')"

upscale() {
  local input="$1"
  local output="$2"

  ffmpeg -y -v error -i "$input" \
    -vf "scale=iw*2:ih*2:flags=lanczos+accurate_rnd+full_chroma_int,unsharp=5:5:0.28:3:3:0" \
    -frames:v 1 -compression_level 6 "$output"
}

upscale "$zhixia_source" "$zhixia_output"
upscale "$ayan_source" "$ayan_output"

seedance_resize() {
  local input="$1"
  local output="$2"

  ffmpeg -y -v error -i "$input" \
    -vf "scale=-2:5984:flags=lanczos+accurate_rnd+full_chroma_int" \
    -frames:v 1 -compression_level 6 "$output"
}

seedance_resize "$zhixia_output" "$zhixia_seedance"
seedance_resize "$ayan_output" "$ayan_seedance"

ffmpeg -y -v error -i "$ayan_seedance" \
  -frames:v 1 -q:v 2 -pix_fmt yuvj444p "$ayan_upload"
ffmpeg -y -v error -i "$zhixia_seedance" \
  -frames:v 1 -q:v 2 -pix_fmt yuvj444p "$zhixia_upload"

zhixia_hash_after="$(shasum -a 256 "$zhixia_source" | awk '{print $1}')"
ayan_hash_after="$(shasum -a 256 "$ayan_source" | awk '{print $1}')"

if [[ "$zhixia_hash_before" != "$zhixia_hash_after" || "$ayan_hash_before" != "$ayan_hash_after" ]]; then
  echo "source masterboard changed during enhancement" >&2
  exit 1
fi

echo "Created: $zhixia_output"
echo "Created: $ayan_output"
echo "Created: $zhixia_seedance"
echo "Created: $ayan_seedance"
echo "Created: $ayan_upload"
echo "Created: $zhixia_upload"
