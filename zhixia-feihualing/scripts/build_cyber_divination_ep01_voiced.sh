#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
content="$project_dir/episodes/cyber-divination-ep01/assets/video/content-raw-v01.mp4"
audio_dir="$project_dir/assets/audio/cyber-divination-ep01"
output="$project_dir/exports/cyber-divination-ep01-voiced-v03.mp4"

line_01="$audio_dir/01-ayan-ayan-question-v02.mp3"
line_03="$audio_dir/03-zhixia-zhixia-hexagram.mp3"
line_04="$audio_dir/04-zhixia-zhixia-reading.mp3"
line_05="$audio_dir/05-ayan-ayan-hope.mp3"
line_06="$audio_dir/06-zhixia-zhixia-reveal-v02.mp3"
line_07="$audio_dir/07-ayan-ayan-excuse.mp3"

for required in \
  "$content" "$line_01" "$line_03" "$line_04" \
  "$line_05" "$line_06" "$line_07"; do
  test -s "$required"
done

mkdir -p "$(dirname "$output")"

ffmpeg -hide_banner -loglevel error -y \
  -i "$content" \
  -i "$line_01" -i "$line_03" -i "$line_04" \
  -i "$line_05" -i "$line_06" -i "$line_07" \
  -filter_complex "\
    [1:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7[voice01];\
    [2:a]aresample=48000,atempo=1.21,loudnorm=I=-18:TP=-2:LRA=7,adelay=3700:all=1[voice03];\
    [3:a]aresample=48000,atempo=1.13,loudnorm=I=-18:TP=-2:LRA=7,adelay=4900:all=1[voice04];\
    [4:a]aresample=48000,atempo=1.04,loudnorm=I=-18:TP=-2:LRA=7,adelay=8500:all=1[voice05];\
    [5:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=10100:all=1[voice06];\
    [6:a]aresample=48000,loudnorm=I=-18:TP=-2:LRA=7,adelay=12100:all=1[voice07];\
    [voice01][voice03][voice04][voice05][voice06][voice07]amix=inputs=6:duration=longest:dropout_transition=0:normalize=0,alimiter=limit=0.95,apad=pad_dur=15.104,atrim=duration=15.104[aout]" \
  -map 0:v:0 -map "[aout]" -t 15.104 \
  -c:v copy \
  -c:a aac -b:a 160k -ar 48000 -ac 2 \
  -movflags +faststart "$output"

echo "$output"
