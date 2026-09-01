#!/bin/zsh
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
  print -u2 -r -- "usage: $0 <input-video> <output-video> [target-duration]"
  exit 2
fi

input="$1"
output="$2"
target_duration="${3:-15}"
[[ -f "$input" ]] || { print -u2 -r -- "input video not found: $input"; exit 2; }

source_duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$input")"
setpts_factor="$(python3 - "$source_duration" "$target_duration" <<'PY'
import sys

source = float(sys.argv[1])
target = float(sys.argv[2])
if source <= 0 or target <= 0:
    raise SystemExit("durations must be positive")
print(f"{target / source:.9f}")
PY
)"

mkdir -p "${output:h}"
ffmpeg -hide_banner -loglevel error -y -i "$input" -an \
  -vf "crop=536:1072:0:80,setpts=${setpts_factor}*PTS,scale=640:1280:flags=lanczos,pad=720:1280:40:0:black,fps=30" \
  -t "$target_duration" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -movflags +faststart "$output"
