#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
episode_dir="$project_dir/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s"
source_video="$episode_dir/assets/video/content-seedance-v01.mp4"
voice_dir="$project_dir/assets/audio/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voice-v01"
voice_audio="$voice_dir/full-recitation-preview-three-lines-10.08s-v03-mono-safe.wav"
voice_builder="$project_dir/scripts/build_jiuyue_haoyun_recitation_v03.sh"
subtitle_plan="$episode_dir/subtitle-plan-jiuyue-haoyun-v01.json"
renderer="$project_dir/scripts/render_jiuyue_haoyun_subtitle_cards.swift"
builder="$project_dir/scripts/build_tiangong_hot_dance_jiuyue_haoyun_final.sh"
voiced="$project_dir/exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voiced-v01.mp4"
subtitled="$project_dir/exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-subtitled-v01.mp4"

fail() {
  print -u2 -r -- "FAIL: $1"
  exit 1
}

for required in \
  "$source_video" \
  "$voice_dir/01-zhixia-modern-blessing.mp3" \
  "$voice_dir/02-zhixia-middle-wish.mp3" \
  "$voice_dir/02-zhixia-poem.mp3" \
  "$subtitle_plan"; do
  [[ -s "$required" ]] || fail "missing required input: $required"
done

jq -e '
  length == 3 and
  .[0] == {id:"01-modern-blessing",kind:"modern",text:"九月 愿所有美好 久久相伴",start:0.42,end:3.7} and
  .[1] == {id:"02-middle-wish",kind:"modern",text:"所念 皆能如愿",start:4.57,end:6.1} and
  .[2] == {id:"03-poem",kind:"poem",text:"好风凭借力，送我上青云",attribution:"清·曹雪芹《临江仙·柳絮》",start:6.96,end:9.52}
' "$subtitle_plan" >/dev/null || fail "invalid subtitle plan"

[[ -s "$renderer" ]] || fail "missing subtitle renderer"
[[ -x "$voice_builder" ]] || fail "missing mono-safe recitation builder"
[[ -x "$builder" ]] || fail "missing executable final builder"

"$voice_builder" >/dev/null
[[ -s "$voice_audio" ]] || fail "missing rebuilt mono-safe recitation"
voice_json="$(
  ffprobe -v error \
    -show_entries format=duration:stream=codec_name,sample_rate,channels \
    -of json "$voice_audio"
)"
print -r -- "$voice_json" | jq -e '
  ([.streams[] | select(.codec_name == "pcm_s16le" and .sample_rate == "48000" and .channels == 2)] | length) == 1 and
  ((.format.duration | tonumber) >= 10.079) and
  ((.format.duration | tonumber) <= 10.081)
' >/dev/null || fail "invalid rebuilt recitation parameters"
voice_channel_difference_db="$(
  ffmpeg -hide_banner -i "$voice_audio" \
    -af "pan=mono|c0=c0-c1,volumedetect" -f null - 2>&1 |
    sed -n 's/.*mean_volume: \([-a-zA-Z0-9.]*\) dB.*/\1/p' |
    tail -1
)"
[[ "$voice_channel_difference_db" == "-91.0" || "$voice_channel_difference_db" == "-inf" ]] || \
  fail "rebuilt narration channels are not identical: ${voice_channel_difference_db} dB"
first_audible_second="$(
  ffmpeg -hide_banner -i "$voice_audio" \
    -af "pan=mono|c0=c0,silencedetect=noise=-42dB:d=0.05" -f null - 2>&1 |
    sed -n 's/.*silence_end: \([0-9.]*\).*/\1/p' |
    head -1
)"
[[ -n "$first_audible_second" ]] || fail "cannot detect first narration entry"
awk -v value="$first_audible_second" 'BEGIN { exit !(value >= 0.40 && value <= 0.48) }' || \
  fail "first narration entry drifted from the subtitle: ${first_audible_second}s"

test_dir="$(mktemp -d /tmp/zhixia-jiuyue-final-test.XXXXXX)"
trap 'rm -rf "$test_dir"' EXIT
cards_dir="$test_dir/cards"
CLANG_MODULE_CACHE_PATH="$test_dir/clang-cache" \
SWIFT_MODULECACHE_PATH="$test_dir/swift-cache" \
  swift "$renderer" "$subtitle_plan" "$cards_dir"

poem_crop="$(
  ffmpeg -hide_banner -loglevel verbose -loop 1 \
    -i "$cards_dir/03-poem.png" \
    -vf "alphaextract,cropdetect=limit=0.01:round=2:reset=1" \
    -frames:v 5 -f null - 2>&1 |
    sed -n 's/.*crop=\([0-9][0-9]*:[0-9][0-9]*:[0-9][0-9]*:[0-9][0-9]*\).*/\1/p' |
    tail -1
)"
[[ -n "$poem_crop" ]] || fail "cannot detect poem subtitle bounds"
crop_parts=("${(@s/:/)poem_crop}")
(( crop_parts[1] >= 240 )) || fail "poem subtitle is not a wide top layout: $poem_crop"
(( crop_parts[2] <= 180 )) || fail "poem subtitle is too tall and may cover faces: $poem_crop"
(( crop_parts[4] <= 300 )) || fail "poem subtitle is below the upper safe area: $poem_crop"

"$builder" >/dev/null

for output in "$voiced" "$subtitled"; do
  [[ -s "$output" ]] || fail "missing output: $output"
  media_json="$(ffprobe -v error -show_entries format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels -of json "$output")"
  print -r -- "$media_json" | jq -e '
    ([.streams[] | select(.codec_type == "video")] | length) == 1 and
    ([.streams[] | select(.codec_type == "audio")] | length) == 1 and
    ([.streams[] | select(.codec_type == "video")][0] |
      .codec_name == "h264" and .width == 1080 and .height == 1920 and .r_frame_rate == "24/1") and
    ([.streams[] | select(.codec_type == "audio")][0] |
      .codec_name == "aac" and .sample_rate == "48000" and .channels == 2) and
    ((.format.duration | tonumber) >= 10.04) and
    ((.format.duration | tonumber) <= 10.12)
  ' >/dev/null || fail "invalid media parameters: $output"
  ffmpeg -v error -i "$output" -f null - || fail "decode failed: $output"
done

tail_mean_db="$(
  ffmpeg -hide_banner -i "$subtitled" \
    -af "atrim=start=9.40:end=9.70,asetpts=PTS-STARTPTS,volumedetect" -f null - 2>&1 |
    sed -n 's/.*mean_volume: \([-0-9.]*\) dB.*/\1/p' |
    tail -1
)"
[[ -n "$tail_mean_db" ]] || fail "cannot measure ending audio"
awk -v value="$tail_mean_db" 'BEGIN { exit !(value > -48.0) }' || \
  fail "ending audio is effectively silent: ${tail_mean_db} dB"

ffmpeg -v error -y -i "$voiced" -map 0:a:0 -c copy -f adts "$test_dir/voiced.aac"
ffmpeg -v error -y -i "$subtitled" -map 0:a:0 -c copy -f adts "$test_dir/subtitled.aac"

voiced_hash="$(shasum -a 256 "$test_dir/voiced.aac" | awk '{print $1}')"
subtitled_hash="$(shasum -a 256 "$test_dir/subtitled.aac" | awk '{print $1}')"
[[ "$voiced_hash" == "$subtitled_hash" ]] || fail "voiced and subtitled audio tracks differ"

print -r -- "PASS: 九月好运天宫双人热舞成片已就绪"
