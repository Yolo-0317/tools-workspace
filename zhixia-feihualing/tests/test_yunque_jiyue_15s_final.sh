#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/yunque-jiyue-15s/assets/video/content-seedance-v01.mp4"
voice_audio="$project_dir/exports/yunque-jiyue-15s-recitation-v01.m4a"
subtitle_plan="$project_dir/episodes/yunque-jiyue-15s/subtitle-plan.json"
build_script="$project_dir/scripts/build_yunque_jiyue_15s_final.sh"
cards_dir="$project_dir/assets/subtitles/yunque-jiyue-15s"
voiced_output="$project_dir/exports/yunque-jiyue-15s-voiced-v01.mp4"
final_output="$project_dir/exports/yunque-jiyue-15s-subtitled-v01.mp4"
check_dir="$(mktemp -d /tmp/zhixia-yunque-jiyue-final-test.XXXXXX)"
trap 'rm -rf "$check_dir"' EXIT

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing accepted source video"; exit 1; }
[[ -s "$voice_audio" ]] || { print -u2 "FAIL: missing approved 15-second narration"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 "FAIL: missing subtitle plan"; exit 1; }

jq -e '
  length == 4 and
  [.[].kind] == ["modern","modern","poem","poem"] and
  [.[].text] == [
    "有些美好并没有真的离开",
    "被人记起时它就会重新有颜色",
    "只愁歌舞散",
    "化作彩云飞"
  ] and
  [.[].side] == ["right","left","right","left"] and
  [.[].start] == [0.2,3.8,8.5,13.608] and
  [.[].end] == [2.45,6.78,9.78,14.85] and
  .[2].attribution == "唐·李白《宫中行乐词》"
' "$subtitle_plan" >/dev/null

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable final builder"; exit 1; }
"$build_script" >/dev/null

[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four rendered subtitle cards"
  exit 1
}

source_aigc="$(ffprobe -v error -show_entries format_tags=AIGC -of default=nw=1:nk=1 "$source_video")"
for output in "$voiced_output" "$final_output"; do
  [[ -s "$output" ]] || { print -u2 "FAIL: missing output $output"; exit 1; }
  ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration -of json "$output" | jq -e '
    .streams[0].codec_name == "h264" and
    .streams[0].width == 1080 and
    .streams[0].height == 1920 and
    .streams[0].r_frame_rate == "24/1" and
    (.format.duration | tonumber) >= 15.09 and
    (.format.duration | tonumber) <= 15.12
  ' >/dev/null
  ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of json "$output" | jq -e '
    .streams[0].codec_name == "aac" and
    .streams[0].sample_rate == "48000" and
    .streams[0].channels == 2
  ' >/dev/null
  [[ "$(ffprobe -v error -show_entries format_tags=AIGC -of default=nw=1:nk=1 "$output")" == "$source_aigc" ]] || {
    print -u2 "FAIL: output did not preserve source AIGC metadata"
    exit 1
  }
  ffmpeg -v error -i "$output" -f null -
done

ffmpeg -hide_banner -loglevel error -y -i "$voiced_output" -map 0:a:0 -c copy "$check_dir/voiced.aac"
ffmpeg -hide_banner -loglevel error -y -i "$final_output" -map 0:a:0 -c copy "$check_dir/final.aac"
[[ "$(shasum -a 256 "$check_dir/voiced.aac" | awk '{print $1}')" == "$(shasum -a 256 "$check_dir/final.aac" | awk '{print $1}')" ]] || {
  print -u2 "FAIL: voiced and subtitled audio tracks differ"
  exit 1
}

print "PASS: 云阙伎乐 voiced and subtitled finals are ready"
