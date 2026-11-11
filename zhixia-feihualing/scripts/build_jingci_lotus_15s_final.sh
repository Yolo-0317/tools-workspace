#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/jingci-lotus-15s/assets/video/content-seedance-v01.mp4"
audio_dir="$project_dir/assets/audio/jingci-lotus-15s-paced-v01"
manifest="$project_dir/episodes/jingci-lotus-15s/subtitle-plan.json"
renderer="$project_dir/scripts/render_story_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/jingci-lotus-15s"
output="$project_dir/exports/jingci-lotus-15s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-jingci-lotus-15s.XXXXXX)"
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
    [base][card1]overlay=eof_action=pass:enable='between(t,0.279,2.394)'[v1];\
    [v1][card2]overlay=eof_action=pass:enable='between(t,3.857,6.142)'[v2];\
    [v2][card3]overlay=eof_action=pass:enable='between(t,7.511,9.784)'[v3];\
    [v3][card4]overlay=eof_action=pass:enable='between(t,12.064,14.347)',format=yuv420p[vout];\
    [1:a]atrim=start=0.408:end=1.879,asetpts=PTS-STARTPTS,atempo=0.62,aresample=48000,aformat=channel_layouts=stereo,adelay=150|150[a1];\
    [2:a]atrim=start=0.366:end=2.240,asetpts=PTS-STARTPTS,atempo=0.75,aresample=48000,aformat=channel_layouts=stereo,adelay=3750|3750[a2];\
    [3:a]atrim=start=0.356:end=2.152,asetpts=PTS-STARTPTS,atempo=0.72,aresample=48000,aformat=channel_layouts=stereo,adelay=7400|7400[a3];\
    [4:a]atrim=start=0.405:end=2.162,asetpts=PTS-STARTPTS,atempo=0.70,aresample=48000,aformat=channel_layouts=stereo,adelay=11950|11950[a4];\
    [a1][a2][a3][a4]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0,apad,atrim=0:15.093,loudnorm=I=-18:TP=-2:LRA=7[voice];\
    [0:a]aresample=48000,aformat=channel_layouts=stereo,volume='if(between(t,0.150,2.523)+between(t,3.750,6.249)+between(t,7.400,9.894)+between(t,11.950,14.460),0.562341,1)':eval=frame[bed];\
    [bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.891251:level=false[aout]" \
  -map "[vout]" -map "[aout]" \
  -t 15.093 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$output"

print -r -- "$output"
