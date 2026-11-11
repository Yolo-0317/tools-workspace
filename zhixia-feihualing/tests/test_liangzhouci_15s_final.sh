#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_liangzhouci_15s_final.sh"
voice_manifest="$project_dir/episodes/liangzhouci-15s/voice-lines.json"
subtitle_plan="$project_dir/episodes/liangzhouci-15s/subtitle-plan.json"
cards_dir="$project_dir/assets/subtitles/liangzhouci-15s"
output="$project_dir/exports/liangzhouci-15s-subtitled-v01.mp4"

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Liangzhouci build script"; exit 1; }
[[ -s "$voice_manifest" ]] || { print -u2 "FAIL: missing Liangzhouci voice manifest"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 "FAIL: missing Liangzhouci subtitle plan"; exit 1; }
rg -qF "[v3][card4]overlay=x=-80:y=0" "$build_script" || {
  print -u2 "FAIL: fourth subtitle card must shift left to avoid Ayan"
  exit 1
}

jq -e '
  .episode == "liangzhouci-15s" and
  [.lines[].role] == ["zhixia", "zhixia", "zhixia", "zhixia"] and
  [.lines[].text] == [
    "黄河远上白云间。",
    "一片孤城万仞山。",
    "羌笛何须怨杨柳。",
    "春风不度玉门关。"
  ]
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == [
    "黄河远上白云间",
    "一片孤城万仞山",
    "羌笛何须怨杨柳",
    "春风不度玉门关"
  ] and
  .[0].start >= 0 and .[0].start <= 0.5 and
  .[3].end >= 14.0 and .[3].end <= 14.6 and
  .[0].end + 0.7 <= .[1].start and
  .[1].end + 0.7 <= .[2].start and
  .[2].end + 0.7 <= .[3].start and
  .[0].attribution == "唐·王之涣" and
  ([.[1,2,3].attribution // ""] | all(. == ""))
' "$subtitle_plan" >/dev/null

"$build_script" >/dev/null

[[ -s "$output" ]] || { print -u2 "FAIL: final Liangzhouci video was not created"; exit 1; }
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four rendered Liangzhouci subtitle cards"
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
  (.format.duration | tonumber) <= 15.2
' >/dev/null

print -r -- "$audio_json" | jq -e '
  .streams[0].codec_name == "aac" and
  .streams[0].sample_rate == "48000" and
  .streams[0].channels == 2
' >/dev/null

print "PASS: Liangzhouci 15s recitation mix and burned subtitles are ready"
