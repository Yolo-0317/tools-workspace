#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/wangtianmenshan-15s/assets/video/content-seedance-v01.mp4"
audio_dir="$project_dir/assets/audio/wangtianmenshan-15s-paced-v01"
manifest="$project_dir/episodes/wangtianmenshan-15s/subtitles-wangtianmenshan-15s.json"
renderer="$project_dir/scripts/render_story_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/wangtianmenshan-15s"
output="$project_dir/exports/wangtianmenshan-15s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-wangtianmenshan-15s.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT
line_one="$audio_dir/01-zhixia-zhixia-line-one.mp3"
line_two="$audio_dir/02-zhixia-zhixia-line-two.mp3"
line_three="$audio_dir/03-zhixia-zhixia-line-three.mp3"
line_four="$audio_dir/04-zhixia-zhixia-line-four.mp3"
for required in "$source_video" "$line_one" "$line_two" "$line_three" "$line_four" "$manifest" "$renderer"; do [[ -s "$required" ]] || { print -u2 -r -- "Missing required input: $required"; exit 1; }; done
mkdir -p "$cards_dir" "$project_dir/exports"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache" SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$manifest" "$cards_dir"
ffmpeg -hide_banner -loglevel error -y -i "$source_video" -i "$line_one" -i "$line_two" -i "$line_three" -i "$line_four" -loop 1 -framerate 24 -i "$cards_dir/01-poem-line-one.png" -loop 1 -framerate 24 -i "$cards_dir/02-poem-line-two.png" -loop 1 -framerate 24 -i "$cards_dir/03-poem-line-three.png" -loop 1 -framerate 24 -i "$cards_dir/04-poem-line-four.png" -filter_complex "[0:v]scale=1080:1920:flags=lanczos,fps=24,format=yuv420p[base];[5:v]scale=1080:1920[c1];[6:v]scale=1080:1920[c2];[7:v]scale=1080:1920[c3];[8:v]scale=1080:1920[c4];[base][c1]overlay=eof_action=pass:enable='between(t,0.250,2.635)'[v1];[v1][c2]overlay=eof_action=pass:enable='between(t,3.500,5.698)'[v2];[v2][c3]overlay=eof_action=pass:enable='between(t,6.800,9.198)'[v3];[v3][c4]overlay=eof_action=pass:enable='between(t,11.750,14.199)',format=yuv420p[vout];[1:a]atrim=start=0.506042:end=2.294708,asetpts=PTS-STARTPTS,atempo=0.75,aresample=48000,aformat=channel_layouts=stereo,adelay=250|250[a1];[2:a]atrim=start=0.458875:end=2.063208,asetpts=PTS-STARTPTS,atempo=0.73,aresample=48000,aformat=channel_layouts=stereo,adelay=3500|3500[a2];[3:a]atrim=start=0.440542:end=2.239083,asetpts=PTS-STARTPTS,atempo=0.75,aresample=48000,aformat=channel_layouts=stereo,adelay=6800|6800[a3];[4:a]atrim=start=0.466542:end=2.230042,asetpts=PTS-STARTPTS,atempo=0.72,aresample=48000,aformat=channel_layouts=stereo,adelay=11750|11750[a4];[a1][a2][a3][a4]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0,apad,atrim=0:15.093,loudnorm=I=-18:TP=-2:LRA=7,asplit=2[voice][voice_sc];[0:a]aresample=48000,aformat=channel_layouts=stereo[bed_raw];[bed_raw][voice_sc]sidechaincompress=threshold=0.02:ratio=4:attack=80:release=180:makeup=1[bed];[bed][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.891251:level=false[aout]" -map "[vout]" -map "[aout]" -t 15.093 -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart "$output"
print -r -- "$output"
