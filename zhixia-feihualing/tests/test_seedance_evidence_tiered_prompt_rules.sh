#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
style="$project_dir/docs/realistic-visual-style.md"
workflow="$project_dir/docs/production-workflow.md"
dance_library="$project_dir/docs/zhixia-classical-dance-library.md"

require_phrase() {
  local phrase="$1"
  shift
  rg -qF "$phrase" "$@" || {
    print -u2 -- "FAIL: missing required rule '$phrase' in $*"
    exit 1
  }
}

for required_file in "$style" "$workflow" "$dance_library"; do
  test -s "$required_file"
done

for current_file in "$style" "$workflow"; do
  for phrase in \
    "基础级" \
    "控制级" \
    "迁移级" \
    "移动或脚步" \
    "重心变化" \
    "方向或高低层次" \
    "上肢与衣料反馈" \
    "起止状态" \
    "一条主路径" \
    "最多两次" \
    "视差" \
    "动作触发反应" \
    "0.5 秒内" \
    "约 40 厘米"; do
    require_phrase "$phrase" "$current_file"
  done
done

for phrase in \
  "六类语义自然组织" \
  "复杂事件推荐三个宽时间段" \
  "具体连接由模型在这些可观察条件内自然完成"; do
  require_phrase "$phrase" "$style" "$workflow"
done

for phrase in \
  "只作历史与动作研究" \
  "不完全放任动作" \
  "全局视觉规范"; do
  require_phrase "$phrase" "$dance_library"
done

for obsolete in \
  "舞蹈约束完整且仅为" \
  "具体动作、连接与收势由 Seedance 自由发挥" \
  "最终提示词固定使用六段结构"; do
  if rg -nF "$obsolete" "$style" "$workflow"; then
    exit 1
  fi
done

if rg -n "😀|🎬|✨" "$style" "$workflow" "$dance_library"; then
  exit 1
fi

echo "PASS: evidence-tiered Seedance prompt rules are enforced"
