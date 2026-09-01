#!/bin/zsh
set -euo pipefail

project_root="${0:A:h:h}"
manifest="$project_root/episodes/quzhong-huteng-15s/voice-lines.json"

[[ -f "$manifest" ]] || { print -u2 "FAIL: missing voice manifest"; exit 1; }

jq -e '
  .lines[]
  | select(.id == "04-classic-horn")
  | .text == "呜呜画角城头发。"
    and .revision == 2
    and .speech_rate == 0
    and (.context_texts | join("") | contains("呜呜画角四字必须连续说出"))
    and (.context_texts | join("") | contains("只在画角之后轻停"))
' "$manifest" >/dev/null || {
  print -u2 "FAIL: final line must group 呜呜画角／城头发 without pausing after 呜呜"
  exit 1
}

print "PASS: final line pronunciation grouping is explicit"

preview="$project_root/exports/quzhong-huteng-15s-recitation-v02.m4a"
[[ -f "$preview" ]] || { print -u2 "FAIL: missing corrected 15-second preview"; exit 1; }

duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$preview")"
awk -v value="$duration" 'BEGIN { exit !(value >= 14.99 && value <= 15.01) }' || {
  print -u2 "FAIL: corrected preview duration must be 15 seconds, got $duration"
  exit 1
}

print "PASS: corrected preview duration is $duration seconds"
