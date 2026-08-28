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
  "历史参考" \
  "每支诗境只制作一张开场状态卡" \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸" \
  "具体舞蹈由 Seedance 自由发挥"; do
  rg -qF "$phrase" "$library"
done

for phrase in \
  "每支诗境只保留一张开场状态卡" \
  "不再为单集自创或指定具体舞蹈动作" \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸" \
  "具体动作、连接与收势由 Seedance 自由发挥"; do
  rg -qF "$phrase" "$style_rules"
done

for phrase in \
  "M04" \
  "H05" \
  "一片真实雪花" \
  "最终 10 秒音画时间轴" \
  "只限定中国古典舞身韵、轻盈克制、连续自然、不遮脸" \
  "具体动作由 Seedance 自由发挥" \
  "不生成图片或视频"; do
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

if print -r -- "$prompt_block" | rg -q "梨花？|是新雪。|忽如一夜春风来|千树万树梨花开"; then
  exit 1
fi

if rg -n "😀|🎬|✨" "$library" "$style_rules" "$episode" "$scene_cards" "$final_prompt"; then
  exit 1
fi

echo "PASS: Zhixia single-state-card free-dance rules are enforced"
