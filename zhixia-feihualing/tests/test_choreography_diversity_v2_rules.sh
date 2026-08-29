#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
style="$project_dir/docs/realistic-visual-style.md"
workflow="$project_dir/docs/production-workflow.md"
history_csv="$project_dir/operations/dance-design-history.csv"

require_phrase() {
  local phrase="$1"
  shift
  rg -qF "$phrase" "$@" || {
    print -u2 -r -- "FAIL: missing v2 choreography rule '$phrase' in $*"
    exit 1
  }
}

for required_file in "$composer" "$style" "$workflow" "$history_csv"; do
  [[ -s "$required_file" ]] || { print -u2 "FAIL: missing $required_file"; exit 1; }
done

for phrase in \
  "主高潮动作家族" \
  "行进旋转" \
  "腾跃展开" \
  "低位扫展" \
  "倾身穿行" \
  "回身展臂" \
  "道具牵引" \
  "纵向提沉" \
  "连续两集禁止" \
  "最多出现两次" \
  "九项视觉指纹" \
  "三项或以上相同" \
  "不得进入 Seedance 提示词" \
  "水景不得默认选择"; do
  require_phrase "$phrase" "$composer"
done

for current_file in "$style" "$workflow"; do
  for phrase in \
    "主高潮动作" \
    "完整旋转不再是必选项" \
    "九项视觉指纹" \
    "三项或以上相同" \
    "开场进入与主高潮动作"; do
    require_phrase "$phrase" "$current_file"
  done
done

for obsolete in \
  "每支新诗境必须写明移动或脚步、至少两次重心或高低层次变化、完整旋转的进入与离开" \
  "正文必须同时描述空间移动、至少两次重心或高低层次变化、完整旋转的进入与离开" \
  "旋转是每支新诗境的固定观感要求"; do
  if rg -nF "$obsolete" "$composer" "$style" "$workflow"; then
    print -u2 -r -- "FAIL: obsolete mandatory-rotation rule remains: $obsolete"
    exit 1
  fi
done

expected_header="episode,poem,opening,movement,climax_family,rotation,body_level,opening_silhouette,arm_path,leg_silhouette,carrier,carrier_shape,effect,effect_shape,climax_window,camera_reaction,camera_climax,ending,status,notes"
actual_header="$(head -n 1 "$history_csv")"
[[ "$actual_header" == "$expected_header" ]] || {
  print -u2 -r -- "FAIL: unexpected dance history header '$actual_header'"
  exit 1
}

awk -F, '
  NR > 1 && NF != 20 { exit 1 }
  NR > 1 && ($5 == "" || $8 == "" || $9 == "" || $10 == "" || $12 == "" || $14 == "" || $15 == "" || $17 == "") { exit 1 }
  END { exit !(NR >= 3) }
' "$history_csv" || {
  print -u2 "FAIL: dance history rows do not contain complete v2 visual fingerprints"
  exit 1
}

print "PASS: choreography diversity v2 rules and visual fingerprints are enforced"
