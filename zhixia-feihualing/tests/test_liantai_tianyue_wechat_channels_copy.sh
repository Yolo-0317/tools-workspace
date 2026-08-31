#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
copy="$project_dir/episodes/liantai-tianyue-15s/wechat-channels-copy.md"

[[ -s "$copy" ]] || { print -u2 "FAIL: missing Liantai Tianyue WeChat Channels copy"; exit 1; }

for heading in '## 标题' '## 发布正文' '## 话题标签' '## 首评（置顶评论）' '## 发布提醒'; do
  rg -Fqx "$heading" "$copy" || { print -u2 "FAIL: missing section: $heading"; exit 1; }
done

for line in \
  '月光落进石窟，栀夏循着一声钟起舞' \
  '霜清东林钟，' \
  '水白虎溪月。' \
  '天香生虚空，' \
  '天乐鸣不歇。' \
  '原创虚拟角色｜AI辅助制作' \
  '#栀夏飞花令 #敦煌舞 #李白 #庐山东林寺夜怀 #中国古典舞 #古诗词' \
  '敦煌十六舞下一支，你想看哪一种舞？也可以留下相关诗句。'; do
  rg -Fqx "$line" "$copy" || { print -u2 "FAIL: missing exact copy line: $line"; exit 1; }
done

rg -Fq '《栀夏·敦煌十六舞》第六支《莲台天乐》' "$copy"
rg -Fq '原创敦煌供养舞意象' "$copy"
rg -Fq 'exports/liantai-tianyue-15s-subtitled-v01.mp4' "$copy"
rg -Fq 'exports/liantai-tianyue-dance-cover-v01.png' "$copy"
rg -Fq '发布时选择视频号要求的 AI 内容声明' "$copy"

for prohibited in '壁画复原' '古舞复原' '数字敦煌' '文物活化' '非遗传承' '专业舞谱复刻' '官方合作' '真人舞者表演'; do
  ! rg -Fq "$prohibited" "$copy" || { print -u2 "FAIL: prohibited unsupported claim: $prohibited"; exit 1; }
done

print "PASS: Liantai Tianyue WeChat Channels copy is ready"
