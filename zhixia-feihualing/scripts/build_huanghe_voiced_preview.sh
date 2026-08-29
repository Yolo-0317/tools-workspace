#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/huanghe/assets/video/content-seedance-v01.mp4"
ayan_voice="$project_dir/assets/audio/huanghe/01-ayan-ayan-dialogue.mp3"
zhixia_voice="$project_dir/assets/audio/huanghe/02-zhixia-zhixia-poem.mp3"
output="$project_dir/exports/huanghe-voiced-v01.mp4"

for input in "$source_video" "$ayan_voice" "$zhixia_voice"; do
  if [[ ! -s "$input" ]]; then
    print -u2 -r -- "Missing required input: $input"
    exit 1
  fi
done

mkdir -p "$project_dir/exports"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$ayan_voice" \
  -i "$zhixia_voice" \
  -filter_complex "\
    [0:a]aresample=48000,aformat=channel_layouts=stereo,volume='if(between(t,0,3.456)+between(t,3.800,8.648),0.562341,1)':eval=frame[bed];\
    [1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-18:TP=-2:LRA=7[ayan];\
    [2:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-18:TP=-2:LRA=7,adelay=3800|3800[zhixia];\
    [bed][ayan][zhixia]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.891251:level=false[aout]" \
  -map 0:v:0 -map "[aout]" \
  -t 10.054 \
  -c:v copy \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart \
  "$output"

print -r -- "$output"
