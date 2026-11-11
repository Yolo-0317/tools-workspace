#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h:h}
standard="$project_dir/docs/seedance-15s-poetry-dance-drama-standard.md"
template="$project_dir/assets/prompts/templates/seedance-15s-poetry-dance-drama.md"
composer="$project_dir/docs/zhixia-poetry-dance-composer.md"
workflow="$project_dir/docs/production-workflow.md"
yunzhongjun_remake="$project_dir/assets/prompts/jiuge/02-yunzhongjun-poetry-dance-drama-15s.md"

for target in "$standard" "$template" "$composer" "$workflow" "$yunzhongjun_remake"; do
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
  "第一帧空间锚定" \
  "承重地面" \
  "固定纵深锚点" \
  "当前 zhixia 声线"; do
  rg -qF "$phrase" "$standard" || {
    print -u2 "FAIL: missing $phrase"
    exit 1
  }
done

for phrase in \
  "【唯一事件】" \
  "【基础空间与第一帧锚点】" \
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

space_line=$(rg -nF "【基础空间与第一帧锚点】" "$template" | head -n 1 | cut -d: -f1)
event_line=$(rg -nF "【唯一事件】" "$template" | head -n 1 | cut -d: -f1)
first_peak_line=$(rg -nF "【0.000—1.800 秒｜第一高潮与诗意钩子】" "$template" | head -n 1 | cut -d: -f1)
if (( space_line >= event_line || space_line >= first_peak_line )); then
  print -u2 "FAIL: first-frame spatial anchor must precede event and timeline"
  exit 1
fi

rg -qF "承重地面" "$composer" || {
  print -u2 "FAIL: composer missing first-frame bearing surface"
  exit 1
}

rg -qF "固定纵深锚点" "$workflow" || {
  print -u2 "FAIL: workflow missing first-frame depth anchor"
  exit 1
}

for phrase in \
  "高山临崖风化石台" \
  "谷底云海明显低于石台" \
  "远处两至三层低饱和蓝灰山脊" \
  "不站在云上"; do
  rg -qF "$phrase" "$yunzhongjun_remake" || {
    print -u2 "FAIL: Yunzhongjun remake missing $phrase"
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
