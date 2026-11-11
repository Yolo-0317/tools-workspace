#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
voice_dir="$project_dir/assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01"
line_one="$voice_dir/01-zhixia-modern-blessing.mp3"
line_two="$voice_dir/02-zhixia-middle-wish.mp3"
line_three="$voice_dir/02-zhixia-poem.mp3"
output="$voice_dir/full-recitation-preview-three-lines-10.08s-v03-mono-safe.wav"
build_dir="$(mktemp -d /tmp/zhixia-jiuyue-recitation-v03.XXXXXX)"
temporary_output="$build_dir/recitation.wav"
trap 'rm -rf "$build_dir"' EXIT

for required in "$line_one" "$line_two" "$line_three"; do
  [[ -s "$required" ]] || {
    print -u2 -r -- "Missing narration segment: $required"
    exit 1
  }
done

ffmpeg -hide_banner -loglevel error -y \
  -i "$line_one" \
  -i "$line_two" \
  -i "$line_three" \
  -filter_complex "\
    [0:a]aresample=48000,aformat=sample_fmts=s16:channel_layouts=mono,\
      atrim=0:3.864,asetpts=PTS-STARTPTS[line1];\
    [1:a]aresample=48000,aformat=sample_fmts=s16:channel_layouts=mono,\
      atrim=0:2.280,asetpts=PTS-STARTPTS[line2];\
    [2:a]aresample=48000,aformat=sample_fmts=s16:channel_layouts=mono,\
      atrim=0:3.048,asetpts=PTS-STARTPTS[line3];\
    anullsrc=r=48000:cl=mono:d=0.236[gap1];\
    anullsrc=r=48000:cl=mono:d=0.165[gap2];\
    anullsrc=r=48000:cl=mono:d=0.487[tail];\
    [line1][gap1][line2][gap2][line3][tail]\
      concat=n=6:v=0:a=1,atrim=0:10.080,\
      pan=stereo|c0=c0|c1=c0[out]" \
  -map "[out]" -c:a pcm_s16le -ar 48000 -ac 2 "$temporary_output"

mv "$temporary_output" "$output"
print -r -- "$output"
