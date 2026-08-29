#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
copy_file="$project_dir/episodes/liangzhouci-15s/wechat-channels-copy.md"

[[ -s "$copy_file" ]] || { print -u2 "FAIL: missing Liangzhouci WeChat Channels copy"; exit 1; }

for phrase in \
  "栀夏这一舞，带着阿砚飞过了玉门关" \
  "黄河远上白云间，一片孤城万仞山。" \
  "羌笛何须怨杨柳，春风不度玉门关。" \
  "AI美女舞蹈" \
  "中国古典舞" \
  "原创虚拟角色｜AI辅助制作" \
  "exports/liangzhouci-15s-subtitled-v01.mp4"; do
  rg -qF "$phrase" "$copy_file" || { print -u2 "FAIL: missing required copy phrase: $phrase"; exit 1; }
done

tag_section="$(awk '/^## 话题标签$/{inside=1;next} /^## /{if(inside) exit} inside{print}' "$copy_file")"
tag_count="$(print -r -- "$tag_section" | rg -o '#[^[:space:]#]+' | wc -l | tr -d ' ')"
[[ "$tag_count" == "6" ]] || { print -u2 "FAIL: expected six topic tags, got $tag_count"; exit 1; }

expected_tags="#栀夏飞花令 #王之涣 #凉州词 #AI美女舞蹈 #中国古典舞 #古诗词"
print -r -- "$tag_section" | rg -qF "$expected_tags" || {
  print -u2 "FAIL: topic tags do not match the approved set"
  exit 1
}

if rg -n "Seedance|提示词|模型参数|镜头代码|真人舞者|专业舞蹈演员|全网第一|最美" "$copy_file"; then
  print -u2 "FAIL: forbidden wording remains in release copy"
  exit 1
fi

print "PASS: Liangzhouci WeChat Channels copy is ready"
