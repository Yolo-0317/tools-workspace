#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
builder="$project_dir/scripts/build_yunzhongjun_15s_final.sh"
audio_dir="$project_dir/assets/audio/jiuge-yunzhongjun-15s-natural-v02"
cards_dir="$project_dir/assets/subtitles/jiuge-yunzhongjun-15s"
voiced="$project_dir/exports/jiuge-yunzhongjun-15s-voiced-v02.mp4"
final="$project_dir/exports/jiuge-yunzhongjun-15s-subtitled-v02.mp4"

[[ -x "$builder" ]] || { print -u2 "FAIL: missing executable Yunzhongjun builder"; exit 1; }
for name in \
  01-zhixia-zhixia-line-one-a.mp3 \
  02-zhixia-zhixia-line-one-b.mp3 \
  03-zhixia-zhixia-line-two-a.mp3 \
  04-zhixia-zhixia-line-two-b.mp3; do
  [[ -s "$audio_dir/$name" ]] || { print -u2 "FAIL: missing natural voice asset $name"; exit 1; }
done

if rg -q 'atempo|speech_rate=-50|slow-v01|v03\.mp3|v04\.mp3' "$builder"; then
  print -u2 "FAIL: builder still contains rejected voice-speed processing"
  exit 1
fi

"$builder" >/dev/null
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "2" ]]

for output in "$voiced" "$final"; do
  video_json=$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height,r_frame_rate \
    -show_entries format=duration -of json "$output")
  audio_json=$(ffprobe -v error -select_streams a:0 \
    -show_entries stream=codec_name,sample_rate,channels -of json "$output")
  print -r -- "$video_json" | jq -e '
    .streams[0].codec_name == "h264" and
    .streams[0].width == 1080 and .streams[0].height == 1920 and
    .streams[0].r_frame_rate == "24/1" and
    (.format.duration | tonumber) >= 15.0 and (.format.duration | tonumber) <= 15.2
  ' >/dev/null
  print -r -- "$audio_json" | jq -e '
    .streams[0].codec_name == "aac" and
    .streams[0].sample_rate == "48000" and .streams[0].channels == 2
  ' >/dev/null
  ffmpeg -v error -i "$output" -f null -
done

hash_dir=$(mktemp -d /tmp/zhixia-yunzhongjun-audio-hash.XXXXXX)
trap 'rm -rf "$hash_dir"' EXIT
ffmpeg -v error -i "$voiced" -map 0:a:0 -c copy -f adts "$hash_dir/voiced.aac"
ffmpeg -v error -i "$final" -map 0:a:0 -c copy -f adts "$hash_dir/final.aac"
[[ "$(shasum -a 256 "$hash_dir/voiced.aac" | awk '{print $1}')" == "$(shasum -a 256 "$hash_dir/final.aac" | awk '{print $1}')" ]]

print "PASS: Yunzhongjun natural recitation v02 finals are ready"
