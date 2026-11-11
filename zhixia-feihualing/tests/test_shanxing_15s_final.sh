#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_shanxing_15s_final.sh"
plan="$project_dir/episodes/shanxing-15s/subtitle-plan.json"
cards_dir="$project_dir/assets/subtitles/shanxing-15s"
output="$project_dir/exports/shanxing-15s-subtitled-v01.mp4"

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable build script"; exit 1; }
[[ -s "$plan" ]] || { print -u2 "FAIL: missing subtitle plan"; exit 1; }

jq -e '
  length == 4 and
  [.[].text] == [
    "远上寒山石径斜",
    "白云生处有人家",
    "停车坐爱枫林晚",
    "霜叶红于二月花"
  ] and
  [.[].start] == [0.285, 4.517, 8.569, 12.473] and
  [.[].end] == [2.841, 6.889, 10.795, 14.587]
' "$plan" >/dev/null

"$build_script" >/dev/null

[[ -s "$output" ]] || { print -u2 "FAIL: final video was not created"; exit 1; }
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four rendered subtitle cards"
  exit 1
}

video_json="$(ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -show_entries format=duration -of json "$output")"
audio_json="$(ffprobe -v error -select_streams a:0 \
  -show_entries stream=codec_name,sample_rate,channels -of json "$output")"

print -r -- "$video_json" | jq -e '
  .streams[0].codec_name == "h264" and
  .streams[0].width == 1080 and
  .streams[0].height == 1920 and
  .streams[0].r_frame_rate == "24/1" and
  (.format.duration | tonumber) >= 15.0 and
  (.format.duration | tonumber) <= 15.1
' >/dev/null

print -r -- "$audio_json" | jq -e '
  .streams[0].codec_name == "aac" and
  .streams[0].sample_rate == "48000" and
  .streams[0].channels == 2
' >/dev/null

print "PASS: Shanxing 15s recitation mix and burned subtitles are ready"
