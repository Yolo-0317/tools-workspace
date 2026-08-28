#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
library="$project_dir/docs/zhixia-classical-dance-library.md"
style_rules="$project_dir/docs/realistic-visual-style.md"
episode="$project_dir/episodes/baixue/README.md"
scene_cards="$project_dir/episodes/baixue/prompts/scene-cards.md"

test -s "$library"
test -s "$style_rules"
test -s "$episode"
test -s "$scene_cards"
test "$(rg -c '^### D[0-9]{2} ' "$library")" = "12"

for phrase in \
  "中国古典舞身韵" \
  "身韵为骨、汉唐气韵为神" \
  "提、沉、冲、靠、含、腆、移、仰" \
  "平圆、立圆、八字圆" \
  "每支诗镜只选择一个动作母题" \
  "最多完成两次换重、两至三步" \
  "不超过 180 度" \
  "不是专业水袖" \
  "专业术语转译" \
  "Seedance 正向提示词" \
  "三张状态卡" \
  "失败降级"; do
  rg -qF "$phrase" "$library"
done

for phrase in \
  "### D01 雪醒梨开" \
  "一片真实雪花" \
  "沉转提" \
  "圆场小步" \
  "约 135 度" \
  "简化云手" \
  "阿砚回应" \
  "脸部安全区"; do
  rg -qF "$phrase" "$library"
done

for phrase in \
  "zhixia-classical-dance-library.md" \
  "只选择一个 Dxx 动作母题" \
  "专业舞蹈术语必须转译" \
  "承重脚" \
  "不是专业水袖"; do
  rg -qF "$phrase" "$style_rules"
done

for phrase in \
  "忽如一夜春风来，千树万树梨花开" \
  "D01“雪醒梨开”" \
  "M02" \
  "H05" \
  "一片真实雪花" \
  "不生成图片或视频"; do
  rg -qF "$phrase" "$episode"
done

test "$(rg -c '^## 状态图 0[1-3]：' "$scene_cards")" = "3"

for phrase in \
  "栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg" \
  "阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg" \
  "同一处雪林边缘" \
  "同一右后方暖金晨光" \
  "唯一引导雪花" \
  "沉转提" \
  "约 135 度" \
  "脸部安全区" \
  "不得自动生成图片"; do
  rg -qF "$phrase" "$scene_cards"
done

if rg -n "😀|🎬|✨" "$library"; then
  exit 1
fi

echo "PASS: Zhixia classical dance library rules are enforced"
