#!/bin/zsh
set -euo pipefail

root="${0:A:h:h}"
base="$root/episodes/ep08/assets/images/cover-base-v01.png"
final="$root/episodes/ep08/assets/images/cover-final-v01.png"
exported="$root/exports/ep08-flute-cover.png"

test -f "$base"
test -f "$final"
test -f "$exported"
cmp -s "$final" "$exported"

dims=$(sips -g pixelWidth -g pixelHeight "$final" 2>/dev/null)
print -r -- "$dims" | grep -q "pixelWidth: 941"
print -r -- "$dims" | grep -q "pixelHeight: 1672"
cmp -s "$base" "$final" && { print -u2 "final cover must differ from base"; exit 1; }

grep -q '笛字飞花令' "$root/scripts/render_ep08_flute_cover.swift"
grep -q '第四句等你' "$root/scripts/render_ep08_flute_cover.swift"
print "PASS: EP08 flute cover has the reusable two-column comment hook"
