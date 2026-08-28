#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/baixue/assets/video/content-seedance-v01.mp4"
subtitle_plan="$project_dir/episodes/baixue/subtitle-plan.json"
builder="$project_dir/scripts/build_baixue_final.sh"
output="$project_dir/exports/baixue-subtitled-v01.mp4"
cards_dir="$project_dir/assets/subtitles/baixue"
audio_dir="$project_dir/assets/audio/baixue"

for required in \
  "$source_video" \
  "$subtitle_plan" \
  "$builder" \
  "$audio_dir/01-ayan-ayan-dialogue.mp3" \
  "$audio_dir/02-zhixia-zhixia-dialogue.mp3" \
  "$audio_dir/03-zhixia-zhixia-poem-one.mp3" \
  "$audio_dir/04-zhixia-zhixia-poem-two.mp3"; do
  if [[ ! -s "$required" ]]; then
    print -u2 -r -- "FAIL: missing required asset $required"
    exit 1
  fi
done

zsh "$builder" >/dev/null

test -s "$output"
for card_id in 01-ayan-dialogue 02-zhixia-dialogue 03-zhixia-poem-one 04-zhixia-poem-two; do
  test -s "$cards_dir/$card_id.png"
done

video_info="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$output")"
audio_info="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of csv=p=0 "$output")"
duration="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$output")"

test "$video_info" = "1080,1920,24/1"
test "$audio_info" = "aac,48000,2"
awk -v value="$duration" 'BEGIN { exit !(value >= 10.09 && value <= 10.11) }'
ffmpeg -v error -i "$output" -f null -

echo "PASS: Baixue final video is 1080x1920, 24fps, 10.1s with mixed stereo audio and four subtitle cards"
