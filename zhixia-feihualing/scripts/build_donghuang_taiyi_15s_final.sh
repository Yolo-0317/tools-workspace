#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
source_video="$project_dir/episodes/jiuge-donghuang-taiyi-15s/assets/video/content-raw-v01.mp4"
audio_dir="$project_dir/assets/audio/jiuge-donghuang-taiyi-15s-v01"
manifest="$project_dir/episodes/jiuge-donghuang-taiyi-15s/subtitle-plan.json"
renderer="$project_dir/scripts/render_jiuge_vertical_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/jiuge-donghuang-taiyi-15s"
voiced="$project_dir/exports/jiuge-donghuang-taiyi-15s-voiced-v01.mp4"
final="$project_dir/exports/jiuge-donghuang-taiyi-15s-subtitled-v01.mp4"
build_dir=$(mktemp -d /tmp/zhixia-donghuang-final.XXXXXX)
trap 'rm -rf "$build_dir"' EXIT

line_one="$audio_dir/01-zhixia-zhixia-line-one.mp3"
line_two="$audio_dir/02-zhixia-zhixia-line-two.mp3"
line_three="$audio_dir/03-zhixia-zhixia-line-three.mp3"
line_four="$audio_dir/04-zhixia-zhixia-line-four.mp3"
for required in \
  "$source_video" "$line_one" "$line_two" "$line_three" "$line_four" \
  "$manifest" "$renderer"; do
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
  -i "$line_one" -i "$line_two" -i "$line_three" -i "$line_four" \
  -filter_complex "\
    [0:v]scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,\
      crop=1080:1920:(iw-1080)/2:0,\
      hqdn3d=0.45:0.45:1.35:1.35,\
      unsharp=5:5:0.16:3:3:0,fps=24,format=yuv420p[vout];\
    [1:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,apad,atrim=0:2.650,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=450|450[a1];\
    [2:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,apad,atrim=0:3.200,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=3400|3400[a2];\
    [3:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,apad,atrim=0:3.100,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=7600|7600[a3];\
    [4:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,apad,atrim=0:3.500,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=11000|11000[a4];\
    [a1][a2][a3][a4]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0,\
      highpass=f=90,equalizer=f=2500:t=q:w=1.0:g=1.4,\
      acompressor=threshold=0.08:ratio=2:attack=12:release=150:makeup=1.25,\
      loudnorm=I=-18:TP=-3:LRA=7,apad,atrim=0:${duration},asplit=2[voice_side][voice_mix];\
    [0:a]aresample=48000,aformat=channel_layouts=stereo[bed];\
    [bed][voice_side]sidechaincompress=threshold=0.025:ratio=1.8:attack=70:release=350[ducked];\
    [ducked][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.870964:attack=5:release=80:level=false[aout]" \
  -map "[vout]" -map "[aout]" -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$voiced"

ffmpeg -hide_banner -loglevel error -y \
  -i "$voiced" \
  -loop 1 -framerate 24 -i "$cards_dir/01-poem-line-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-poem-line-two.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem-line-three.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-poem-line-four.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0.450:d=0.120:alpha=1,fade=t=out:st=2.980:d=0.120:alpha=1[c1];\
    [2:v]format=rgba,fade=t=in:st=3.400:d=0.120:alpha=1,fade=t=out:st=6.480:d=0.120:alpha=1[c2];\
    [3:v]format=rgba,fade=t=in:st=7.600:d=0.120:alpha=1,fade=t=out:st=10.580:d=0.120:alpha=1[c3];\
    [4:v]format=rgba,fade=t=in:st=11.000:d=0.120:alpha=1,fade=t=out:st=14.380:d=0.120:alpha=1[c4];\
    [0:v][c1]overlay=eof_action=pass:enable='between(t,0.450,3.100)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,3.400,6.600)'[v2];\
    [v2][c3]overlay=eof_action=pass:enable='between(t,7.600,10.700)'[v3];\
    [v3][c4]overlay=eof_action=pass:enable='between(t,11.000,14.500)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$final"

print -r -- "$voiced"
print -r -- "$final"
