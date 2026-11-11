#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/shanxing-15s/assets/video/content-seedance-v01.mp4"
audio_dir="$project_dir/assets/audio/shanxing-15s-paced-v01"
manifest="$project_dir/episodes/shanxing-15s/subtitle-plan.json"
renderer="$project_dir/scripts/render_story_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/shanxing-15s"
output="$project_dir/exports/shanxing-15s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-shanxing-15s.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

line_one="$audio_dir/01-zhixia-zhixia-line-one.mp3"
line_two="$audio_dir/02-zhixia-zhixia-line-two.mp3"
line_three="$audio_dir/03-zhixia-zhixia-line-three.mp3"
line_four="$audio_dir/04-zhixia-zhixia-line-four.mp3"

for required in \
  "$source_video" \
  "$line_one" "$line_two" "$line_three" "$line_four" \
  "$manifest" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "Missing required input: $required"; exit 1; }
done

mkdir -p "$cards_dir" "$project_dir/exports"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$line_one" -i "$line_two" -i "$line_three" -i "$line_four" \
  -loop 1 -framerate 24 -i "$cards_dir/01-poem-line-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-poem-line-two.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem-line-three.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-poem-line-four.png" \
  -filter_complex "\
    [0:v]scale=1080:1920:flags=lanczos,fps=24,format=yuv420p[base];\
    [5:v]scale=1080:1920:flags=lanczos[card1];\
    [6:v]scale=1080:1920:flags=lanczos[card2];\
    [7:v]scale=1080:1920:flags=lanczos[card3];\
    [8:v]scale=1080:1920:flags=lanczos[card4];\
    [base][card1]overlay=eof_action=pass:enable='between(t,0.285,2.841)'[v1];\
    [v1][card2]overlay=eof_action=pass:enable='between(t,4.517,6.889)'[v2];\
    [v2][card3]overlay=eof_action=pass:enable='between(t,8.569,10.795)'[v3];\
    [v3][card4]overlay=eof_action=pass:enable='between(t,12.473,14.587)',format=yuv420p[vout];\
    anullsrc=r=48000:cl=stereo:d=0.15[lead];\
    anullsrc=r=48000:cl=stereo:d=1.42[g1];\
    anullsrc=r=48000:cl=stereo:d=1.42[g2];\
    anullsrc=r=48000:cl=stereo:d=1.42[g3];\
    [1:a]atrim=start=0.628:end=2.619,asetpts=PTS-STARTPTS,atempo=0.7,aresample=48000,aformat=channel_layouts=stereo[a1];\
    [2:a]atrim=start=0.349:end=2.196,asetpts=PTS-STARTPTS,atempo=0.7,aresample=48000,aformat=channel_layouts=stereo[a2];\
    [3:a]atrim=start=0.390:end=2.147,asetpts=PTS-STARTPTS,atempo=0.7,aresample=48000,aformat=channel_layouts=stereo[a3];\
    [4:a]atrim=start=0.543:end=2.217,asetpts=PTS-STARTPTS,atempo=0.7,aresample=48000,aformat=channel_layouts=stereo[a4];\
    [lead][a1][g1][a2][g2][a3][g3][a4]concat=n=8:v=0:a=1,apad,atrim=0:15,loudnorm=I=-18:TP=-2:LRA=7[voice];\
    [0:a]aresample=48000,aformat=channel_layouts=stereo,volume='if(between(t,0.285,2.841)+between(t,4.517,6.889)+between(t,8.569,10.795)+between(t,12.473,14.587),0.562341,1)':eval=frame[bed];\
    [bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.891251:level=false[aout]" \
  -map "[vout]" -map "[aout]" \
  -t 15.069 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$output"

print -r -- "$output"
