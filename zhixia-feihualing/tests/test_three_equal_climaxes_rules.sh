#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
style="$project_dir/docs/realistic-visual-style.md"
workflow="$project_dir/docs/production-workflow.md"
history_csv="$project_dir/operations/dance-design-history.csv"

require_phrase() {
  local phrase="$1"
  local target="$2"
  rg -qF "$phrase" "$target" || {
    print -u2 -r -- "FAIL: missing three-climax rule '$phrase' in $target"
    exit 1
  }
}

for target in "$composer" "$style" "$workflow" "$history_csv"; do
  [[ -s "$target" ]] || {
    print -u2 -r -- "FAIL: missing required file $target"
    exit 1
  }
done

for target in "$composer" "$style" "$workflow"; do
  for phrase in \
    "15 秒三次同等强度高潮" \
    "0.000—1.800 秒" \
    "4.800—7.000 秒" \
    "10.000—13.000 秒" \
    "13.000—15.000 秒" \
    "纵向、横向和纵深" \
    "身体发力" \
    "轮廓变化" \
    "空间变化" \
    "承接物轨迹" \
    "镜头反馈" \
    "一个核心自然元素" \
    "一条摄影机主路径" \
    "不追溯重做"; do
    require_phrase "$phrase" "$target"
  done
done

expected_header="episode,poem,opening,movement,climax_family,rotation,body_level,opening_silhouette,arm_path,leg_silhouette,carrier,carrier_shape,effect,effect_shape,climax_window,camera_reaction,camera_climax,ending,status,notes,peak_sequence,peak_directions,peak_windows,carrier_trajectories,camera_peak_reactions"
actual_header="$(head -n 1 "$history_csv")"
[[ "$actual_header" == "$expected_header" ]] || {
  print -u2 -r -- "FAIL: unexpected three-climax history header '$actual_header'"
  exit 1
}

awk -F, '
  NF != 25 { exit 1 }
  NR > 1 && ($1 == "" || $2 == "" || $5 == "" || $8 == "" || $9 == "" || $10 == "" || $12 == "" || $14 == "" || $15 == "" || $17 == "" || $19 == "") { exit 1 }
  END { exit !(NR >= 2) }
' "$history_csv" || {
  print -u2 "FAIL: dance history does not preserve 20 legacy fields plus 5 three-climax fields"
  exit 1
}

print "PASS: 15-second three equal-strength climaxes and compatible history schema are enforced"
