#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/liantai-tianyue-15s/README.md"
prompt="$project_dir/episodes/liantai-tianyue-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Liantai Tianyue component $required"; exit 1; }
done

for required_text in \
  '参考上传图片中的栀夏' \
  '0.000—0.500秒' \
  '0.500—0.800秒' \
  '0.800—1.800秒' \
  '4.800—7.000秒' \
  '10.000—13.200秒' \
  '纵向应钟' \
  '横向追月' \
  '纵深迎乐' \
  '向上拔高的窄柱' \
  '贴近地面的横向薄带' \
  '由近向斜前方延伸的长线' \
  '左右上臂后外侧' \
  '沿原轴迎面推近' \
  '13.200—15.000秒' \
  '声音仅包含钟声、箜篌、低沉鼓点、衣料声、脚步声与石窟空间回响'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }

for required_text in \
  '霜清东林钟' \
  '天乐鸣不歇' \
  '近处璎珞与指尖' \
  '上方天窗月影' \
  '斜前上方不可见的天乐来处' \
  '0.800 秒前恢复完整全身' \
  '回退为第一帧完整全身强起势' \
  '原创敦煌供养舞意象' \
  '约 68%—72%'; do
  rg -qF "$required_text" "$readme" || { print -u2 -r -- "FAIL: README lacks $required_text"; exit 1; }
done

for forbidden_claim in '历史舞谱复原' '壁画舞姿复原' 'AI活化文物' '数字敦煌复原' '某窟原舞复原'; do
  ! rg -qF "$forbidden_claim" "$readme" || { print -u2 -r -- "FAIL: README contains misleading claim $forbidden_claim"; exit 1; }
done

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^liantai-tianyue-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Liantai Tianyue history row is missing or duplicated"; exit 1; }
[[ "$(awk -F, '$1=="liantai-tianyue-15s" {print $19}' "$history_file")" == "designed" ]] || { print -u2 "FAIL: Liantai Tianyue history status must be designed"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in '基础级' '视觉指纹' 'v03' '文件名' '历史复原' '文物复原' '图片2' '真实人物' '艺人' '18岁'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

for negative_expression in '只有一个' '没有其他人物' '不得' '禁止' '不生成' '不要' '不拿' '不抓' '不出现' '无阿砚'; do
  [[ "$prompt_body" != *"$negative_expression"* ]] || { print -u2 -r -- "FAIL: positive prompt body contains negative expression $negative_expression"; exit 1; }
done

print -r -- "PASS: Liantai Tianyue 15s prompt and history are complete"
