#!/bin/zsh
set -euo pipefail

root="${0:A:h:h}"
base="$root/episodes/jiangxue/assets/images/cover-base-v01.png"
final="$root/episodes/jiangxue/assets/images/cover-final-v01.png"
exported="$root/exports/jiangxue-cover.png"
renderer="$root/scripts/render_jiangxue_cover.swift"

for file in "$base" "$final" "$exported" "$renderer"; do
  [[ -f "$file" ]] || { print -u2 "缺少文件：$file"; exit 1; }
done

for file in "$base" "$final" "$exported"; do
  width="$(sips -g pixelWidth "$file" | awk '/pixelWidth/ {print $2}')"
  height="$(sips -g pixelHeight "$file" | awk '/pixelHeight/ {print $2}')"
  [[ "$width" == "720" ]]
  [[ "$height" == "1280" ]]
done

cmp -s "$final" "$exported"
cmp -s "$base" "$final" && { print -u2 "最终封面不能与底图相同"; exit 1; }

grep -q '诗词小故事' "$renderer"
grep -q '孤舟蓑笠翁' "$renderer"
grep -q '独钓寒江雪' "$renderer"
grep -q '唐·柳宗元《江雪》' "$renderer"
! grep -q '他怎么还不收竿' "$renderer"
grep -q 'STXingkaiSC-Bold' "$renderer"
grep -q 'STKaitiSC-Regular' "$renderer"
grep -q '228.0 / 255.0' "$renderer"
grep -q '215.0 / 255.0' "$renderer"
grep -q '192.0 / 255.0' "$renderer"
! grep -q '\.strokeColor' "$renderer"

print "PASS: 江雪视频号封面"
