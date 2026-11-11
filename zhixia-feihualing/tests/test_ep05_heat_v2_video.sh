#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
video="${1:-$project_dir/exports/ep05-heat-v2-subtitled-v01.mp4}"

test -f "$video"
width="$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$video")"
height="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$video")"
fps="$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$video")"
video_codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$video")"
audio_codec="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$video")"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")"

test "$width" = "720"
test "$height" = "1280"
test "$fps" = "24/1"
test "$video_codec" = "h264"
test "$audio_codec" = "aac"
awk -v value="$duration" 'BEGIN { exit !(value >= 19.35 && value <= 19.50) }'
ffmpeg -v error -i "$video" -f null -

# After each poem finishes, the subtitle area must return to the raw picture.
raw="$project_dir/episodes/ep05/assets/video/content-raw-v01.mp4"
for check_time in 3.50 8.50 14.20; do
  ssim="$(ffmpeg -v info -ss "$check_time" -i "$raw" -ss "$check_time" -i "$video" \
    -filter_complex '[0:v]crop=240:520:0:0[a];[1:v]crop=240:520:0:0[b];[a][b]ssim' \
    -frames:v 1 -f null - 2>&1 | sed -n 's/.* All:\([0-9.]*\) .*/\1/p')"
  awk -v value="$ssim" 'BEGIN { exit !(value >= 0.95) }'
done

# The second subtitle must already be visible just after scene two begins.
second_ssim="$(ffmpeg -v info -ss 5.10 -i "$raw" -ss 5.10 -i "$video" \
  -filter_complex '[0:v]crop=240:520:0:0[a];[1:v]crop=240:520:0:0[b];[a][b]ssim' \
  -frames:v 1 -f null - 2>&1 | sed -n 's/.* All:\([0-9.]*\) .*/\1/p')"
awk -v value="$second_ssim" 'BEGIN { exit !(value <= 0.92) }'

echo "PASS: EP05 heat v2 is decodable, 720x1280, 24fps, H.264/AAC, and approximately 19.4 seconds"
