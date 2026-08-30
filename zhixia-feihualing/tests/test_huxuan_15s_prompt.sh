#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/huxuan-15s/README.md"
prompt="$project_dir/episodes/huxuan-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Huxuan component $required"; exit 1; }
done

for required_text in \
  '@图片1是本项目原创虚构数字角色栀夏' \
  '0.000—1.800秒' \
  '4.800—7.000秒' \
  '10.000—13.200秒' \
  '立轴疾旋' \
  '贴地低位枢轴旋转' \
  '斜向景深完成两次短促腾跃换轴' \
  '近处幡幔只向上纵向扬起一次' \
  '两侧幡幔只向左右横向卷开' \
  '后方幡幔由近向远逐层掠动一次' \
  '全片手中无道具' \
  '人物不得小于画面高度的约一半' \
  '不生成对白、旁白、诗歌朗诵、吟唱、歌声、歌词'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }
rg -qF '弦鼓一声双袖举' "$readme" || { print -u2 "FAIL: README lacks poem"; exit 1; }
rg -qF '千匝万周无已时' "$readme" || { print -u2 "FAIL: README lacks final poem line"; exit 1; }

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^huxuan-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Huxuan history row is missing or duplicated"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in 'D01' 'M01' 'H01' 'S01' '图片2' '琵琶道具卡'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

print -r -- "PASS: Huxuan 15s prompt and history are complete"
