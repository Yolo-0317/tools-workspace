#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
style="$project_dir/docs/realistic-visual-style.md"
workflow="$project_dir/docs/production-workflow.md"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
history_csv="$project_dir/operations/dance-design-history.csv"
ayan_rules="$project_dir/assets/characters/阿砚角色母板-v01-Seedance固定说明.md"
character_bible="$project_dir/docs/character-bible.md"

require_phrase() {
  local phrase="$1"
  shift
  rg -qF "$phrase" "$@" || {
    print -u2 -r -- "FAIL: missing required rule '$phrase' in $*"
    exit 1
  }
}

for required_file in "$style" "$workflow" "$composer" "$history_csv" "$ayan_rules" "$character_bible"; do
  if [[ ! -s "$required_file" ]]; then
    print -u2 -r -- "FAIL: missing required high-impact dance component $required_file"
    exit 1
  fi
done

for current_file in "$style" "$workflow" "$composer"; do
  for phrase in \
    "诗中核心景物" \
    "动作舒展有力、节奏鲜明、连续自然" \
    "完整旋转" \
    "视觉高潮" \
    "特效由动作触发" \
    "旋转与高潮" \
    "不强制形成封面舞姿" \
    "近期至少五支诗境"; do
    require_phrase "$phrase" "$current_file"
  done
done

for current_file in "$ayan_rules" "$character_bible" "$style" "$workflow"; do
  require_phrase "外扩纸纤维" "$current_file"
  require_phrase "不得变成贴身顺毛" "$current_file"
  require_phrase "不强制安排阿砚单独特写" "$current_file"
done

expected_header="episode,poem,opening,movement,rotation,body_level,carrier,effect,camera_reaction,ending,status,notes"
actual_header="$(head -n 1 "$history_csv")"
if [[ "$actual_header" != "$expected_header" ]]; then
  print -u2 -r -- "FAIL: unexpected dance history header '$actual_header'"
  exit 1
fi

for obsolete in \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸" \
  "承载一个主要视觉事件和中等复杂度以内的舞蹈短句"; do
  if rg -nF "$obsolete" "$style" "$workflow"; then
    print -u2 -r -- "FAIL: obsolete dance baseline remains: $obsolete"
    exit 1
  fi
done

if rg -n "😀|🎬|✨" "$style" "$workflow" "$composer" "$ayan_rules" "$character_bible"; then
  exit 1
fi

print -r -- "PASS: high-impact poetry dance and Ayan fiber rules are enforced"
