#!/bin/zsh
set -euo pipefail

PROJECT_ROOT="${0:A:h:h}"
BUILD_SCRIPT="$PROJECT_ROOT/scripts/build_jingtao_subtitled_final.sh"
OUTPUT="$PROJECT_ROOT/exports/jingtao-subtitled-v01.mp4"
CARDS_DIR="$PROJECT_ROOT/assets/subtitles/jingtao"

if [[ ! -x "$BUILD_SCRIPT" ]]; then
  print -u2 "FAIL: missing executable build script: $BUILD_SCRIPT"
  exit 1
fi

"$BUILD_SCRIPT"

for card in \
  01-ayan-dialogue.png \
  02-poem-one.png \
  03-poem-two.png \
  04-poem-three.png; do
  if [[ ! -s "$CARDS_DIR/$card" ]]; then
    print -u2 "FAIL: missing subtitle card: $CARDS_DIR/$card"
    exit 1
  fi
done

if [[ ! -s "$OUTPUT" ]]; then
  print -u2 "FAIL: missing output video: $OUTPUT"
  exit 1
fi

VIDEO_SPEC="$(ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 "$OUTPUT")"
AUDIO_SPEC="$(ffprobe -v error -select_streams a:0 \
  -show_entries stream=codec_name,sample_rate,channels \
  -of default=noprint_wrappers=1 "$OUTPUT")"
DURATION="$(ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "$OUTPUT")"
SUBTITLE_STREAMS="$(ffprobe -v error -select_streams s \
  -show_entries stream=index -of csv=p=0 "$OUTPUT")"

[[ "$VIDEO_SPEC" == *"codec_name=h264"* ]] || { print -u2 "FAIL: video codec is not H.264"; exit 1; }
[[ "$VIDEO_SPEC" == *"width=1080"* ]] || { print -u2 "FAIL: video width is not 1080"; exit 1; }
[[ "$VIDEO_SPEC" == *"height=1920"* ]] || { print -u2 "FAIL: video height is not 1920"; exit 1; }
[[ "$VIDEO_SPEC" == *"r_frame_rate=24/1"* ]] || { print -u2 "FAIL: frame rate is not 24 fps"; exit 1; }
[[ "$AUDIO_SPEC" == *"codec_name=aac"* ]] || { print -u2 "FAIL: audio codec is not AAC"; exit 1; }
[[ "$AUDIO_SPEC" == *"sample_rate=48000"* ]] || { print -u2 "FAIL: audio sample rate is not 48 kHz"; exit 1; }
[[ "$AUDIO_SPEC" == *"channels=2"* ]] || { print -u2 "FAIL: audio is not stereo"; exit 1; }
awk -v duration="$DURATION" 'BEGIN { exit !(duration >= 10.05 && duration <= 10.15) }' || {
  print -u2 "FAIL: duration is outside 10.05-10.15 seconds: $DURATION"
  exit 1
}
[[ -z "$SUBTITLE_STREAMS" ]] || { print -u2 "FAIL: output contains a separate subtitle stream"; exit 1; }

print "PASS: Jingtao subtitled final is ready"
