#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_nichang_feitian_15s_final.sh"
download_source="/Users/huan.yu/Downloads/d2a00f67-6708-4440-b225-ccfc270a01c6.mp4"
source_video="$project_dir/episodes/nichang-feitian-15s/assets/video/content-seedance-v01.mp4"
voice_manifest="$project_dir/episodes/nichang-feitian-15s/voice-lines.json"
subtitle_plan="$project_dir/episodes/nichang-feitian-15s/subtitle-plan.json"
audio_dir="$project_dir/assets/audio/nichang-feitian-15s-paced-v01"
cards_dir="$project_dir/assets/subtitles/nichang-feitian-15s"
voiced="$project_dir/exports/nichang-feitian-15s-voiced-v01.mp4"
final="$project_dir/exports/nichang-feitian-15s-subtitled-v01.mp4"

[[ -s "$voice_manifest" ]] || { print -u2 "FAIL: missing Nichang Feitian voice manifest"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 "FAIL: missing Nichang Feitian subtitle plan"; exit 1; }

jq -e '
  .episode == "nichang-feitian-15s" and
  .audio_slug == "nichang-feitian-15s-paced-v01" and
  [.lines[].role] == ["zhixia", "zhixia", "zhixia", "zhixia"] and
  [.lines[].text] == [
    "素手把芙蓉。",
    "虚步蹑太清。",
    "霓裳曳广带。",
    "飘拂升天行。"
  ]
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == [
    "素手把芙蓉",
    "虚步蹑太清",
    "霓裳曳广带",
    "飘拂升天行"
  ] and
  .[0].start == 0.250 and .[0].end == 3.050 and
  .[1].start == 3.500 and .[1].end == 6.350 and
  .[2].start == 6.850 and .[2].end == 9.750 and
  .[3].start == 10.200 and .[3].end == 14.550 and
  .[0].attribution == "唐·李白《古风·其十九》" and
  ([.[1,2,3].attribution // ""] | all(. == "")) and
  .[0].end < .[1].start and .[1].end < .[2].start and .[2].end < .[3].start
' "$subtitle_plan" >/dev/null

[[ -s "$download_source" ]] || { print -u2 "FAIL: missing downloaded Nichang Feitian source video"; exit 1; }
[[ -s "$source_video" ]] || { print -u2 "FAIL: missing archived Nichang Feitian source video"; exit 1; }
[[ "$(shasum -a 256 "$download_source" | awk '{print $1}')" == "$(shasum -a 256 "$source_video" | awk '{print $1}')" ]] || {
  print -u2 "FAIL: archived Nichang Feitian source differs from download"
  exit 1
}

for audio_file in \
  "$audio_dir/01-zhixia-zhixia-line-one.mp3" \
  "$audio_dir/02-zhixia-zhixia-line-two.mp3" \
  "$audio_dir/03-zhixia-zhixia-line-three.mp3" \
  "$audio_dir/04-zhixia-zhixia-line-four.mp3"; do
  [[ -s "$audio_file" ]] || { print -u2 "FAIL: missing voice asset: $audio_file"; exit 1; }
done

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Nichang Feitian build script"; exit 1; }
! rg -q 'sidechaincompress|volume=.*enable|volume=.*between' "$build_script" || {
  print -u2 "FAIL: Nichang Feitian build script must not duck the original soundtrack"
  exit 1
}
rg -q 'amix=inputs=2:duration=first:dropout_transition=0:normalize=0' "$build_script" || {
  print -u2 "FAIL: Nichang Feitian build script must mix the unattenuated bed with voice"
  exit 1
}
rg -q 'alimiter=limit=0.870964:attack=5:release=80:level=false' "$build_script" || {
  print -u2 "FAIL: Nichang Feitian final bus must reserve AAC true-peak headroom"
  exit 1
}

"$build_script" >/dev/null

[[ -s "$voiced" ]] || { print -u2 "FAIL: Nichang Feitian voiced preview was not created"; exit 1; }
[[ -s "$final" ]] || { print -u2 "FAIL: Nichang Feitian subtitled final was not created"; exit 1; }
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four Nichang Feitian subtitle cards"
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

print "PASS: Nichang Feitian four-line recitation HD finals are ready"
