#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
builder="$project_root/scripts/upscale_character_masterboards_2x.sh"
inventory="$project_root/assets/inventory.csv"

zhixia_source="$project_root/assets/characters/归档/栀夏角色母板高写实CG-v04-完整档案增彩版.png"
ayan_source="$project_root/assets/characters/归档/阿砚角色母板高写实CG-v01-最终版.png"
zhixia_output="$project_root/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-高清2x.png"
ayan_output="$project_root/assets/characters/阿砚角色母板高写实CG-v01-最终版-高清2x.png"
zhixia_seedance="$project_root/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance高清版.png"
ayan_seedance="$project_root/assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance高清版.png"
ayan_upload="$project_root/assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg"
zhixia_upload="$project_root/assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg"

expected_zhixia_hash="143dcd26b3c2560f3bd66aa3cc42193f84554368af281cd8c722b2079cacfb74"
expected_ayan_hash="fbf492bce0dde436c83765ebfc8dfe06b9f5abec1562bf0ad5f2ec0f09bdbb66"

if [[ ! -x "$builder" ]]; then
  echo "missing executable masterboard upscale script: $builder" >&2
  exit 1
fi

bash "$builder"

assert_image() {
  local image="$1"
  local expected_width="$2"
  local expected_height="$3"
  local width height

  [[ -s "$image" ]] || { echo "missing enhanced image: $image" >&2; exit 1; }
  width="$(sips -g pixelWidth "$image" | awk '/pixelWidth:/ {print $2}')"
  height="$(sips -g pixelHeight "$image" | awk '/pixelHeight:/ {print $2}')"
  [[ "$width" == "$expected_width" && "$height" == "$expected_height" ]] || {
    echo "wrong enhanced dimensions for $image: ${width}x${height}" >&2
    exit 1
  }
  ffmpeg -v error -i "$image" -frames:v 1 -f null -
}

assert_image "$zhixia_output" 4084 6164
assert_image "$ayan_output" 4092 6148

assert_seedance_image() {
  local image="$1"
  local width height

  [[ -s "$image" ]] || { echo "missing Seedance-safe image: $image" >&2; exit 1; }
  width="$(sips -g pixelWidth "$image" | awk '/pixelWidth:/ {print $2}')"
  height="$(sips -g pixelHeight "$image" | awk '/pixelHeight:/ {print $2}')"
  (( width <= 6000 && height <= 6000 )) || {
    echo "Seedance-safe image exceeds 6000px: ${width}x${height}" >&2
    exit 1
  }
  [[ "$height" == "5984" ]] || {
    echo "unexpected Seedance-safe height: ${width}x${height}" >&2
    exit 1
  }
  ffmpeg -v error -i "$image" -frames:v 1 -f null -
}

assert_seedance_image "$zhixia_seedance"
assert_seedance_image "$ayan_seedance"

[[ -s "$ayan_upload" ]] || { echo "missing compressed Ayan upload image: $ayan_upload" >&2; exit 1; }
ayan_upload_width="$(sips -g pixelWidth "$ayan_upload" | awk '/pixelWidth:/ {print $2}')"
ayan_upload_height="$(sips -g pixelHeight "$ayan_upload" | awk '/pixelHeight:/ {print $2}')"
ayan_upload_bytes="$(stat -f '%z' "$ayan_upload")"
[[ "$ayan_upload_width" == "3982" && "$ayan_upload_height" == "5984" ]] || {
  echo "wrong compressed Ayan dimensions: ${ayan_upload_width}x${ayan_upload_height}" >&2
  exit 1
}
(( ayan_upload_bytes <= 10485760 )) || {
  echo "compressed Ayan upload exceeds 10MiB: $ayan_upload_bytes bytes" >&2
  exit 1
}
ffmpeg -v error -i "$ayan_upload" -frames:v 1 -f null -

[[ -s "$zhixia_upload" ]] || { echo "missing compressed Zhixia upload image: $zhixia_upload" >&2; exit 1; }
zhixia_upload_width="$(sips -g pixelWidth "$zhixia_upload" | awk '/pixelWidth:/ {print $2}')"
zhixia_upload_height="$(sips -g pixelHeight "$zhixia_upload" | awk '/pixelHeight:/ {print $2}')"
zhixia_upload_bytes="$(stat -f '%z' "$zhixia_upload")"
[[ "$zhixia_upload_width" == "3964" && "$zhixia_upload_height" == "5984" ]] || {
  echo "wrong compressed Zhixia dimensions: ${zhixia_upload_width}x${zhixia_upload_height}" >&2
  exit 1
}
(( zhixia_upload_bytes <= 10485760 )) || {
  echo "compressed Zhixia upload exceeds 10MiB: $zhixia_upload_bytes bytes" >&2
  exit 1
}
ffmpeg -v error -i "$zhixia_upload" -frames:v 1 -f null -

actual_zhixia_hash="$(shasum -a 256 "$zhixia_source" | awk '{print $1}')"
actual_ayan_hash="$(shasum -a 256 "$ayan_source" | awk '{print $1}')"
[[ "$actual_zhixia_hash" == "$expected_zhixia_hash" ]] || { echo "Zhixia source image changed" >&2; exit 1; }
[[ "$actual_ayan_hash" == "$expected_ayan_hash" ]] || { echo "Ayan source image changed" >&2; exit 1; }

rg -q '^zhixia-high-realism-cg-masterboard-v04-2x,' "$inventory"
rg -q '^ayan-high-realism-cg-masterboard-v01-2x,' "$inventory"
rg -q '^zhixia-high-realism-cg-masterboard-v04-seedance,' "$inventory"
rg -q '^ayan-high-realism-cg-masterboard-v01-seedance,' "$inventory"
rg -q '^ayan-high-realism-cg-masterboard-v01-upload,' "$inventory"
rg -q '^zhixia-high-realism-cg-masterboard-v04-upload,' "$inventory"

echo "Character masterboards 2x verified: Zhixia 4084x6164; Ayan 4092x6148"
