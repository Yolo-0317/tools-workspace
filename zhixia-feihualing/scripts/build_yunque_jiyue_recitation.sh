#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_audio="$project_dir/assets/audio/yunque-jiyue-15s-continuous-v01/01-zhixia-full-recitation.mp3"
output="$project_dir/exports/yunque-jiyue-15s-recitation-v01.m4a"

[[ -s "$source_audio" ]] || { print -u2 "Missing source recitation: $source_audio"; exit 1; }
mkdir -p "${output:h}"

ffmpeg -hide_banner -loglevel error -y -i "$source_audio" \
  -filter_complex \
  "[0:a]asplit=4[a1][a2][a3][a4];
   [a1]atrim=start=0.434292:end=2.538208,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=200|200[l1];
   [a2]atrim=start=2.910583:end=5.739500,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=3800|3800[l2];
   [a3]atrim=start=6.547500:end=7.654125,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=8500|8500[l3];
   [a4]atrim=start=8.031083:end=9.122583,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=13550|13550[l4];
   [l1][l2][l3][l4]amix=inputs=4:duration=longest:normalize=0,loudnorm=I=-18:TP=-3:LRA=7,apad,atrim=0:15[out]" \
  -map "[out]" -c:a aac -b:a 192k -ar 48000 -ac 2 -t 15 "$output"

print -r -- "$output"
