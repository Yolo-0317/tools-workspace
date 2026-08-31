#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
copy="$project_dir/episodes/feimei-lvyao-15s/wechat-channels-copy.md"

[[ -s "$copy" ]] || { print -u2 'FAIL: missing Feimei Lvyao WeChat Channels copy'; exit 1; }
rg -Fxq '《栀夏·敦煌十六舞》07｜飞袂绿腰' "$copy"

for text in \
  '南国有佳人，' \
  '轻盈绿腰舞。' \
  '华筵九秋暮，' \
  '飞袂拂云雨。' \
  '原创虚拟角色｜AI辅助制作' \
  '敦煌十六舞下一支，你想看哪一种舞？也可以留下相关诗句。' \
  'exports/feimei-lvyao-15s-subtitled-v01.mp4' \
  'exports/feimei-lvyao-dance-cover-v01.png'; do
  rg -Fq "$text" "$copy"
done

[[ "$(rg -o '#[^ #]+' "$copy" | sort -u | wc -l | tr -d ' ')" == '6' ]] || {
  print -u2 'FAIL: expected exactly six unique hashtags'
  exit 1
}

if rg -q '古舞复原|壁画复刻|文物活化|数字敦煌|非遗传承|官方合作' "$copy"; then
  print -u2 'FAIL: unsupported historical or institutional claim'
  exit 1
fi

print 'PASS: Feimei Lvyao WeChat Channels copy is ready'
