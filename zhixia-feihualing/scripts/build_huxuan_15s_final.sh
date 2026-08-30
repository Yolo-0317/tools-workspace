#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/huxuan-15s/assets/video/content-seedance-v01.mp4"
audio_dir="$project_dir/assets/audio/huxuan-15s-paced-v01"
manifest="$project_dir/episodes/huxuan-15s/subtitle-plan.json"
renderer="$project_dir/scripts/render_story_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/huxuan-15s"
voiced_output="$project_dir/exports/huxuan-15s-voiced-v01.mp4"
final_output="$project_dir/exports/huxuan-15s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-huxuan-15s.XXXXXX)"
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

duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$source_video")"
mkdir -p "$cards_dir" "$project_dir/exports"
find "$cards_dir" -maxdepth 1 -name '*.png' -type f -delete

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$line_one" -i "$line_two" -i "$line_three" -i "$line_four" \
  -filter_complex "\
    [0:v]scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,\
      crop=1080:1920:(iw-1080)/2:0,\
      hqdn3d=0.6:0.6:1.8:1.8,\
      unsharp=5:5:0.22:3:3:0,\
      fps=24,format=yuv420p[vout];\
    [1:a]atrim=start=0.440:end=2.200,asetpts=PTS-STARTPTS,atempo=0.78,\
      afade=t=in:st=0:d=0.035,afade=t=out:st=2.130:d=0.120,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=250|250[a1];\
    [2:a]atrim=start=0.520:end=2.580,asetpts=PTS-STARTPTS,atempo=0.80,\
      afade=t=in:st=0:d=0.035,afade=t=out:st=2.450:d=0.120,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=3650|3650[a2];\
    [3:a]atrim=start=0.340:end=2.160,asetpts=PTS-STARTPTS,atempo=0.75,\
      afade=t=in:st=0:d=0.035,afade=t=out:st=2.300:d=0.120,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=7150|7150[a3];\
    [4:a]atrim=start=0.380:end=2.200,asetpts=PTS-STARTPTS,atempo=0.68,\
      afade=t=in:st=0:d=0.035,afade=t=out:st=2.550:d=0.120,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=10650|10650[a4];\
    [a1][a2][a3][a4]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0,\
      highpass=f=90,equalizer=f=2600:t=q:w=1.0:g=1.8,\
      acompressor=threshold=0.08:ratio=2:attack=10:release=120:makeup=1.35,\
      loudnorm=I=-15:TP=-2:LRA=7,apad,atrim=0:${duration}[voice_mix];\
    [0:a]aresample=48000,aformat=channel_layouts=stereo[bed];\
    [bed][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.870964:attack=5:release=80:level=false[aout]" \
  -map "[vout]" -map "[aout]" \
  -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$voiced_output"

ffmpeg -hide_banner -loglevel error -y \
  -i "$voiced_output" \
  -loop 1 -framerate 24 -i "$cards_dir/01-poem-line-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-poem-line-two.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem-line-three.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-poem-line-four.png" \
  -filter_complex "\
    [1:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=0.250:d=0.120:alpha=1,fade=t=out:st=2.980:d=0.120:alpha=1[c1];\
    [2:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=3.650:d=0.120:alpha=1,fade=t=out:st=6.530:d=0.120:alpha=1[c2];\
    [3:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=7.150:d=0.120:alpha=1,fade=t=out:st=9.980:d=0.120:alpha=1[c3];\
    [4:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=10.650:d=0.120:alpha=1,fade=t=out:st=14.330:d=0.120:alpha=1[c4];\
    [0:v][c1]overlay=eof_action=pass:enable='between(t,0.250,3.100)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,3.650,6.650)'[v2];\
    [v2][c3]overlay=eof_action=pass:enable='between(t,7.150,10.100)'[v3];\
    [v3][c4]overlay=eof_action=pass:enable='between(t,10.650,14.450)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 \
  -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$final_output"

print -r -- "$voiced_output"
print -r -- "$final_output"
