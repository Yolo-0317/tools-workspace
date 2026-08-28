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
  "每份 Seedance 提示词的第一句必须先声明" \
  "@图片1与@图片2均为本项目原创虚拟角色" \
  "最终提交给 Seedance 的提示词正文不得出现任何项目内部代码" \
  "只允许平台明确支持的参考图标记" \
  "第一个可感知动作必须来自栀夏" \
  "首帧必须已经能辨认栀夏" \
  "0.5秒内" \
  "不得以纯风景、纯意象、阿砚单独画面或角色缺席的空镜开场"; do
  rg -qF "$phrase" "$style"
done

for phrase in \
  "所有 Seedance 提示词在进入三层结构前" \
  "实际提交给模型的提示词正文内" \
  "从内部设计稿转换为最终提示词时" \
  "逐项展开为模型可直接理解的自然语言" \
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
first_prompt_line="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/{n;p;q;}' "$final_prompt")"
test "$first_prompt_line" = "@图片1与@图片2均为本项目原创虚拟角色，均为虚构数字角色，不对应任何现实人物、艺人、真实动物或既有影视动漫角色。"
for phrase in \
  "@图片1是原创虚拟角色栀夏，@图片2是原创虚拟东方墨灵阿砚" \
  "本次只上传两张角色母版，不上传状态图、首帧图或其他场景参考图" \
  "@图片1只参考栀夏的身份" \
  "@图片2只参考阿砚的身份" \
  "场景、首帧构图和全部运动只由文字提示词生成" \
  "0.000—0.500 秒，栀夏先动钩子" \
  "0.500—1.724 秒，阿砚无声疑问口型" \
  "摄影机沿栀夏身体外侧做极短、稳定的贴身侧滑" \
  "从此时起，唯一雪花才开始缓慢向前下落" \
  "阿砚足底至耳尖约40厘米" \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸"; do
  print -r -- "$prompt_block" | rg -qF "$phrase"
done

if print -r -- "$prompt_block" | rg -n '(^|[^[:alnum:]])[MHDS][0-9]{2}([^[:alnum:]]|$)|assets/|\.png|\.jpg|seedance-v[0-9]+|状态图[[:space:]]*[0-9]{2}'; then
  exit 1
fi

for phrase in \
  "两张参考图只用于锁定原创角色身份、结构与造型" \
  "场景、首帧构图和全部运动只由文字提示词生成" \
  "具体动作、连接与收势由 Seedance 自由发挥" \
  "声音只生成无人声背景音乐和自然环境声"; do
  print -r -- "$prompt_block" | rg -qF "$phrase"
done

if rg -n "状态图 01：|一张开场状态卡锁定|使用已经人工验收通过的雪林状态图" "$final_prompt"; then
  exit 1
fi

for current_file in "$episode" "$scene_cards" "$final_prompt"; do
  if rg -n "8至10厘米|8 至 10 厘米|8—10厘米|微距雪晶钩子" "$current_file"; then
    exit 1
  fi
done

if rg -n "😀|🎬|✨" "$style" "$workflow" "$episode" "$scene_cards" "$final_prompt"; then
  exit 1
fi

echo "PASS: Zhixia-first opening and Baixue 40cm rules are enforced"
