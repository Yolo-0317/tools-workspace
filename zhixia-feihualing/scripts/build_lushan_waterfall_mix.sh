#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
raw="$project_dir/episodes/lushan/assets/video/content-raw-v01.mp4"
waterfall="$project_dir/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3"
output="$project_dir/exports/lushan-waterfall-mix-preview-v01.mp4"

for required in "$raw" "$waterfall"; do
  test -s "$required"
done
mkdir -p "$(dirname "$output")"

ffmpeg -hide_banner -loglevel error -y \
  -i "$raw" -i "$waterfall" \
  -filter_complex "\
    [0:a]aresample=48000[bed];\
    [1:a]atrim=start=0:end=15.104,asetpts=PTS-STARTPTS,aresample=48000,\
      highpass=f=70,lowpass=f=12000,\
      equalizer=f=2200:t=q:w=1.2:g=-4,\
      loudnorm=I=-18:TP=-3:LRA=5,\
      volume='if(lt(t,4),0.20+0.0625*t,if(lt(t,9.5),0.45+0.063636*(t-4),if(lt(t,9.7),0.80-1.75*(t-9.5),if(lt(t,14.8),0.45,0.45+1.151316*(t-14.8)))))':eval=frame,\
      afade=t=in:st=0:d=0.20[waterfall];\
    [bed][waterfall]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.95:attack=5:release=50[aout]" \
  -map 0:v:0 -map "[aout]" -t 15.104 \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$output"

echo "$output"
