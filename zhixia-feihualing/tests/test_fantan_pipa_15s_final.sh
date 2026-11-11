#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_fantan_pipa_15s_final.sh"
mix_script="$project_dir/scripts/mix_audio_no_duck.sh"
source_video="$project_dir/episodes/fantan-pipa-15s/assets/video/content-seedance-no-prop-v02.mp4"
voice_manifest="$project_dir/episodes/fantan-pipa-15s/voice-lines.json"
subtitle_plan="$project_dir/episodes/fantan-pipa-15s/subtitle-plan.json"
audio_dir="$project_dir/assets/audio/fantan-pipa-15s-paced-v01"
cards_dir="$project_dir/assets/subtitles/fantan-pipa-15s"
voiced="$project_dir/exports/fantan-pipa-15s-voiced-v01.mp4"
final="$project_dir/exports/fantan-pipa-15s-subtitled-v01.mp4"
test_dir="$(mktemp -d /tmp/zhixia-fantan-pipa-test.XXXXXX)"
trap 'rm -rf "$test_dir"' EXIT

[[ -s "$voice_manifest" ]] || { print -u2 "FAIL: missing Fantan Pipa voice manifest"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 "FAIL: missing Fantan Pipa subtitle plan"; exit 1; }

jq -e '
  .episode == "fantan-pipa-15s" and
  .audio_slug == "fantan-pipa-15s-paced-v01" and
  [.lines[].role] == ["zhixia", "zhixia", "zhixia", "zhixia"] and
  [.lines[].text] == [
    "琵琶起舞换新声。",
    "总是关山旧别情。",
    "撩乱边愁听不尽。",
    "高高秋月照长城。"
  ]
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == [
    "琵琶起舞换新声",
    "总是关山旧别情",
    "撩乱边愁听不尽",
    "高高秋月照长城"
  ] and
  .[0].start == 0.250 and .[0].end == 3.100 and
  .[1].start == 3.550 and .[1].end == 6.400 and
  .[2].start == 6.900 and .[2].end == 9.800 and
  .[3].start == 10.350 and .[3].end == 14.400 and
  .[0].attribution == "唐·王昌龄《从军行七首·其二》" and
  ([.[1,2,3].attribution // ""] | all(. == "")) and
  .[0].end < .[1].start and .[1].end < .[2].start and .[2].end < .[3].start
' "$subtitle_plan" >/dev/null

[[ -x "$mix_script" ]] || { print -u2 "FAIL: missing executable no-duck audio mixer"; exit 1; }

# Regression behavior: a voice burst must not reduce the bed tone while it is present.
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=2" \
  -af "volume=0.05" -ac 2 "$test_dir/bed.wav"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "sine=frequency=880:sample_rate=48000:duration=0.8" \
  -af "volume=0.02,adelay=600|600,apad,atrim=0:2" -ac 2 "$test_dir/voice.wav"
"$mix_script" "$test_dir/bed.wav" "$test_dir/voice.wav" 2 "$test_dir/mixed.wav"

measure_rms() {
  local start="$1"
  ffmpeg -hide_banner -nostats -ss "$start" -t 0.3 -i "$test_dir/mixed.wav" \
    -af "bandpass=f=440:w=20,astats=metadata=0:reset=0" -f null - 2>&1 |
    awk -F': ' '/RMS level dB/ { value=$2 } END { print value }'
}

bed_before="$(measure_rms 0.1)"
bed_during="$(measure_rms 0.8)"
awk -v before="$bed_before" -v during="$bed_during" 'BEGIN {
  delta = before - during;
  if (delta < 0) delta = -delta;
  if (delta > 0.25) {
    printf "FAIL: background bed changed by %.3f dB during narration\n", delta > "/dev/stderr";
    exit 1;
  }
}'

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Fantan Pipa build script"; exit 1; }
[[ -s "$source_video" ]] || { print -u2 "FAIL: missing archived Fantan Pipa source video"; exit 1; }

for audio_file in \
  "$audio_dir/01-zhixia-zhixia-line-one.mp3" \
  "$audio_dir/02-zhixia-zhixia-line-two.mp3" \
  "$audio_dir/03-zhixia-zhixia-line-three.mp3" \
  "$audio_dir/04-zhixia-zhixia-line-four.mp3"; do
  [[ -s "$audio_file" ]] || { print -u2 "FAIL: missing voice asset: $audio_file"; exit 1; }
done

"$build_script" >/dev/null

[[ -s "$voiced" ]] || { print -u2 "FAIL: voiced preview was not created"; exit 1; }
[[ -s "$final" ]] || { print -u2 "FAIL: subtitled final was not created"; exit 1; }
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four Fantan Pipa subtitle cards"
  exit 1
}

for output in "$voiced" "$final"; do
  video_json="$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height,r_frame_rate \
    -show_entries format=duration -of json "$output")"
  audio_json="$(ffprobe -v error -select_streams a:0 \
    -show_entries stream=codec_name,sample_rate,channels -of json "$output")"

  print -r -- "$video_json" | jq -e '
    .streams[0].codec_name == "h264" and
    .streams[0].width == 1080 and
    .streams[0].height == 1920 and
    .streams[0].r_frame_rate == "24/1" and
    (.format.duration | tonumber) >= 15.0 and
    (.format.duration | tonumber) <= 15.2
  ' >/dev/null

  print -r -- "$audio_json" | jq -e '
    .streams[0].codec_name == "aac" and
    .streams[0].sample_rate == "48000" and
    .streams[0].channels == 2
  ' >/dev/null

  ffmpeg -v error -i "$output" -f null -
done

loudness_report="$(ffmpeg -hide_banner -i "$voiced" \
  -af loudnorm=I=-16:TP=-1:LRA=7:print_format=json -f null - 2>&1)"
true_peak="$(print -r -- "$loudness_report" | awk -F'"' '/"input_tp"/ { print $4 }')"
awk -v peak="$true_peak" 'BEGIN {
  if (peak > -1.0) {
    printf "FAIL: true peak %.2f dBTP exceeds -1.0 dBTP\n", peak > "/dev/stderr";
    exit 1;
  }
}'

print "PASS: Fantan Pipa four-line recitation finals preserve the original music level"
