#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
validator="$project_dir/scripts/validate_jiuge_dance_design.py"

if [[ ! -f "$validator" ]]; then
  print -u2 "FAIL: missing validator scripts/validate_jiuge_dance_design.py"
  exit 1
fi

python3 -m unittest "$project_dir/tests/test_validate_jiuge_dance_design.py" -v
python3 "$validator" --project-root "$project_dir"
