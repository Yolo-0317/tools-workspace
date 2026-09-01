#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
script="$project_dir/scripts/prepare_pipaxing_motion_reference.sh"
[[ -x "$script" ]] || { print -u2 -r -- "FAIL: missing executable $script"; exit 1; }

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
input="$work_dir/input.mp4"
output="$work_dir/output.mp4"

ffmpeg -hide_banner -loglevel error \
  -f lavfi -i 'testsrc2=size=592x1280:rate=30:duration=1.2' \
  -f lavfi -i 'sine=frequency=440:sample_rate=44100:duration=1.2' \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$input"

"$script" "$input" "$output" 1

python3 - "$output" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

path = Path(sys.argv[1])
assert path.is_file() and path.stat().st_size > 0, "output video missing"
probe = json.loads(subprocess.check_output([
    "ffprobe", "-v", "error", "-show_entries",
    "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
    "-of", "json", str(path),
], text=True))
streams = probe["streams"]
video = [stream for stream in streams if stream["codec_type"] == "video"]
audio = [stream for stream in streams if stream["codec_type"] == "audio"]
assert len(video) == 1, "expected exactly one video stream"
assert not audio, "motion reference must not contain audio"
assert video[0]["codec_name"] == "h264", video[0]
assert (video[0]["width"], video[0]["height"]) == (720, 1280), video[0]
assert video[0]["r_frame_rate"] == "30/1", video[0]
duration = float(probe["format"]["duration"])
assert 0.95 <= duration <= 1.05, duration
print("PASS: motion reference preprocessing is reproducible")
PY
