#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
library="$project_dir/docs/zhixia-classical-dance-library.md"

test -s "$library"
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

if rg -n "😀|🎬|✨" "$library"; then
  exit 1
fi

echo "PASS: Zhixia classical dance library rules are enforced"
