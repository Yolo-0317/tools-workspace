#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
source_video="$project_dir/episodes/jiuge-yunzhongjun-15s/assets/video/content-raw-v01.mp4"
audio_dir="$project_dir/assets/audio/jiuge-yunzhongjun-15s-slow-v01"
manifest="$project_dir/episodes/jiuge-yunzhongjun-15s/subtitle-plan.json"
renderer="$project_dir/scripts/render_jiuge_vertical_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/jiuge-yunzhongjun-15s"
voiced="$project_dir/exports/jiuge-yunzhongjun-15s-voiced-v01.mp4"
final="$project_dir/exports/jiuge-yunzhongjun-15s-subtitled-v01.mp4"
build_dir=$(mktemp -d /tmp/zhixia-yunzhongjun-final.XXXXXX)
trap 'rm -rf "$build_dir"' EXIT

line_one="$audio_dir/01-zhixia-zhixia-line-one-v03.mp3"
line_two="$audio_dir/02-zhixia-zhixia-line-two-v04.mp3"
for required in \
  "$source_video" "$line_one" "$line_two" "$manifest" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "missing required input: $required"; exit 1; }
done

duration=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$source_video")
mkdir -p "$cards_dir" "$project_dir/exports"
find "$cards_dir" -maxdepth 1 -name '*.png' -type f -delete
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-cache"
swift "$renderer" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$line_one" -i "$line_two" \
  -filter_complex "\
    [0:v]scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,\
      crop=1080:1920:(iw-1080)/2:0,\
      hqdn3d=0.45:0.45:1.35:1.35,\
      unsharp=5:5:0.16:3:3:0,fps=24,format=yuv420p[vout];\
    [1:a]atrim=start=0.800:end=4.580,asetpts=PTS-STARTPTS,atempo=0.84,\
      afade=t=in:st=0:d=0.05,afade=t=out:st=4.38:d=0.12,apad,atrim=0:4.500,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=1000|1000[a1];\
    [2:a]atrim=start=1.000:end=5.750,asetpts=PTS-STARTPTS,atempo=0.95,\
      afade=t=in:st=0:d=0.05,afade=t=out:st=4.88:d=0.12,apad,atrim=0:5.000,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=7700|7700[a2];\
    [a1][a2]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,\
      highpass=f=90,equalizer=f=2500:t=q:w=1.0:g=1.2,\
      acompressor=threshold=0.08:ratio=2:attack=16:release=180:makeup=1.18,\
      loudnorm=I=-18:TP=-3:LRA=7,apad,atrim=0:${duration},asplit=2[voice_side][voice_mix];\
    [0:a]aresample=48000,aformat=channel_layouts=stereo[bed];\
    [bed][voice_side]sidechaincompress=threshold=0.030:ratio=1.5:attack=90:release=420[ducked];\
    [ducked][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.891251:attack=5:release=100:level=false[aout]" \
  -map "[vout]" -map "[aout]" -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$voiced"

ffmpeg -hide_banner -loglevel error -y \
  -i "$voiced" \
  -loop 1 -framerate 24 -i "$cards_dir/01-poem-line-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-poem-line-two.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=1.000:d=0.120:alpha=1,fade=t=out:st=6.080:d=0.120:alpha=1[c1];\
    [2:v]format=rgba,fade=t=in:st=7.700:d=0.120:alpha=1,fade=t=out:st=13.380:d=0.120:alpha=1[c2];\
    [0:v][c1]overlay=eof_action=pass:enable='between(t,1.000,6.200)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,7.700,13.500)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$final"

print -r -- "$voiced"
print -r -- "$final"
