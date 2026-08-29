#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
style="$project_dir/docs/realistic-visual-style.md"
workflow="$project_dir/docs/production-workflow.md"
character_bible="$project_dir/docs/character-bible.md"
memory="$project_dir/../.cursor/rules/memory-workspace.mdc"

require_phrase() {
  local phrase="$1"
  shift
  rg -qF "$phrase" "$@" || {
    print -u2 -r -- "FAIL: missing Ayan dynamic-participation rule '$phrase' in $*"
    exit 1
  }
}

for required_file in "$composer" "$style" "$workflow" "$character_bible" "$memory"; do
  [[ -s "$required_file" ]] || { print -u2 "FAIL: missing $required_file"; exit 1; }
done

for current_file in "$composer" "$style" "$workflow" "$character_bible"; do
  for phrase in \
    "动态跟随" \
    "奔跑、跨步" \
    "不得整段静坐" \
    "不抢栀夏的开场和主高潮" \
    "不横穿栀夏腿部"; do
    require_phrase "$phrase" "$current_file"
  done
done

for phrase in \
  "阿砚动态参与" \
  "默认动态跟随" \
  "一次短距离跃过" \
  "保持减速移动直至画面结束"; do
  require_phrase "$phrase" "$memory"
done

print "PASS: Ayan stays dynamically involved without stealing Zhixia's dance"
