#!/bin/zsh
set -euo pipefail

project_root="${0:A:h:h}"
manifest="$project_root/episodes/yunque-jiyue-15s/voice-lines-continuous-v01.json"
builder="$project_root/scripts/build_yunque_jiyue_recitation.sh"
preview="$project_root/exports/yunque-jiyue-15s-recitation-v01.m4a"

[[ -f "$manifest" ]] || { print -u2 "FAIL: missing 云阙伎乐 continuous recitation manifest"; exit 1; }

jq -e '
  .format == "one-poem-story"
  and (.lines | length) == 1
  and .lines[0].role == "zhixia"
  and .lines[0].speech_rate == 0
  and .lines[0].text == "有些美好，并没有真的离开。被人记起时，它就会重新有颜色。只愁歌舞散，化作彩云飞。"
  and (.lines[0].context_texts | join("") | contains("温柔回望"))
  and (.lines[0].context_texts | join("") | contains("明亮笃定"))
  and (.lines[0].context_texts | join("") | contains("只愁歌舞散"))
  and (.lines[0].context_texts | join("") | contains("化作彩云飞"))
' "$manifest" >/dev/null || {
  print -u2 "FAIL: recitation must be one continuous emotional TTS call"
  exit 1
}

[[ -x "$builder" ]] || { print -u2 "FAIL: missing executable recitation builder"; exit 1; }
"$builder" >/dev/null

[[ -f "$preview" ]] || { print -u2 "FAIL: missing 15-second recitation preview"; exit 1; }

duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$preview")"
awk -v value="$duration" 'BEGIN { exit !(value >= 14.99 && value <= 15.01) }' || {
  print -u2 "FAIL: preview duration must be 15 seconds, got $duration"
  exit 1
}

ffmpeg -v error -i "$preview" -f null -

last_voice_end="$(
  ffmpeg -hide_banner -i "$preview" -af silencedetect=noise=-40dB:d=0.08 -f null - 2>&1 \
    | sed -n 's/.*silence_start: \([0-9.]*\).*/\1/p' \
    | tail -n 1
)"
awk -v value="$last_voice_end" 'BEGIN { exit !(value >= 14.50 && value <= 14.95) }' || {
  print -u2 "FAIL: final spoken line must end near 15 seconds, got $last_voice_end"
  exit 1
}

print "PASS: 云阙伎乐 15-second continuous recitation is ready"
