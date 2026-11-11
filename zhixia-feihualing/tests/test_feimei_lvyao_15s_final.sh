#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
voice_manifest="$project_dir/episodes/feimei-lvyao-15s/voice-lines.json"
subtitle_plan="$project_dir/episodes/feimei-lvyao-15s/subtitle-plan.json"
source_video="$project_dir/exports/feimei-lvyao-15s-repaired-v01.mp4"
audio_dir="$project_dir/assets/audio/feimei-lvyao-15s-paced-v01"
cards_dir="$project_dir/assets/subtitles/feimei-lvyao-15s"
build_script="$project_dir/scripts/build_feimei_lvyao_15s_final.sh"
voiced_output="$project_dir/exports/feimei-lvyao-15s-voiced-v01.mp4"
final_output="$project_dir/exports/feimei-lvyao-15s-subtitled-v01.mp4"
check_dir="$(mktemp -d /tmp/zhixia-feimei-lvyao-final-test.XXXXXX)"
trap 'rm -rf "$check_dir"' EXIT

[[ -s "$voice_manifest" ]] || { print -u2 -r -- "FAIL: missing Feimei Lvyao voice-lines.json"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 -r -- "FAIL: missing Feimei Lvyao subtitle-plan.json"; exit 1; }
[[ -s "$source_video" ]] || { print -u2 -r -- "FAIL: missing repaired source master"; exit 1; }

jq -e '
  .episode == "feimei-lvyao-15s" and
  .audio_slug == "feimei-lvyao-15s-paced-v01" and
  [.lines[].role] == ["zhixia","zhixia","zhixia","zhixia"] and
  [.lines[].text] == [
    "南国有佳人。",
    "轻盈绿腰舞。",
    "华筵九秋暮。",
    "飞袂拂云雨。"
  ] and
  ([.lines[].speech_rate] | all(. == 0))
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == ["南国有佳人","轻盈绿腰舞","华筵九秋暮","飞袂拂云雨"] and
  [.[].start] == [1.300,4.100,7.050,11.100] and
  [.[].end] == [3.450,6.250,9.200,13.350] and
  .[0].attribution == "唐·李群玉《长沙九日登东楼观舞》"
' "$subtitle_plan" >/dev/null

source_hash="$(shasum -a 256 "$source_video" | awk '{ print $1 }')"
[[ "$source_hash" == "1df9482117c07833f8c7efaa23bc56f4d2cd76010002580db87e95e70bf4a6a5" ]] || {
  print -u2 -r -- "FAIL: repaired source master hash changed"
  exit 1
}

audio_files=(
  "$audio_dir/01-zhixia-zhixia-line-one.mp3"
  "$audio_dir/02-zhixia-zhixia-line-two.mp3"
  "$audio_dir/03-zhixia-zhixia-line-three.mp3"
  "$audio_dir/04-zhixia-zhixia-line-four.mp3"
)
window_limits=(2.150 2.150 2.150 2.250)

for index in {1..4}; do
  audio_file="${audio_files[$index]}"
  [[ -s "$audio_file" ]] || { print -u2 -r -- "FAIL: missing voice asset: $audio_file"; exit 1; }

  audio_json="$(ffprobe -v error -show_entries stream=codec_name,sample_rate,channels \
    -show_entries format=duration -of json "$audio_file")"
  print -r -- "$audio_json" | jq -e '
    .streams[0].codec_name == "mp3" and
    .streams[0].sample_rate == "24000" and
    .streams[0].channels == 1 and
    (.format.duration | tonumber) > 1.0
  ' >/dev/null

  trimmed_wav="$check_dir/trimmed-${index}.wav"
  ffmpeg -hide_banner -loglevel error -y -i "$audio_file" \
    -af "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse" \
    "$trimmed_wav"
  trimmed_duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$trimmed_wav")"
  awk -v duration="$trimmed_duration" -v limit="${window_limits[$index]}" -v line="$index" '
    BEGIN {
      if (duration > limit) {
        printf "FAIL: trimmed voice line %s is %.3f seconds; limit is %.3f\n", line, duration, limit > "/dev/stderr"
        exit 1
      }
    }
  '
done

[[ -x "$build_script" ]] || { print -u2 -r -- "FAIL: missing executable Feimei Lvyao final build script"; exit 1; }

if rg -q 'atempo=' "$build_script"; then
  print -u2 -r -- "FAIL: final build must not time-stretch the recitation"
  exit 1
fi

if rg -q 'sidechaincompress|volume=.*between|volume=.*enable' "$build_script"; then
  print -u2 -r -- "FAIL: final build must not duck the repaired source bed"
  exit 1
fi

"$build_script" >/dev/null

[[ -s "$voiced_output" ]] || { print -u2 -r -- "FAIL: voiced preview was not created"; exit 1; }
[[ -s "$final_output" ]] || { print -u2 -r -- "FAIL: subtitled final was not created"; exit 1; }
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 -r -- "FAIL: expected four subtitle cards"
  exit 1
}

source_aigc="$(ffprobe -v error -show_entries format_tags=AIGC -of default=nw=1:nk=1 "$source_video")"

for output in "$voiced_output" "$final_output"; do
  video_json="$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height,r_frame_rate \
    -show_entries format=duration -of json "$output")"
  audio_json="$(ffprobe -v error -select_streams a:0 \
    -show_entries stream=codec_name,sample_rate,channels -of json "$output")"
  output_aigc="$(ffprobe -v error -show_entries format_tags=AIGC -of default=nw=1:nk=1 "$output")"

  print -r -- "$video_json" | jq -e '
    .streams[0].codec_name == "h264" and
    .streams[0].width == 1080 and
    .streams[0].height == 1920 and
    .streams[0].r_frame_rate == "24/1" and
    (.format.duration | tonumber) >= 15.05 and
    (.format.duration | tonumber) <= 15.15
  ' >/dev/null

  print -r -- "$audio_json" | jq -e '
    .streams[0].codec_name == "aac" and
    .streams[0].sample_rate == "48000" and
    .streams[0].channels == 2
  ' >/dev/null

  [[ -n "$source_aigc" && "$output_aigc" == "$source_aigc" ]] || {
    print -u2 -r -- "FAIL: output did not preserve source AIGC metadata"
    exit 1
  }

  ffmpeg -hide_banner -loglevel error -i "$output" -f null -
done

ffmpeg -hide_banner -loglevel error -y -i "$voiced_output" -map 0:a:0 -c copy "$check_dir/voiced.aac"
ffmpeg -hide_banner -loglevel error -y -i "$final_output" -map 0:a:0 -c copy "$check_dir/final.aac"
voiced_audio_hash="$(shasum -a 256 "$check_dir/voiced.aac" | awk '{ print $1 }')"
final_audio_hash="$(shasum -a 256 "$check_dir/final.aac" | awk '{ print $1 }')"
[[ "$voiced_audio_hash" == "$final_audio_hash" ]] || {
  print -u2 -r -- "FAIL: voiced and subtitled audio tracks differ"
  exit 1
}

print -r -- "PASS: Feimei Lvyao four-line recitation finals are ready"
