#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
workflow="$project_dir/docs/production-workflow.md"
style="$project_dir/docs/realistic-visual-style.md"

require_rule() {
  local rule_name="$1"
  local phrase="$2"
  local target="$3"
  rg -qF "$phrase" "$target" || {
    print -u2 -r -- "FAIL: missing $rule_name rule '$phrase' in $target"
    exit 1
  }
}

for target in "$composer" "$workflow" "$style"; do
  [[ -s "$target" ]] || { print -u2 -r -- "FAIL: missing $target"; exit 1; }
  require_rule "no-running" "不得把持续奔跑" "$target"
  require_rule "connective-steps" "一至两步" "$target"
  require_rule "dance-units" "至少两类" "$target"
  require_rule "camera-follows-dance" "摄影机围绕舞姿" "$target"
  require_rule "Ayan-running-exception" "阿砚可以奔跑跟随" "$target"
done

print "PASS: Zhixia dance rules prevent running from replacing choreography"
