#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/baixue/prompts/seedance-v01.md"
readme="$project_dir/episodes/baixue/README.md"

test -s "$prompt"
test -s "$readme"

prompt_block="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' "$prompt")"

require_phrase() {
  local content="$1"
  local phrase="$2"
  local label="$3"
  if ! print -r -- "$content" | rg -qF "$phrase"; then
    print -u2 -r -- "FAIL: missing '$phrase' in $label"
    exit 1
  fi
}

for phrase in \
  "0.5 秒内" \
  "沿小弧线迈步" \
  "重心由后脚平滑移向前脚" \
  "第二次换重" \
  "由微沉进入提起" \
  "高低错落的连续圆弧" \
  "一条主路径" \
  "第一次动作触发反应" \
  "第二次动作触发反应" \
  "前景视差" \
  "约40厘米" \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸" \
  "画面中始终只有积雪与松枝" \
  "声音只生成无人声背景音乐和自然环境声"; do
  require_phrase "$prompt_block" "$phrase" "Seedance prompt block"
done

for phrase in \
  "弧线移动" \
  "两次换重" \
  "两次动作触发反应" \
  "用户已确认层次舞蹈版 Seedance 原片通过" \
  "最终成片"; do
  require_phrase "$(<"$readme")" "$phrase" "Baixue README"
done

if print -r -- "$prompt_block" | rg -n '具体动作、连接与收势由 Seedance 自由发挥|摄影机始终位于|(^|[^[:alnum:]])[DM][0-9]{2}([^[:alnum:]]|$)|状态图|assets/|\.png|\.jpg'; then
  exit 1
fi

echo "PASS: Baixue layered dance and action-triggered camera prompt is enforced"
