#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
episode_dir="$project_dir/episodes/yiwu-yiyuan-huanxi-cha-cha-10s"
source_video="$episode_dir/assets/video/content-seedance-v01.mp4"
voice_audio="$project_dir/assets/audio/yiwu-yiyuan-huanxi-cha-cha-10s-voice-v01/01-zhixia-full-recitation-10s-stretched-v02.wav"
subtitle_plan="$episode_dir/subtitle-plan-final-v01.json"
renderer="$project_dir/scripts/render_story_subtitle_cards.swift"
voiced_output="$project_dir/exports/yiwu-yiyuan-huanxi-cha-cha-10s-voiced-v01.mp4"
subtitled_output="$project_dir/exports/yiwu-yiyuan-huanxi-cha-cha-10s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-cha-cha-10s-final.XXXXXX)"
cards_dir="$build_dir/cards"
master="$build_dir/voiced-master.mp4"
trap 'rm -rf "$build_dir"' EXIT

for required in "$source_video" "$voice_audio" "$subtitle_plan" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "Missing required input: $required"; exit 1; }
done

mkdir -p "$cards_dir" "$project_dir/exports"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$subtitle_plan" "$cards_dir"

for card in 01-blessing 02-step 03-poem; do
  [[ -s "$cards_dir/$card.png" ]] || { print -u2 -r -- "Missing subtitle card: $card"; exit 1; }
done

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$voice_audio" \
  -filter_complex "\
    [0:v]trim=start=0:duration=10,setpts=PTS-STARTPTS,\
      scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,\
      crop=1080:1920:(iw-1080)/2:0,\
      hqdn3d=0.6:0.6:1.8:1.8,unsharp=5:5:0.22:3:3:0,\
      fps=24,format=yuv420p[vout];\
    [1:a]atrim=0:10,asetpts=PTS-STARTPTS,\
      aresample=48000,aformat=channel_layouts=stereo,\
      highpass=f=90,equalizer=f=2600:t=q:w=1.0:g=1.8,\
      acompressor=threshold=0.08:ratio=2:attack=10:release=120:makeup=1.30,\
      volume=1.08,asplit=2[voice][voice_sc];\
    [0:a]atrim=0:10,asetpts=PTS-STARTPTS,\
      aresample=48000,aformat=channel_layouts=stereo,volume=0.90[bed_raw];\
    [bed_raw][voice_sc]sidechaincompress=threshold=0.018:ratio=5:attack=60:release=220:makeup=1[bed];\
    [bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.870964:attack=5:release=80:level=false,\
      apad,atrim=0:10[aout]" \
  -map "[vout]" -map "[aout]" -map_metadata 0 \
  -t 10 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$master"

cp "$master" "$voiced_output"

ffmpeg -hide_banner -loglevel error -y \
  -i "$master" \
  -loop 1 -framerate 24 -i "$cards_dir/01-blessing.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-step.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem.png" \
  -filter_complex "\
    [0:v]setpts=PTS-STARTPTS[base];\
    [1:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=0.720:d=0.080:alpha=1,fade=t=out:st=2.440:d=0.120:alpha=1[c1];\
    [2:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=2.800:d=0.100:alpha=1,fade=t=out:st=4.040:d=0.120:alpha=1[c2];\
    [3:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=4.360:d=0.120:alpha=1,fade=t=out:st=9.880:d=0.120:alpha=1[c3];\
    [base][c1]overlay=eof_action=pass:enable='between(t,0.720,2.560)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,2.800,4.160)'[v2];\
    [v2][c3]overlay=eof_action=pass:enable='between(t,4.360,10.000)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -map_metadata 0 \
  -t 10 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$subtitled_output"

print -r -- "$voiced_output"
print -r -- "$subtitled_output"
