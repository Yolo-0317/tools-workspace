#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/xuexiu-baizhu-15s/README.md"
prompt="$project_dir/episodes/xuexiu-baizhu-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Xuexiu Baizhu component $required"; exit 1; }
done

for required_text in \
  '参考上传图片中的栀夏' \
  '三次高能舞姿同等强烈' \
  '0.000—1.800秒' \
  '4.800—7.000秒' \
  '10.000—13.200秒' \
  '纵向掩袖冲顶' \
  '横向双袖交剪' \
  '纵深折腰再独立' \
  '沿立柱向上拔高' \
  '横扫左右壁面' \
  '沿舞坪由远及近' \
  '左右上臂后外侧' \
  '第三段保持近距离并短促微推' \
  '13.200—15.000秒' \
  '无人声敦煌乐舞配乐'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }
rg -qF '吴刀剪彩缝舞衣' "$readme" || { print -u2 "FAIL: README lacks opening poem line"; exit 1; }
rg -qF '倾城独立世所稀' "$readme" || { print -u2 "FAIL: README lacks final poem line"; exit 1; }
rg -qF '68%—72%' "$readme" || { print -u2 "FAIL: README lacks first peak scale"; exit 1; }
rg -qF '66%—71%' "$readme" || { print -u2 "FAIL: README lacks second peak scale"; exit 1; }
rg -qF '68%—73%' "$readme" || { print -u2 "FAIL: README lacks third peak scale"; exit 1; }
rg -qF '13—15 秒不得低于约 60%' "$readme" || { print -u2 "FAIL: README lacks ending scale"; exit 1; }

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^xuexiu-baizhu-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Xuexiu Baizhu history row is missing or duplicated"; exit 1; }
[[ "$(awk -F, '$1=="xuexiu-baizhu-15s" {print $19}' "$history_file")" == "designed" ]] || { print -u2 "FAIL: Xuexiu Baizhu history status must be designed"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in '基础级' '视觉指纹' 'v03' '文件名' '历史复原' '图片2' '真实人物' '艺人' '18岁'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

for negative_expression in '只有一个' '没有其他人物' '不得' '禁止' '不生成' '不要' '不拿' '不抓' '不出现' '无阿砚'; do
  [[ "$prompt_body" != *"$negative_expression"* ]] || { print -u2 -r -- "FAIL: positive prompt body contains negative expression $negative_expression"; exit 1; }
done

print -r -- "PASS: Xuexiu Baizhu 15s prompt and history are complete"
