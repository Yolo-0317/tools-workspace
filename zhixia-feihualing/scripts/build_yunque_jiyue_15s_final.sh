#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/yunque-jiyue-15s/assets/video/content-seedance-v01.mp4"
voice_audio="$project_dir/exports/yunque-jiyue-15s-recitation-v01.m4a"
subtitle_plan="$project_dir/episodes/yunque-jiyue-15s/subtitle-plan.json"
renderer="$project_dir/scripts/render_jiuge_vertical_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/yunque-jiyue-15s"
voiced_output="$project_dir/exports/yunque-jiyue-15s-voiced-v01.mp4"
final_output="$project_dir/exports/yunque-jiyue-15s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-yunque-jiyue-15s.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

for required in "$source_video" "$voice_audio" "$subtitle_plan" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "Missing required input: $required"; exit 1; }
done

duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$source_video")"
mkdir -p "$cards_dir" "$project_dir/exports"
find "$cards_dir" -maxdepth 1 -name '*.png' -type f -delete

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$subtitle_plan" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" -i "$voice_audio" \
  -filter_complex "\
    [0:v]scale=1080:1920:flags=lanczos,fps=24,format=yuv420p[vout];\
    [1:a]aresample=48000,aformat=channel_layouts=stereo,\
      highpass=f=90,equalizer=f=2600:t=q:w=1.0:g=1.8,\
      acompressor=threshold=0.08:ratio=2:attack=10:release=120:makeup=1.25,\
      loudnorm=I=-15:TP=-2:LRA=7[voice];\
    [0:a]aresample=48000,aformat=channel_layouts=stereo[bed];\
    [bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.891251:attack=5:release=80:level=false[aout]" \
  -map "[vout]" -map "[aout]" -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -map_metadata 0 -movflags use_metadata_tags+faststart "$voiced_output"

ffmpeg -hide_banner -loglevel error -y \
  -i "$voiced_output" \
  -loop 1 -framerate 24 -i "$cards_dir/01-modern-beauty.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-modern-color.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-classic-dance.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-classic-cloud.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0.200:d=0.120:alpha=1,fade=t=out:st=2.330:d=0.120:alpha=1[c1];\
    [2:v]format=rgba,fade=t=in:st=3.800:d=0.120:alpha=1,fade=t=out:st=6.660:d=0.120:alpha=1[c2];\
    [3:v]format=rgba,fade=t=in:st=8.500:d=0.120:alpha=1,fade=t=out:st=9.660:d=0.120:alpha=1[c3];\
    [4:v]format=rgba,fade=t=in:st=13.608:d=0.120:alpha=1,fade=t=out:st=14.730:d=0.120:alpha=1[c4];\
    [0:v][c1]overlay=eof_action=pass:enable='between(t,0.200,2.450)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,3.800,6.780)'[v2];\
    [v2][c3]overlay=eof_action=pass:enable='between(t,8.500,9.780)'[v3];\
    [v3][c4]overlay=eof_action=pass:enable='between(t,13.608,14.850)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -map_metadata 0 -movflags use_metadata_tags+faststart "$final_output"

print -r -- "$voiced_output"
print -r -- "$final_output"
