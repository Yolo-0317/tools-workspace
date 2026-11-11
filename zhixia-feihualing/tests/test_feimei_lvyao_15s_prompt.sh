#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/feimei-lvyao-15s/README.md"
prompt="$project_dir/episodes/feimei-lvyao-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Feimei Lvyao component $required"; exit 1; }
done

for required_text in \
  '参考上传图片中的栀夏' \
  '第一帧完整显示栀夏从头顶到鞋履' \
  '0.000—1.800秒，兰苕侧折' \
  '4.800—7.000秒，游龙回腰' \
  '10.000—13.200秒，飞袂凌云' \
  '深侧弓步' \
  '斜向S形交叉步' \
  '剪步腾跃' \
  '左右上臂后外侧' \
  '秋叶形成窄幅向上弧线' \
  '左右青绿色帷幔依次横向起伏' \
  '后方帷幔下缘与旧金流苏向斜前方掠动' \
  '沿原轴迎面短促推近' \
  '13.200—15.000秒' \
  '清亮琵琶、拍板和小鼓'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }

for required_text in \
  '南国有佳人' \
  '飞袂拂云雨' \
  '原创敦煌绿腰舞意象' \
  '“绿腰”是舞名' \
  '第一帧完整全身强起势' \
  '约 68%—72%' \
  '约 68%—73%' \
  '约 70%—74%' \
  '保持背景音乐原音量'; do
  rg -qF "$required_text" "$readme" || { print -u2 -r -- "FAIL: README lacks $required_text"; exit 1; }
done

for forbidden_claim in '唐代舞谱复原' '莫高窟第 445 窟舞姿复原' 'AI活化文物' '数字敦煌复原' '某窟原舞复原'; do
  ! rg -qF "$forbidden_claim" "$readme" || { print -u2 -r -- "FAIL: README contains misleading claim $forbidden_claim"; exit 1; }
done

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^feimei-lvyao-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Feimei Lvyao history row is missing or duplicated"; exit 1; }
[[ "$(awk -F, '$1=="feimei-lvyao-15s" {print $19}' "$history_file")" == "designed" ]] || { print -u2 "FAIL: Feimei Lvyao history status must be designed"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in '基础级' '视觉指纹' 'v03' '文件名' '历史复原' '文物复原' '图片2' '真实人物' '艺人' '18岁' '第445窟'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

for negative_expression in '只有一个' '没有其他人物' '不得' '禁止' '不生成' '不要' '不拿' '不抓' '不出现' '无阿砚'; do
  [[ "$prompt_body" != *"$negative_expression"* ]] || { print -u2 -r -- "FAIL: positive prompt body contains negative expression $negative_expression"; exit 1; }
done

print -r -- "PASS: Feimei Lvyao 15s prompt and history are complete"
