#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
style="$project_dir/docs/realistic-visual-style.md"
workflow="$project_dir/docs/production-workflow.md"
character="$project_dir/docs/character-bible.md"
episode="$project_dir/episodes/baixue/README.md"
scene_cards="$project_dir/episodes/baixue/prompts/scene-cards.md"
final_prompt="$project_dir/episodes/baixue/prompts/seedance-v01.md"

for required_file in "$style" "$workflow" "$character" "$episode" "$scene_cards" "$final_prompt"; do
  test -s "$required_file"
done

for phrase in \
  "第一个可感知动作必须来自栀夏" \
  "首帧必须已经能辨认栀夏" \
  "0.5秒内" \
  "不得以纯风景、纯意象、阿砚单独画面或角色缺席的空镜开场"; do
  rg -qF "$phrase" "$style"
done

for phrase in \
  "第一秒先看见谁、谁先动" \
  "第一个动作来自栀夏" \
  "0.5秒内清楚展示她的脸"; do
  rg -qF "$phrase" "$workflow"
done

for phrase in \
  "足底至耳尖的站立总高度约40厘米" \
  "肩高约24至28厘米" \
  "躯干长度约40至45厘米"; do
  rg -qF "$phrase" "$character"
done

test "$(rg -c '^## 状态图 01：' "$scene_cards")" = "1"
test "$(rg -c '^## 状态图 0[2-9]：' "$scene_cards" || echo 0)" = "0"

for phrase in \
  "栀夏优先开场" \
  "栀夏是第一视觉主体" \
  "阿砚足底至耳尖约40厘米"; do
  rg -qF "$phrase" "$scene_cards"
done

prompt_block="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' "$final_prompt")"
for phrase in \
  "0.000—0.500 秒，栀夏先动钩子" \
  "0.500—1.724 秒，阿砚无声疑问口型" \
  "M04" \
  "阿砚足底至耳尖约40厘米" \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸"; do
  print -r -- "$prompt_block" | rg -qF "$phrase"
done

for current_file in "$episode" "$scene_cards" "$final_prompt"; do
  if rg -n "8至10厘米|8 至 10 厘米|8—10厘米|微距雪晶钩子" "$current_file"; then
    exit 1
  fi
done

if rg -n "😀|🎬|✨" "$style" "$workflow" "$episode" "$scene_cards" "$final_prompt"; then
  exit 1
fi

echo "PASS: Zhixia-first opening and Baixue 40cm rules are enforced"
