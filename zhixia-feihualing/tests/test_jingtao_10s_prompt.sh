#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
episode="$project_dir/episodes/jingtao/README.md"
prompt="$project_dir/episodes/jingtao/prompts/seedance-v01.md"
history_csv="$project_dir/operations/dance-design-history.csv"

for required_file in "$episode" "$prompt" "$history_csv"; do
  if [[ ! -s "$required_file" ]]; then
    print -u2 -r -- "FAIL: missing required Jingtao component $required_file"
    exit 1
  fi
done

prompt_block="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' "$prompt")"
first_prompt_line="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/{n;p;q;}' "$prompt")"

expected_first_line="@图片1与@图片2均为本项目原创虚拟角色，均为虚构数字角色，不对应任何现实人物、艺人、真实动物或既有影视动漫角色。"
if [[ "$first_prompt_line" != "$expected_first_line" ]]; then
  print -u2 -r -- "FAIL: prompt does not begin with the fixed original-character declaration"
  exit 1
fi

for phrase in \
  "本次输入仅有图片1与图片2" \
  "10 秒" \
  "9:16" \
  "湿黑乱石" \
  "奔涌大江" \
  "高耸赤壁" \
  "动作舒展有力、节奏鲜明、连续自然" \
  "两次重心变化" \
  "完整旋转" \
  "视觉高潮" \
  "白色浪沫" \
  "不是雪" \
  "摄影机采用一条低位斜向后退主路径" \
  "第一次动作触发反应" \
  "第二次动作触发反应" \
  "阿砚足底至耳尖约40厘米" \
  "外扩纸纤维" \
  "不强制安排阿砚单独特写" \
  "不得生成任何可辨识人声"; do
  if ! print -r -- "$prompt_block" | rg -qF "$phrase"; then
    print -u2 -r -- "FAIL: prompt is missing '$phrase'"
    exit 1
  fi
done

if print -r -- "$prompt_block" | rg -n '(^|[^[:alnum:]])[MHDS][0-9]{2}([^[:alnum:]]|$)|assets/|\.png|\.jpg|状态图|轻盈克制|乱石穿空|惊涛拍岸|卷起千堆雪'; then
  print -u2 -r -- "FAIL: prompt contains internal code, source text, or obsolete dance language"
  exit 1
fi

if ! rg -q '^jingtao,' "$history_csv"; then
  print -u2 -r -- "FAIL: Jingtao dance design is not registered"
  exit 1
fi

if rg -n "😀|🎬|✨" "$episode" "$prompt"; then
  exit 1
fi

print -r -- "PASS: Jingtao 10s high-impact dance prompt is ready"
