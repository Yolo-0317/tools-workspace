#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
validator="$project_dir/scripts/validate_late_pose_prompt.py"
valid_fixture="$project_dir/tests/fixtures/late-pose-prompt-valid.txt"
early_pose_fixture="$project_dir/tests/fixtures/late-pose-prompt-early-pose.txt"
huanghe_prompt="$project_dir/episodes/huanghe/prompts/seedance-v01.md"

if [[ ! -x "$validator" ]]; then
  print -u2 -r -- "FAIL: missing executable late-pose validator: $validator"
  exit 1
fi

"$validator" "$valid_fixture"

if "$validator" "$early_pose_fixture" >/dev/null 2>&1; then
  print -u2 -r -- "FAIL: validator accepted a prompt that finishes the pose at 8 seconds"
  exit 1
fi

if [[ ! -s "$huanghe_prompt" ]]; then
  print -u2 -r -- "FAIL: missing Huanghe Seedance prompt: $huanghe_prompt"
  exit 1
fi

"$validator" "$huanghe_prompt"

print -r -- "PASS: late-pose ending rules and Huanghe prompt are ready"
