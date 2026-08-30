#!/bin/zsh
set -euo pipefail

if [[ "$#" -ne 4 ]]; then
  print -u2 -r -- "Usage: $0 <bed-input> <voice-input> <duration-seconds> <output-wav>"
  exit 2
fi

bed_input="$1"
voice_input="$2"
duration="$3"
output="$4"

[[ -s "$bed_input" ]] || { print -u2 -r -- "Missing bed input: $bed_input"; exit 1; }
[[ -s "$voice_input" ]] || { print -u2 -r -- "Missing voice input: $voice_input"; exit 1; }

mkdir -p "${output:h}"

ffmpeg -hide_banner -loglevel error -y \
  -i "$bed_input" \
  -i "$voice_input" \
  -filter_complex "\
    [0:a]aresample=48000,aformat=channel_layouts=stereo,volume=1.0[bed];\
    [1:a]aresample=48000,aformat=channel_layouts=stereo[voice];\
    [bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.881049:attack=5:release=50:level=0:latency=1[aout]" \
  -map "[aout]" \
  -t "$duration" \
  -c:a pcm_s24le -ar 48000 -ac 2 \
  "$output"
