#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
copy="$project_dir/episodes/huxuan-15s/wechat-channels-copy.md"

[[ -s "$copy" ]] || { print -u2 "FAIL: missing Huxuan WeChat Channels copy"; exit 1; }

for heading in '## 标题' '## 发布正文' '## 话题标签' '## 置顶评论' '## 发布提醒'; do
  rg -q "^${heading}$" "$copy" || { print -u2 "FAIL: missing section: $heading"; exit 1; }
done

for line in \
  '敦煌十六舞第三支，栀夏这一转停不下来了' \
  '弦鼓一声双袖举，' \
  '回雪飘飖转蓬舞。' \
  '左旋右转不知疲，' \
  '千匝万周无已时。' \
  '原创虚拟角色｜AI辅助制作' \
  '#栀夏飞花令 #敦煌舞 #胡旋舞 #白居易 #中国古典舞 #古诗词'; do
  rg -Fqx "$line" "$copy" || { print -u2 "FAIL: missing exact copy line: $line"; exit 1; }
done

rg -q '敦煌十六舞第四支，你想看栀夏跳哪一种舞' "$copy"
rg -q 'exports/huxuan-15s-subtitled-v01.mp4' "$copy"
rg -q 'exports/huxuan-dance-cover-v01.png' "$copy"

for prohibited in '复原唐代舞谱' '还原历史舞台' '非遗传承人编舞' '真人舞者表演'; do
  ! rg -q "$prohibited" "$copy" || { print -u2 "FAIL: prohibited unsupported claim: $prohibited"; exit 1; }
done

print "PASS: Huxuan WeChat Channels copy is ready"
