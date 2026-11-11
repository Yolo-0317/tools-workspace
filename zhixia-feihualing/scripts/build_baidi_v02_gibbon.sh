#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
base="$project_dir/exports/baidi-subtitled-v01.mp4"
gibbon="$project_dir/assets/audio/sfx/baidi/hylobates-syndactylus-calling-3588.ogg"
output="$project_dir/exports/baidi-subtitled-v03-gibbon-louder.mp4"

test -s "$base"
test -s "$gibbon"

ffmpeg -hide_banner -loglevel error -y \
  -i "$base" -i "$gibbon" \
  -filter_complex "\
    [0:a]aresample=48000[base];\
    [1:a]atrim=start=0:end=4.6,asetpts=PTS-STARTPTS,aresample=48000,highpass=f=350,lowpass=f=4500,volume=0.22,aecho=0.8:0.5:380|760:0.28|0.14,adelay=9900:all=1[gibbon];\
    [base][gibbon]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" -t 15.104 \
  -c:v copy -c:a aac -b:a 160k -ar 48000 -ac 2 -movflags +faststart "$output"

echo "$output"
