#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp_dir="$(mktemp -d /tmp/zhixia-cyber-cards.XXXXXX)"
trap 'rm -rf "$tmp_dir"' EXIT

export CLANG_MODULE_CACHE_PATH="$tmp_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$tmp_dir/swift-module-cache"
swift "$project_dir/scripts/render_cyber_divination_cards.swift" \
  "$project_dir/episodes/cyber-divination-ep01/subtitle-plan.json" "$tmp_dir/cards"

for card in \
  01-ayan-question \
  03-zhixia-hexagram \
  04-zhixia-reading \
  05-ayan-hope \
  06-zhixia-reveal \
  07-ayan-excuse \
  08-disclaimer \
  09-series-title; do
  test -s "$tmp_dir/cards/$card.png"
  dimensions="$(sips -g pixelWidth -g pixelHeight "$tmp_dir/cards/$card.png" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w"x"h}')"
  test "$dimensions" = "720x1280"
done

hexagram_center_alpha="$(ffmpeg -v error -i "$tmp_dir/cards/03-zhixia-hexagram.png" \
  -vf 'crop=520:520:100:240,alphaextract,signalstats,metadata=print:file=-' -frames:v 1 -f null - 2>&1 \
  | awk -F= '/lavfi.signalstats.YAVG/{print $2; exit}')"
disclaimer_bottom_alpha="$(ffmpeg -v error -i "$tmp_dir/cards/08-disclaimer.png" \
  -vf 'crop=640:130:40:1110,alphaextract,signalstats,metadata=print:file=-' -frames:v 1 -f null - 2>&1 \
  | awk -F= '/lavfi.signalstats.YAVG/{print $2; exit}')"
title_top_alpha="$(ffmpeg -v error -i "$tmp_dir/cards/09-series-title.png" \
  -vf 'crop=520:170:100:60,alphaextract,signalstats,metadata=print:file=-' -frames:v 1 -f null - 2>&1 \
  | awk -F= '/lavfi.signalstats.YAVG/{print $2; exit}')"
dialogue_bottom_alpha="$(ffmpeg -v error -i "$tmp_dir/cards/01-ayan-question.png" \
  -vf 'crop=720:320:0:800,alphaextract,signalstats,metadata=print:file=-' -frames:v 1 -f null - 2>&1 \
  | awk -F= '/lavfi.signalstats.YAVG/{print $2; exit}')"

awk -v v="$hexagram_center_alpha" 'BEGIN { exit !(v > 1.0) }'
awk -v v="$disclaimer_bottom_alpha" 'BEGIN { exit !(v > 0.3) }'
awk -v v="$title_top_alpha" 'BEGIN { exit !(v > 0.5) }'
awk -v v="$dialogue_bottom_alpha" 'BEGIN { exit !(v > 1.0) }'

echo "cyber divination cards: PASS"
