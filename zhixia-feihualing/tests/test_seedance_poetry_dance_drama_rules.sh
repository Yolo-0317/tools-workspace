#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
standard="$project_dir/docs/seedance-15s-poetry-dance-drama-standard.md"
template="$project_dir/assets/prompts/templates/seedance-15s-poetry-dance-drama.md"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
workflow="$project_dir/docs/production-workflow.md"

for target in "$standard" "$template" "$composer" "$workflow"; do
  [[ -s "$target" ]] || {
    print -u2 "FAIL: missing $target"
    exit 1
  }
done

for phrase in \
  "一位核心人物" \
  "一个事件" \
  "一个视觉象征" \
  "一个连续空间" \
  "一条摄影机主路径" \
  "栀夏为什么起舞" \
  "舞后发生什么变化" \
  "0.000—1.800 秒" \
  "4.800—7.000 秒" \
  "10.000—13.200 秒" \
  "建立—行动—结果" \
  "当前 zhixia 声线"; do
  rg -qF "$phrase" "$standard" || {
    print -u2 "FAIL: missing $phrase"
    exit 1
  }
done

for phrase in \
  "【唯一事件】" \
  "【核心视觉象征】" \
  "【0.000—1.800 秒｜第一高潮与诗意钩子】" \
  "【4.800—7.000 秒｜第二高潮与行动决定】" \
  "【10.000—13.200 秒｜第三高潮与最终变化】" \
  "Seedance 不生成可辨识人声" \
  "后期栀夏朗诵"; do
  rg -qF "$phrase" "$template" || {
    print -u2 "FAIL: template missing $phrase"
    exit 1
  }
done

for target in "$standard" "$template" "$composer" "$workflow"; do
  if rg -q "优先使用 Seedance 原生画外朗诵|默认由 Seedance 原生生成" "$target"; then
    print -u2 "FAIL: active file still defaults to native recitation: $target"
    exit 1
  fi
done

rg -qF "docs/seedance-15s-poetry-dance-drama-standard.md" "$project_dir/README.md" || {
  print -u2 "FAIL: README missing standard link"
  exit 1
}

print "PASS: Seedance 15-second poetry-dance drama standard is enforced"
