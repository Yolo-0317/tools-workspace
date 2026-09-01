#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/quzhong-huteng-15s/assets/video/content-seedance-v01.mp4"
voice_audio="$project_dir/exports/quzhong-huteng-15s-recitation-fullspan-v04.m4a"
subtitle_plan="$project_dir/episodes/quzhong-huteng-15s/subtitle-plan.json"
build_script="$project_dir/scripts/build_quzhong_huteng_15s_final.sh"
cards_dir="$project_dir/assets/subtitles/quzhong-huteng-15s"
voiced_output="$project_dir/exports/quzhong-huteng-15s-voiced-v01.mp4"
final_output="$project_dir/exports/quzhong-huteng-15s-subtitled-v01.mp4"
check_dir="$(mktemp -d /tmp/zhixia-quzhong-huteng-final-test.XXXXXX)"
trap 'rm -rf "$check_dir"' EXIT

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing accepted source video"; exit 1; }
[[ -s "$voice_audio" ]] || { print -u2 "FAIL: missing approved full-span narration"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 "FAIL: missing subtitle plan"; exit 1; }
[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable build script"; exit 1; }

jq -e '
  length == 4 and
  [.[].kind] == ["modern","modern","poem","poem"] and
  [.[].text] == [
    "有些告别不必说出口",
    "把最后一步跳完就该继续上路",
    "丝桐忽奏一曲终",
    "呜呜画角城头发"
  ] and
  [.[].side] == ["right","left","right","left"] and
  [.[].start] == [0.2,3.9,8.4,12.8] and
  [.[].end] == [2.4,6.65,10.4,14.85] and
  .[2].attribution == "唐·李端《胡腾儿》"
' "$subtitle_plan" >/dev/null

if rg -q 'sidechaincompress|volume=.*between|volume=.*enable' "$build_script"; then
  print -u2 "FAIL: build must not lower or duck the original background music"
  exit 1
fi

if rg -q 'atempo=' "$build_script"; then
  print -u2 "FAIL: build must not time-stretch the narration"
  exit 1
fi

"$build_script" >/dev/null

[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four rendered subtitle cards"
  exit 1
}

source_aigc="$(ffprobe -v error -show_entries format_tags=AIGC -of default=nw=1:nk=1 "$source_video")"

for output in "$voiced_output" "$final_output"; do
  [[ -s "$output" ]] || { print -u2 "FAIL: missing output $output"; exit 1; }
  video_json="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration -of json "$output")"
  audio_json="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of json "$output")"
  output_aigc="$(ffprobe -v error -show_entries format_tags=AIGC -of default=nw=1:nk=1 "$output")"

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
    .streams[0].sample_rate == "48000" and
    .streams[0].channels == 2
  ' >/dev/null

  [[ -n "$source_aigc" && "$output_aigc" == "$source_aigc" ]] || {
    print -u2 "FAIL: output did not preserve source AIGC metadata"
    exit 1
  }

  ffmpeg -hide_banner -loglevel error -i "$output" -f null -
done

ffmpeg -hide_banner -loglevel error -y -i "$voiced_output" -map 0:a:0 -c copy "$check_dir/voiced.aac"
ffmpeg -hide_banner -loglevel error -y -i "$final_output" -map 0:a:0 -c copy "$check_dir/final.aac"
[[ "$(shasum -a 256 "$check_dir/voiced.aac" | awk '{ print $1 }')" == "$(shasum -a 256 "$check_dir/final.aac" | awk '{ print $1 }')" ]] || {
  print -u2 "FAIL: voiced and subtitled audio tracks differ"
  exit 1
}

print "PASS: Quzhong Huteng voiced and subtitled finals are ready"
