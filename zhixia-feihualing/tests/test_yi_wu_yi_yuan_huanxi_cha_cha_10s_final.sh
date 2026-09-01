#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
episode_dir="$project_dir/episodes/yiwu-yiyuan-huanxi-cha-cha-10s"
subtitle_plan="$episode_dir/subtitle-plan-final-v01.json"
source_video="$episode_dir/assets/video/content-seedance-v01.mp4"
voice_audio="$project_dir/assets/audio/yiwu-yiyuan-huanxi-cha-cha-10s-voice-v01/01-zhixia-full-recitation-10s-stretched-v02.wav"
builder="$project_dir/scripts/build_yi_wu_yi_yuan_huanxi_cha_cha_10s_final.sh"
voiced="$project_dir/exports/yiwu-yiyuan-huanxi-cha-cha-10s-voiced-v01.mp4"
subtitled="$project_dir/exports/yiwu-yiyuan-huanxi-cha-cha-10s-subtitled-v01.mp4"

fail() {
  print -u2 -r -- "FAIL: $1"
  exit 1
}

[[ -s "$subtitle_plan" ]] || fail "missing heavenly cha-cha subtitle plan"
[[ -s "$source_video" ]] || fail "missing heavenly cha-cha source video"
[[ -s "$voice_audio" ]] || fail "missing heavenly cha-cha 10s voice"

jq -e '
  length == 3 and
  .[0] == {id:"01-blessing",kind:"modern",text:"愿你心有欢喜",start:0.72,end:2.56} and
  .[1] == {id:"02-step",kind:"modern",text:"步步生风",start:2.8,end:4.16} and
  .[2] == {id:"03-poem",kind:"poem",text:"春风得意马蹄疾，一日看尽长安花",attribution:"唐·孟郊《登科后》",start:4.36,end:10.0}
' "$subtitle_plan" >/dev/null || fail "invalid heavenly cha-cha subtitle plan"

[[ -x "$builder" ]] || fail "missing executable heavenly cha-cha final builder"

"$builder" >/dev/null

for output in "$voiced" "$subtitled"; do
  [[ -s "$output" ]] || fail "missing output $(basename "$output")"
  media_json="$(ffprobe -v error -show_entries format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels -of json "$output")"
  print -r -- "$media_json" | jq -e '
    ([.streams[] | select(.codec_type == "video")] | length) == 1 and
    ([.streams[] | select(.codec_type == "audio")] | length) == 1 and
    ([.streams[] | select(.codec_type == "video")][0] |
      .codec_name == "h264" and .width == 1080 and .height == 1920 and .r_frame_rate == "24/1") and
    ([.streams[] | select(.codec_type == "audio")][0] |
      .codec_name == "aac" and .sample_rate == "48000" and .channels == 2) and
    ((.format.duration | tonumber) >= 9.958) and
    ((.format.duration | tonumber) <= 10.042)
  ' >/dev/null || fail "invalid media parameters for $(basename "$output")"
  ffmpeg -v error -i "$output" -f null - || fail "decode failed for $(basename "$output")"
done

build_dir="$(mktemp -d /tmp/zhixia-cha-cha-final-test.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT
ffmpeg -v error -y -i "$voiced" -map 0:a:0 -c copy -f adts "$build_dir/voiced.aac"
ffmpeg -v error -y -i "$subtitled" -map 0:a:0 -c copy -f adts "$build_dir/subtitled.aac"

voiced_hash="$(shasum -a 256 "$build_dir/voiced.aac" | awk '{print $1}')"
subtitled_hash="$(shasum -a 256 "$build_dir/subtitled.aac" | awk '{print $1}')"
[[ "$voiced_hash" == "$subtitled_hash" ]] || fail "voiced and subtitled audio tracks differ"

print -r -- "PASS: heavenly cha-cha 10s voiced and subtitled finals are ready"
