#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_xuexiu_baizhu_15s_final.sh"
download_source="/Users/huan.yu/Downloads/4b3a6780-fa45-4745-ba77-c2dc6343752a.mp4"
source_video="$project_dir/episodes/xuexiu-baizhu-15s/assets/video/content-seedance-v01.mp4"
voice_manifest="$project_dir/episodes/xuexiu-baizhu-15s/voice-lines.json"
subtitle_plan="$project_dir/episodes/xuexiu-baizhu-15s/subtitle-plan.json"
audio_dir="$project_dir/assets/audio/xuexiu-baizhu-15s-paced-v01"
cards_dir="$project_dir/assets/subtitles/xuexiu-baizhu-15s"
voiced="$project_dir/exports/xuexiu-baizhu-15s-voiced-v01.mp4"
final="$project_dir/exports/xuexiu-baizhu-15s-subtitled-v01.mp4"

[[ -s "$voice_manifest" ]] || { print -u2 "FAIL: missing Xuexiu Baizhu voice manifest"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 "FAIL: missing Xuexiu Baizhu subtitle plan"; exit 1; }

jq -e '
  .episode == "xuexiu-baizhu-15s" and
  .audio_slug == "xuexiu-baizhu-15s-paced-v01" and
  [.lines[].role] == ["zhixia", "zhixia", "zhixia", "zhixia"] and
  [.lines[].text] == [
    "吴刀剪彩缝舞衣。",
    "明妆丽服夺春晖。",
    "扬眉转袖若雪飞。",
    "倾城独立世所稀。"
  ]
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == [
    "吴刀剪彩缝舞衣",
    "明妆丽服夺春晖",
    "扬眉转袖若雪飞",
    "倾城独立世所稀"
  ] and
  .[0].start == 0.250 and .[0].end == 3.200 and
  .[1].start == 3.500 and .[1].end == 6.450 and
  .[2].start == 6.750 and .[2].end == 9.850 and
  .[3].start == 10.150 and .[3].end == 14.650 and
  .[0].attribution == "唐·李白《白纻辞三首·其三》" and
  ([.[1,2,3].attribution // ""] | all(. == "")) and
  .[0].end < .[1].start and .[1].end < .[2].start and .[2].end < .[3].start
' "$subtitle_plan" >/dev/null

[[ -s "$download_source" ]] || { print -u2 "FAIL: missing downloaded Xuexiu Baizhu source video"; exit 1; }
[[ -s "$source_video" ]] || { print -u2 "FAIL: missing archived Xuexiu Baizhu source video"; exit 1; }
[[ "$(shasum -a 256 "$download_source" | awk '{print $1}')" == "$(shasum -a 256 "$source_video" | awk '{print $1}')" ]] || {
  print -u2 "FAIL: archived Xuexiu Baizhu source differs from download"
  exit 1
}

for audio_file in \
  "$audio_dir/01-zhixia-zhixia-line-one.mp3" \
  "$audio_dir/02-zhixia-zhixia-line-two.mp3" \
  "$audio_dir/03-zhixia-zhixia-line-three.mp3" \
  "$audio_dir/04-zhixia-zhixia-line-four.mp3"; do
  [[ -s "$audio_file" ]] || { print -u2 "FAIL: missing voice asset: $audio_file"; exit 1; }
done

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Xuexiu Baizhu build script"; exit 1; }
! rg -q 'sidechaincompress|volume=.*enable|volume=.*between' "$build_script" || {
  print -u2 "FAIL: Xuexiu Baizhu build script must not duck the original soundtrack"
  exit 1
}
rg -q 'amix=inputs=2:duration=first:dropout_transition=0:normalize=0' "$build_script" || {
  print -u2 "FAIL: Xuexiu Baizhu build script must mix the unattenuated bed with voice"
  exit 1
}
rg -q 'alimiter=limit=0.870964:attack=5:release=80:level=false' "$build_script" || {
  print -u2 "FAIL: Xuexiu Baizhu final bus must reserve AAC true-peak headroom"
  exit 1
}

"$build_script" >/dev/null

[[ -s "$voiced" ]] || { print -u2 "FAIL: Xuexiu Baizhu voiced preview was not created"; exit 1; }
[[ -s "$final" ]] || { print -u2 "FAIL: Xuexiu Baizhu subtitled final was not created"; exit 1; }
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four Xuexiu Baizhu subtitle cards"
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

hash_dir="$(mktemp -d /tmp/zhixia-xuexiu-audio-hash.XXXXXX)"
trap 'rm -rf "$hash_dir"' EXIT
ffmpeg -v error -i "$voiced" -map 0:a:0 -c copy -f adts "$hash_dir/voiced.aac"
ffmpeg -v error -i "$final" -map 0:a:0 -c copy -f adts "$hash_dir/final.aac"
[[ "$(shasum -a 256 "$hash_dir/voiced.aac" | awk '{print $1}')" == "$(shasum -a 256 "$hash_dir/final.aac" | awk '{print $1}')" ]] || {
  print -u2 "FAIL: voiced and subtitled Xuexiu Baizhu audio streams differ"
  exit 1
}

print "PASS: Xuexiu Baizhu four-line recitation HD finals are ready"
