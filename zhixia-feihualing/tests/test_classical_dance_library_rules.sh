#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
library="$project_dir/docs/zhixia-classical-dance-library.md"
style_rules="$project_dir/docs/realistic-visual-style.md"
episode="$project_dir/episodes/baixue/README.md"
scene_cards="$project_dir/episodes/baixue/prompts/scene-cards.md"
final_prompt="$project_dir/episodes/baixue/prompts/seedance-v01.md"

test -s "$library"
test -s "$style_rules"
test -s "$episode"
test -s "$scene_cards"
test -s "$final_prompt"
test "$(rg -c '^### D[0-9]{2} ' "$library")" = "12"

for phrase in \
  "只作历史与动作研究" \
  "全局视觉规范" \
  "动作舒展有力、节奏鲜明、连续自然" \
  "诗境自动编舞组合器" \
  "不完全放任动作"; do
  rg -qF "$phrase" "$library"
done

for phrase in \
  "每支诗境至多保留一张开场状态卡作为人工构图参考" \
  "动作舒展有力、节奏鲜明、连续自然" \
  "完整旋转" \
  "视觉高潮" \
  "移动或脚步" \
  "重心或高低层次" \
  "上肢与衣料反馈" \
  "诗意结束" \
  "具体连接由模型在这些可观察条件内自然完成"; do
  rg -qF "$phrase" "$style_rules"
done

for phrase in \
  "三个宽时间段" \
  "一条主路径" \
  "枝头粉雪自然落下" \
  "梨花般的视觉联想" \
  "弧线移动、两次换重" \
  "具体连接只在这些可观察条件内自然完成" \
  "两次动作触发反应" \
  "最终成片"; do
  rg -qF "$phrase" "$episode"
done

test "$(rg -c '^## 状态图 01：' "$scene_cards")" = "1"
test "$(rg -c '^## 状态图 0[2-9]：' "$scene_cards" || echo 0)" = "0"

for phrase in \
  "只用于生成和审阅一张开场状态图" \
  "不锁定后续舞蹈动作或结束姿态" \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸" \
  "具体动作由 Seedance 自由发挥"; do
  rg -qF "$phrase" "$scene_cards"
done

prompt_block="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' "$final_prompt")"
print -r -- "$prompt_block" | rg -qF "中国古典舞身韵、轻盈克制、连续自然、不遮脸"

if print -r -- "$prompt_block" | rg -q "D01|沉转提|立圆|云手|山膀|圆场|135 度|90 度"; then
  exit 1
fi

if print -r -- "$prompt_block" | rg -q "唯一雪花|唯一引导雪花|无声.*口型|[0-9]+\.[0-9]{3}—[0-9]+\.[0-9]{3}"; then
  exit 1
fi

if print -r -- "$prompt_block" | rg -q "梨花？|是新雪。|忽如一夜春风来|千树万树梨花开"; then
  exit 1
fi

if rg -n "😀|🎬|✨" "$library" "$style_rules" "$episode" "$scene_cards" "$final_prompt"; then
  exit 1
fi

echo "PASS: Zhixia dance research boundary and observable-action rules are enforced"
