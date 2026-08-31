#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4"

[[ -s "$source_video" ]] || {
  print -u2 -r -- "FAIL: missing Feimei Lvyao source video: $source_video"
  exit 1
}

video_json="$(ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -show_entries format=duration -of json "$source_video")"
audio_json="$(ffprobe -v error -select_streams a:0 \
  -show_entries stream=codec_name,sample_rate,channels -of json "$source_video")"

print -r -- "$video_json" | jq -e '
  .streams[0].codec_name == "h264" and
  .streams[0].width == 496 and
  .streams[0].height == 864 and
  .streams[0].r_frame_rate == "24/1" and
  (.format.duration | tonumber) >= 15.05 and
  (.format.duration | tonumber) <= 15.15
' >/dev/null

print -r -- "$audio_json" | jq -e '
  .streams[0].codec_name == "aac" and
  .streams[0].sample_rate == "44100" and
  .streams[0].channels == 2
' >/dev/null

print -r -- "PASS: Feimei Lvyao source video matches the accepted input"
