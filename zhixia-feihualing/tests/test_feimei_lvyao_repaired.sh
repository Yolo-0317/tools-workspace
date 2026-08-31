#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_feimei_lvyao_repaired.sh"
output="$project_dir/exports/feimei-lvyao-15s-repaired-v01.mp4"
check_dir="$(mktemp -d /tmp/zhixia-feimei-lvyao-test.XXXXXX)"
trap 'rm -rf "$check_dir"' EXIT

[[ -x "$build_script" ]] || {
  print -u2 -r -- "FAIL: missing executable Feimei Lvyao repair build script"
  exit 1
}

for marker in "0.420" "5.450" "11.550" "0.120" "1.050"; do
  rg -qF "$marker" "$build_script" || {
    print -u2 -r -- "FAIL: missing effect timing marker $marker"
    exit 1
  }
done

rg -qF "[bed][sfx]amix=inputs=2:duration=first:dropout_transition=0:normalize=0" "$build_script" || {
  print -u2 -r -- "FAIL: source bed must enter the final mix without normalization"
  exit 1
}

if rg -q '\[bed\].*(volume|loudnorm|sidechaincompress)' "$build_script"; then
  print -u2 -r -- "FAIL: source bed must remain at 0 dB without ducking or loudness processing"
  exit 1
fi

"$build_script" >/dev/null

[[ -s "$output" ]] || {
  print -u2 -r -- "FAIL: repaired master was not created"
  exit 1
}

first_build_hash="$(shasum -a 256 "$output" | awk '{ print $1 }')"

video_json="$(ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -show_entries format=duration -of json "$output")"
audio_json="$(ffprobe -v error -select_streams a:0 \
  -show_entries stream=codec_name,sample_rate,channels -of json "$output")"
source_aigc="$(ffprobe -v error -show_entries format_tags=AIGC \
  -of default=nw=1:nk=1 \
  "$project_dir/episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4")"
output_aigc="$(ffprobe -v error -show_entries format_tags=AIGC \
  -of default=nw=1:nk=1 "$output")"

print -r -- "$video_json" | jq -e '
  .streams[0].codec_name == "h264" and
  .streams[0].width == 1080 and
  .streams[0].height == 1920 and
  .streams[0].r_frame_rate == "24/1" and
  (.format.duration | tonumber) >= 15.05 and
  (.format.duration | tonumber) <= 15.15
' >/dev/null

print -r -- "$audio_json" | jq -e '
  .streams[0].codec_name == "aac" and
  .streams[0].sample_rate == "44100" and
  .streams[0].channels == 2
' >/dev/null

[[ -n "$source_aigc" && "$output_aigc" == "$source_aigc" ]] || {
  print -u2 -r -- "FAIL: repaired master did not preserve the source AIGC metadata"
  exit 1
}

ffmpeg -hide_banner -loglevel error -y -ss 0 -i "$output" \
  -frames:v 1 "$check_dir/opening.png"
ffmpeg -hide_banner -loglevel error -y -ss 14.5 -i "$output" \
  -frames:v 1 "$check_dir/ending.png"

[[ -s "$check_dir/opening.png" && -s "$check_dir/ending.png" ]] || {
  print -u2 -r -- "FAIL: opening or ending inspection frame was not created"
  exit 1
}

ffmpeg -hide_banner -loglevel error -i "$output" -f null -

frame_yavg() {
  local video="$1"
  local timestamp="$2"
  local normalize_filter="$3"
  ffmpeg -hide_banner -loglevel error -ss "$timestamp" -i "$video" \
    -frames:v 1 -vf "${normalize_filter}signalstats,metadata=print:file=-" \
    -f null - 2>/dev/null | awk -F= '/lavfi.signalstats.YAVG/ { print $2; exit }'
}

source_video="$project_dir/episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4"
source_normalize='scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x172525,'

for pulse_time in 0.420 5.450 11.550; do
  source_yavg="$(frame_yavg "$source_video" "$pulse_time" "$source_normalize")"
  repaired_yavg="$(frame_yavg "$output" "$pulse_time" '')"
  awk -v source="$source_yavg" -v repaired="$repaired_yavg" -v time="$pulse_time" '
    BEGIN {
      if ((repaired - source) < 3.0) {
        printf "FAIL: pulse at %s raises average luma by only %.3f; expected at least 3.0\n", time, repaired - source > "/dev/stderr"
        exit 1
      }
    }
  '
done

"$build_script" >/dev/null
second_build_hash="$(shasum -a 256 "$output" | awk '{ print $1 }')"
[[ "$second_build_hash" == "$first_build_hash" ]] || {
  print -u2 -r -- "FAIL: repeated builds are not deterministic"
  exit 1
}

print -r -- "PASS: Feimei Lvyao repaired master meets the delivery contract"
