#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_gucuizhezhi_15s_final.sh"
source_video="$project_dir/episodes/gucuizhezhi-15s/assets/video/content-seedance-v01.mp4"
voice_manifest="$project_dir/episodes/gucuizhezhi-15s/voice-lines.json"
subtitle_plan="$project_dir/episodes/gucuizhezhi-15s/subtitle-plan.json"
audio_dir="$project_dir/assets/audio/gucuizhezhi-15s-paced-v01"
cards_dir="$project_dir/assets/subtitles/gucuizhezhi-15s"
voiced="$project_dir/exports/gucuizhezhi-15s-voiced-v01.mp4"
final="$project_dir/exports/gucuizhezhi-15s-subtitled-v01.mp4"

[[ -s "$voice_manifest" ]] || { print -u2 "FAIL: missing Gucuizhezhi voice manifest"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 "FAIL: missing Gucuizhezhi subtitle plan"; exit 1; }

jq -e '
  .episode == "gucuizhezhi-15s" and
  .audio_slug == "gucuizhezhi-15s-paced-v01" and
  [.lines[].role] == ["zhixia", "zhixia", "zhixia", "zhixia"] and
  [.lines[].text] == [
    "平铺一合锦筵开。",
    "连击三声画鼓催。",
    "红蜡烛移桃叶起。",
    "紫罗衫动柘枝来。"
  ]
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == [
    "平铺一合锦筵开",
    "连击三声画鼓催",
    "红蜡烛移桃叶起",
    "紫罗衫动柘枝来"
  ] and
  .[0].start == 0.250 and .[0].end == 3.050 and
  .[1].start == 3.650 and .[1].end == 6.450 and
  .[2].start == 7.050 and .[2].end == 9.950 and
  .[3].start == 10.600 and .[3].end == 14.300 and
  .[0].attribution == "唐·白居易《柘枝妓》" and
  ([.[1,2,3].attribution // ""] | all(. == "")) and
  .[0].end < .[1].start and .[1].end < .[2].start and .[2].end < .[3].start
' "$subtitle_plan" >/dev/null

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Gucuizhezhi build script"; exit 1; }
[[ -s "$source_video" ]] || { print -u2 "FAIL: missing archived Gucuizhezhi source video"; exit 1; }

for audio_file in \
  "$audio_dir/01-zhixia-zhixia-line-one.mp3" \
  "$audio_dir/02-zhixia-zhixia-line-two.mp3" \
  "$audio_dir/03-zhixia-zhixia-line-three.mp3" \
  "$audio_dir/04-zhixia-zhixia-line-four.mp3"; do
  [[ -s "$audio_file" ]] || { print -u2 "FAIL: missing voice asset: $audio_file"; exit 1; }
done

"$build_script" >/dev/null

[[ -s "$voiced" ]] || { print -u2 "FAIL: voiced preview was not created"; exit 1; }
[[ -s "$final" ]] || { print -u2 "FAIL: subtitled final was not created"; exit 1; }
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four Gucuizhezhi subtitle cards"
  exit 1
}

for output in "$voiced" "$final"; do
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

  ffmpeg -v error -i "$output" -f null -
done

print "PASS: Gucuizhezhi four-line recitation HD finals are ready"
