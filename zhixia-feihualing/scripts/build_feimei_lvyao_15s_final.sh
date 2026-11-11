#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/feimei-lvyao-15s-repaired-v01.mp4"
audio_dir="$project_dir/assets/audio/feimei-lvyao-15s-paced-v01"
manifest="$project_dir/episodes/feimei-lvyao-15s/subtitle-plan.json"
renderer="$project_dir/scripts/render_story_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/feimei-lvyao-15s"
voiced_output="$project_dir/exports/feimei-lvyao-15s-voiced-v01.mp4"
final_output="$project_dir/exports/feimei-lvyao-15s-subtitled-v01.mp4"
build_dir="$(mktemp -d /tmp/zhixia-feimei-lvyao-15s.XXXXXX)"
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
    [1:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.035,areverse,afade=t=in:st=0:d=0.120,areverse,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=1300|1300[a1];\
    [2:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.035,areverse,afade=t=in:st=0:d=0.120,areverse,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=4100|4100[a2];\
    [3:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.035,areverse,afade=t=in:st=0:d=0.120,areverse,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=7050|7050[a3];\
    [4:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.035,areverse,afade=t=in:st=0:d=0.120,areverse,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=11100|11100[a4];\
    [a1][a2][a3][a4]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0,\
      apad,atrim=0:${duration},highpass=f=90,\
      equalizer=f=2600:t=q:w=1.0:g=1.8,\
      acompressor=threshold=0.08:ratio=2:attack=10:release=120:makeup=1.35,\
      loudnorm=I=-15:TP=-2:LRA=7[voice_mix];\
    [0:a]aresample=48000,aformat=channel_layouts=stereo[bed];\
    [bed][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.891251:attack=5:release=80:level=false[aout]" \
  -map 0:v:0 -map "[aout]" \
  -t "$duration" \
  -c:v copy \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -map_metadata 0 -movflags use_metadata_tags+faststart "$voiced_output"

ffmpeg -hide_banner -loglevel error -y \
  -i "$voiced_output" \
  -loop 1 -framerate 24 -i "$cards_dir/01-poem-line-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-poem-line-two.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem-line-three.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-poem-line-four.png" \
  -filter_complex "\
    [1:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=1.300:d=0.120:alpha=1,fade=t=out:st=3.330:d=0.120:alpha=1[c1];\
    [2:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=4.100:d=0.120:alpha=1,fade=t=out:st=6.130:d=0.120:alpha=1[c2];\
    [3:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=7.050:d=0.120:alpha=1,fade=t=out:st=9.080:d=0.120:alpha=1[c3];\
    [4:v]scale=1080:1920:flags=lanczos,format=rgba,\
      fade=t=in:st=11.100:d=0.120:alpha=1,fade=t=out:st=13.230:d=0.120:alpha=1[c4];\
    [0:v][c1]overlay=eof_action=pass:enable='between(t,1.300,3.450)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,4.100,6.250)'[v2];\
    [v2][c3]overlay=eof_action=pass:enable='between(t,7.050,9.200)'[v3];\
    [v3][c4]overlay=eof_action=pass:enable='between(t,11.100,13.350)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 \
  -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy \
  -map_metadata 0 -movflags use_metadata_tags+faststart "$final_output"

print -r -- "$voiced_output"
print -r -- "$final_output"
