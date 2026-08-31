#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
voice="$project_dir/episodes/jiuge-donghuang-taiyi-15s/voice-lines.json"
subtitles="$project_dir/episodes/jiuge-donghuang-taiyi-15s/subtitle-plan.json"

[[ -s "$voice" ]] || { print -u2 "FAIL: missing Donghuang Taiyi voice manifest"; exit 1; }
[[ -s "$subtitles" ]] || { print -u2 "FAIL: missing Donghuang Taiyi subtitle plan"; exit 1; }

jq -e '
  .episode == "jiuge-donghuang-taiyi-15s" and
  .format == "one-poem-story" and
  .audio_slug == "jiuge-donghuang-taiyi-15s-v01" and
  [.lines[].role] == ["zhixia", "zhixia", "zhixia", "zhixia"] and
  [.lines[].text] == [
    "吉日兮辰良。",
    "穆将愉兮上皇。",
    "五音纷兮繁会。",
    "君欣欣兮乐康。"
  ]
' "$voice" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == ["吉日兮辰良", "穆将愉兮上皇", "五音纷兮繁会", "君欣欣兮乐康"] and
  [.[].side] == ["right", "left", "right", "left"] and
  .[0].start == 0.450 and .[0].end == 3.100 and
  .[1].start == 3.400 and .[1].end == 6.600 and
  .[2].start == 7.600 and .[2].end == 10.700 and
  .[3].start == 11.000 and .[3].end == 14.500 and
  .[0].attribution == "屈原《九歌·东皇太一》节选" and
  ([.[1,2,3].attribution // ""] | all(. == ""))
' "$subtitles" >/dev/null

print "PASS: Donghuang Taiyi recitation configuration is ready"
