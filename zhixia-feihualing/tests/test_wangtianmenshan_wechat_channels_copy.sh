#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
copy="$project_dir/episodes/wangtianmenshan-15s/wechat-channels-copy.md"
[[ -s "$copy" ]] || { print -u2 "FAIL: missing Wangtianmenshan WeChat Channels copy"; exit 1; }
for phrase in "栀夏这一舞，把青山碧水都舞醒了" "天门中断楚江开" "碧水东流至此回" "两岸青山相对出" "孤帆一片日边来" "AI美女舞蹈" "中国古典舞" "国风舞蹈" "古诗词" "原创虚拟角色｜AI辅助制作" "exports/wangtianmenshan-15s-subtitled-v01.mp4"; do rg -qF "$phrase" "$copy" || { print -u2 "FAIL: missing $phrase"; exit 1; }; done
if rg -n "Seedance|提示词|模型参数|真人舞者|专业舞蹈演员|全网第一|最美" "$copy"; then print -u2 "FAIL: copy contains production or exaggerated language"; exit 1; fi
print "PASS: Wangtianmenshan WeChat Channels copy is ready"
