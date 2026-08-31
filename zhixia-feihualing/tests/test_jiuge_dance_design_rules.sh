#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
validator="$project_dir/scripts/validate_jiuge_dance_design.py"

if [[ ! -f "$validator" ]]; then
  print -u2 "FAIL: missing validator scripts/validate_jiuge_dance_design.py"
  exit 1
fi

python3 -m unittest "$project_dir/tests/test_validate_jiuge_dance_design.py" -v
validator_output=$(python3 "$validator" --project-root "$project_dir")
expected='PASS: Jiuge future prompts are blocked pending poetry-dance drama rewrites'
if [[ "$validator_output" != "$expected" ]]; then
  print -u2 -r -- "FAIL: unexpected validator result: $validator_output"
  exit 1
fi
print -r -- "$validator_output"
