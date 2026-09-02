#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
episode_dir="$project_dir/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s"
source_video="$episode_dir/assets/video/content-seedance-v01.mp4"
voice_audio="$project_dir/assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01/full-recitation-preview-three-lines-10.08s-v02.wav"
subtitle_plan="$episode_dir/subtitle-plan-jiuyue-haoyun-v01.json"
renderer="$project_dir/scripts/render_jiuyue_haoyun_subtitle_cards.swift"
voiced_output="$project_dir/exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voiced-v01.mp4"
subtitled_output="$project_dir/exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-jiuyue-hot-dance-final.XXXXXX)"
cards_dir="$build_dir/cards"
master="$build_dir/voiced-master.mp4"
trap 'rm -rf "$build_dir"' EXIT

for required in "$source_video" "$voice_audio" "$subtitle_plan" "$renderer"; do
  [[ -s "$required" ]] || {
    print -u2 -r -- "Missing required input: $required"
    exit 1
  }
done

mkdir -p "$cards_dir" "$project_dir/exports"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$subtitle_plan" "$cards_dir"

for card in 01-modern-blessing 02-middle-wish 03-poem; do
  [[ -s "$cards_dir/$card.png" ]] || {
    print -u2 -r -- "Missing subtitle card: $card"
    exit 1
  }
done

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -i "$voice_audio" \
  -filter_complex "\
    [0:v]trim=start=0:duration=10.08,setpts=PTS-STARTPTS,\
      scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,\
      crop=1080:1920:(iw-1080)/2:0,\
      hqdn3d=0.6:0.6:1.8:1.8,unsharp=5:5:0.22:3:3:0,\
      fps=24,format=yuv420p[vout];\
    [1:a]atrim=0:10.08,asetpts=PTS-STARTPTS,\
      aresample=48000,aformat=channel_layouts=stereo,\
      highpass=f=90,equalizer=f=2600:t=q:w=1.0:g=1.8,\
      acompressor=threshold=0.08:ratio=2:attack=10:release=120:makeup=1.30,\
      volume=1.08,asplit=2[voice][voice_sc];\
    [0:a]atrim=0:10.08,asetpts=PTS-STARTPTS,\
      aresample=48000,aformat=channel_layouts=stereo,volume=0.90,\
      apad,atrim=0:10.08,\
      asplit=2[bed_main][tail_source];\
    [tail_source]atrim=start=8.40:end=8.70,asetpts=PTS-STARTPTS,\
      volume=0.55,afade=t=in:st=0:d=0.03,\
      aecho=0.8:0.70:180|360|540:0.50|0.30|0.20,\
      adelay=delays=9400:all=1[tail];\
    [bed_main][tail]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[bed_raw];\
    [bed_raw][voice_sc]sidechaincompress=threshold=0.018:ratio=5:attack=60:release=220:makeup=1[bed];\
    [bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.870964:attack=5:release=80:level=false,\
      apad,atrim=0:10.08[aout]" \
  -map "[vout]" -map "[aout]" -map_metadata 0 \
  -t 10.08 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$master"

cp "$master" "$voiced_output"

ffmpeg -hide_banner -loglevel error -y \
  -i "$master" \
  -loop 1 -framerate 24 -i "$cards_dir/01-modern-blessing.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-middle-wish.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem.png" \
  -filter_complex "\
    [0:v]setpts=PTS-STARTPTS[base];\
    [1:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=0.420:d=0.100:alpha=1,fade=t=out:st=3.580:d=0.120:alpha=1[c1];\
    [2:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=4.570:d=0.100:alpha=1,fade=t=out:st=5.980:d=0.120:alpha=1[c2];\
    [3:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=6.960:d=0.100:alpha=1,fade=t=out:st=9.400:d=0.120:alpha=1[c3];\
    [base][c1]overlay=eof_action=pass:enable='between(t,0.420,3.700)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,4.570,6.100)'[v2];\
    [v2][c3]overlay=eof_action=pass:enable='between(t,6.960,9.520)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -map_metadata 0 \
  -t 10.08 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$subtitled_output"

print -r -- "$voiced_output"
print -r -- "$subtitled_output"
