#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_huanghe_voiced_preview.sh"
source_video="$project_dir/episodes/huanghe/assets/video/content-seedance-v01.mp4"
output="$project_dir/exports/huanghe-voiced-v01.mp4"

if [[ ! -x "$build_script" ]]; then
  print -u2 -r -- "FAIL: missing executable build script $build_script"
  exit 1
fi

"$build_script"

if [[ ! -s "$output" ]]; then
  print -u2 -r -- "FAIL: missing voiced preview $output"
  exit 1
fi

video_codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$output")"
video_size="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")"
video_rate="$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=nw=1:nk=1 "$output")"
audio_codec="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$output")"
audio_rate="$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of default=nw=1:nk=1 "$output")"
audio_channels="$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of default=nw=1:nk=1 "$output")"
duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$output")"
subtitle_count="$(ffprobe -v error -select_streams s -show_entries stream=index -of csv=p=0 "$output" | wc -l | tr -d ' ')"

[[ "$video_codec" == "h264" ]] || { print -u2 -- "FAIL: video codec is $video_codec"; exit 1; }
[[ "$video_size" == "496x864" ]] || { print -u2 -- "FAIL: video size is $video_size"; exit 1; }
[[ "$video_rate" == "24/1" ]] || { print -u2 -- "FAIL: frame rate is $video_rate"; exit 1; }
[[ "$audio_codec" == "aac" ]] || { print -u2 -- "FAIL: audio codec is $audio_codec"; exit 1; }
[[ "$audio_rate" == "48000" ]] || { print -u2 -- "FAIL: audio rate is $audio_rate"; exit 1; }
[[ "$audio_channels" == "2" ]] || { print -u2 -- "FAIL: audio channels is $audio_channels"; exit 1; }
awk -v value="$duration" 'BEGIN { exit !(value >= 10.00 && value <= 10.10) }' || {
  print -u2 -- "FAIL: duration is $duration"
  exit 1
}
[[ "$subtitle_count" == "0" ]] || { print -u2 -- "FAIL: subtitle stream count is $subtitle_count"; exit 1; }

source_video_hash="$(ffmpeg -v error -i "$source_video" -map 0:v:0 -c copy -f hash -hash md5 - | sed 's/^MD5=//')"
output_video_hash="$(ffmpeg -v error -i "$output" -map 0:v:0 -c copy -f hash -hash md5 - | sed 's/^MD5=//')"
[[ "$source_video_hash" == "$output_video_hash" ]] || {
  print -u2 -- "FAIL: output video packets differ from the source"
  exit 1
}

max_volume="$(ffmpeg -hide_banner -i "$output" -af volumedetect -f null /dev/null 2>&1 \
  | awk '/max_volume:/ { print $(NF-1); exit }')"
awk -v value="$max_volume" 'BEGIN { exit !(value < 0.0) }' || {
  print -u2 -- "FAIL: mixed audio clips at $max_volume dB"
  exit 1
}

print -r -- "PASS: Huanghe voiced preview is ready"
