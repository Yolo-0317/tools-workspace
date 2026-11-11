#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/assets/video/content-seedance-xianxia-v01.mp4"
audio_dir="$project_dir/assets/audio/yiwu-yiyuan-qiancheng-01-restart-12s-voice-v01"
subtitle_plan="$project_dir/episodes/yiwu-yiyuan-qiancheng-01-restart-15s/subtitle-plan-12s-v01.json"
renderer="$project_dir/scripts/render_story_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/yiwu-yiyuan-qiancheng-01-restart-12s"
output="$project_dir/exports/yiwu-yiyuan-qiancheng-01-restart-12s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-restart-12s.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

line_one="$audio_dir/01-zhixia-restart.mp3"
line_two="$audio_dir/02-zhixia-blessing.mp3"
line_three="$audio_dir/03-zhixia-poem.mp3"

for required in \
  "$source_video" \
  "$line_one" "$line_two" "$line_three" \
  "$subtitle_plan" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "Missing required input: $required"; exit 1; }
done

source_duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$source_video")"
trim_start="3.000"
output_duration="$(awk -v duration="$source_duration" -v start="$trim_start" 'BEGIN { printf "%.6f", duration - start }')"

mkdir -p "$cards_dir" "$project_dir/exports"
find "$cards_dir" -maxdepth 1 -name '*.png' -type f -delete

export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$subtitle_plan" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$line_one" -i "$line_two" -i "$line_three" \
  -loop 1 -framerate 24 -i "$cards_dir/01-restart.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-blessing.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem.png" \
  -filter_complex "\
    [0:v]trim=start=${trim_start}:duration=${output_duration},setpts=PTS-STARTPTS,\
      scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,\
      crop=1080:1920:(iw-1080)/2:0,\
      hqdn3d=0.6:0.6:1.8:1.8,unsharp=5:5:0.22:3:3:0,\
      fps=24,format=yuv420p[base];\
    [4:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=0.000:d=0.080:alpha=1,fade=t=out:st=1.674:d=0.120:alpha=1[c1];\
    [5:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=2.394:d=0.120:alpha=1,fade=t=out:st=4.697:d=0.120:alpha=1[c2];\
    [6:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=5.617:d=0.120:alpha=1,fade=t=out:st=8.901:d=0.120:alpha=1[c3];\
    [base][c1]overlay=eof_action=pass:enable='between(t,0.000,1.794)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,2.394,4.817)'[v2];\
    [v2][c3]overlay=eof_action=pass:enable='between(t,5.617,9.021)',format=yuv420p[vout];\
    [1:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,\
      aresample=48000,aformat=channel_layouts=stereo[a1];\
    [2:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=2394|2394[a2];\
    [3:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=5617|5617[a3];\
    [a1][a2][a3]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0,\
      highpass=f=90,equalizer=f=2600:t=q:w=1.0:g=1.8,\
      acompressor=threshold=0.08:ratio=2:attack=10:release=120:makeup=1.30,\
      volume=1.08,apad,atrim=0:${output_duration},asplit=2[voice][voice_sc];\
    [0:a]atrim=start=${trim_start}:duration=${output_duration},asetpts=PTS-STARTPTS,\
      aresample=48000,aformat=channel_layouts=stereo,volume=0.90[bed_raw];\
    [bed_raw][voice_sc]sidechaincompress=threshold=0.018:ratio=5:attack=60:release=220:makeup=1[bed];\
    [bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.870964:attack=5:release=80:level=false[aout]" \
  -map "[vout]" -map "[aout]" \
  -t "$output_duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$output"

print -r -- "$output"
