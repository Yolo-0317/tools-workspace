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

continuous_manifest="$project_root/episodes/quzhong-huteng-15s/voice-lines-continuous-v03.json"
[[ -f "$continuous_manifest" ]] || {
  print -u2 "FAIL: missing single-call continuous recitation manifest"
  exit 1
}

jq -e '
  .format == "one-poem-story"
  and (.lines | length) == 1
  and .lines[0].role == "zhixia"
  and .lines[0].speech_rate == 0
  and .lines[0].text == "有些告别，不必说出口。把最后一步跳完，就该继续上路。丝桐忽奏一曲终，呜呜画角城头发。"
  and (.lines[0].context_texts | join("") | contains("压住不舍"))
  and (.lines[0].context_texts | join("") | contains("下定决心"))
  and (.lines[0].context_texts | join("") | contains("心里一震"))
  and (.lines[0].context_texts | join("") | contains("带着眷恋启程"))
' "$continuous_manifest" >/dev/null || {
  print -u2 "FAIL: continuous narration must use one call and one explicit emotional arc"
  exit 1
}

print "PASS: continuous narration uses one explicit emotional arc"

continuous_preview="$project_root/exports/quzhong-huteng-15s-recitation-continuous-v03.m4a"
[[ -f "$continuous_preview" ]] || {
  print -u2 "FAIL: missing 15-second continuous emotional preview"
  exit 1
}

continuous_duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$continuous_preview")"
awk -v value="$continuous_duration" 'BEGIN { exit !(value >= 14.99 && value <= 15.01) }' || {
  print -u2 "FAIL: continuous emotional preview must be 15 seconds, got $continuous_duration"
  exit 1
}

print "PASS: continuous emotional preview duration is $continuous_duration seconds"
