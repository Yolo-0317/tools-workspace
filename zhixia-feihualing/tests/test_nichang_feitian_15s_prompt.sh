#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/nichang-feitian-15s/README.md"
prompt="$project_dir/episodes/nichang-feitian-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Nichang Feitian component $required"; exit 1; }
done

for required_text in \
  '@图片1是本项目原创虚构数字角色栀夏' \
  '只有一个栀夏' \
  '双手全程空着' \
  '0.000—1.800秒' \
  '4.800—7.000秒' \
  '10.000—13.200秒' \
  '纵向离地提展' \
  '横向S形腾移' \
  '斜前俯冲再提展' \
  '莲瓣只从脚下浅水莲池纵向扬起' \
  '莲瓣只向画面左右横向分开' \
  '莲瓣只沿斜向纵深由远向近掠动' \
  '第三高潮人物高度至少约60%' \
  '13—15秒人物高度不得低于约55%' \
  '第三高潮保持或微推，禁止后撤' \
  '左右上臂后外侧' \
  '不生成对白、旁白、诗歌朗诵、吟唱、歌声、歌词'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }
rg -qF '素手把芙蓉' "$readme" || { print -u2 "FAIL: README lacks opening poem line"; exit 1; }
rg -qF '飘拂升天行' "$readme" || { print -u2 "FAIL: README lacks final poem line"; exit 1; }

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^nichang-feitian-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Nichang Feitian history row is missing or duplicated"; exit 1; }
[[ "$(awk -F, '$1=="nichang-feitian-15s" {print $19}' "$history_file")" == "designed" ]] || { print -u2 "FAIL: Nichang Feitian history status must be designed"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in '基础级' '高潮动作家族' '视觉指纹' 'v03' '文件名' '复原唐代舞谱' '图片2'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

print -r -- "PASS: Nichang Feitian 15s prompt and history are complete"
