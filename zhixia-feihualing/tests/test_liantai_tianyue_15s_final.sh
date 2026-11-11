#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
build_script="$project_dir/scripts/build_liantai_tianyue_15s_final.sh"
source_video="$project_dir/episodes/liantai-tianyue-15s/assets/video/content-seedance-v01.mp4"
voice_manifest="$project_dir/episodes/liantai-tianyue-15s/voice-lines.json"
subtitle_plan="$project_dir/episodes/liantai-tianyue-15s/subtitle-plan.json"
audio_dir="$project_dir/assets/audio/liantai-tianyue-15s-paced-v01"
cards_dir="$project_dir/assets/subtitles/liantai-tianyue-15s"
voiced="$project_dir/exports/liantai-tianyue-15s-voiced-v01.mp4"
final="$project_dir/exports/liantai-tianyue-15s-subtitled-v01.mp4"
expected_source_sha="1561fe69b243e23b66d4a462b95207953b117616e8d4872faa9da3d219d12918"

[[ -s "$voice_manifest" ]] || { print -u2 "FAIL: missing Liantai Tianyue voice manifest"; exit 1; }
[[ -s "$subtitle_plan" ]] || { print -u2 "FAIL: missing Liantai Tianyue subtitle plan"; exit 1; }

jq -e '
  .episode == "liantai-tianyue-15s" and
  .audio_slug == "liantai-tianyue-15s-paced-v01" and
  [.lines[].role] == ["zhixia", "zhixia", "zhixia", "zhixia"] and
  [.lines[].text] == [
    "霜清东林钟。",
    "水白虎溪月。",
    "天香生虚空。",
    "天乐鸣不歇。"
  ] and
  ([.lines[].speech_rate] | all(. == -35))
' "$voice_manifest" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == ["霜清东林钟", "水白虎溪月", "天香生虚空", "天乐鸣不歇"] and
  .[0].start == 0.250 and .[0].end == 2.750 and
  .[1].start == 3.500 and .[1].end == 6.050 and
  .[2].start == 6.900 and .[2].end == 9.450 and
  .[3].start == 11.200 and .[3].end == 13.700 and
  .[0].attribution == "唐·李白《庐山东林寺夜怀》" and
  ([.[1,2,3].attribution // ""] | all(. == "")) and
  .[0].end < .[1].start and .[1].end < .[2].start and .[2].end < .[3].start
' "$subtitle_plan" >/dev/null

[[ -s "$source_video" ]] || { print -u2 "FAIL: missing archived Liantai Tianyue source video"; exit 1; }
[[ "$(shasum -a 256 "$source_video" | awk '{print $1}')" == "$expected_source_sha" ]] || {
  print -u2 "FAIL: archived Liantai Tianyue source hash changed"
  exit 1
}

for audio_file in \
  "$audio_dir/01-zhixia-zhixia-line-one.mp3" \
  "$audio_dir/02-zhixia-zhixia-line-two.mp3" \
  "$audio_dir/03-zhixia-zhixia-line-three.mp3" \
  "$audio_dir/04-zhixia-zhixia-line-four.mp3"; do
  [[ -s "$audio_file" ]] || { print -u2 "FAIL: missing voice asset: $audio_file"; exit 1; }
done

[[ -x "$build_script" ]] || { print -u2 "FAIL: missing executable Liantai Tianyue build script"; exit 1; }
! rg -q 'sidechaincompress|volume=.*enable|volume=.*between' "$build_script" || {
  print -u2 "FAIL: Liantai Tianyue build script must not duck the original soundtrack"
  exit 1
}
rg -q 'amix=inputs=2:duration=first:dropout_transition=0:normalize=0' "$build_script" || {
  print -u2 "FAIL: Liantai Tianyue build script must mix the unattenuated bed with voice"
  exit 1
}
rg -q 'alimiter=limit=0.870964:attack=5:release=80:level=false' "$build_script" || {
  print -u2 "FAIL: Liantai Tianyue final bus must reserve AAC true-peak headroom"
  exit 1
}
[[ "$(rg -o 'atempo=0\.92' "$build_script" | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: each Liantai Tianyue line must use only the approved 0.92 correction"
  exit 1
}
[[ "$(rg -o 'atempo=' "$build_script" | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: Liantai Tianyue narration must not use chained time stretching"
  exit 1
}

"$build_script" >/dev/null

[[ -s "$voiced" ]] || { print -u2 "FAIL: Liantai Tianyue voiced preview was not created"; exit 1; }
[[ -s "$final" ]] || { print -u2 "FAIL: Liantai Tianyue subtitled final was not created"; exit 1; }
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]] || {
  print -u2 "FAIL: expected four Liantai Tianyue subtitle cards"
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

hash_dir="$(mktemp -d /tmp/zhixia-liantai-audio-hash.XXXXXX)"
trap 'rm -rf "$hash_dir"' EXIT
ffmpeg -v error -i "$voiced" -map 0:a:0 -c copy -f adts "$hash_dir/voiced.aac"
ffmpeg -v error -i "$final" -map 0:a:0 -c copy -f adts "$hash_dir/final.aac"
[[ "$(shasum -a 256 "$hash_dir/voiced.aac" | awk '{print $1}')" == "$(shasum -a 256 "$hash_dir/final.aac" | awk '{print $1}')" ]] || {
  print -u2 "FAIL: voiced and subtitled Liantai Tianyue audio streams differ"
  exit 1
}

print "PASS: Liantai Tianyue four-line recitation HD finals are ready"
