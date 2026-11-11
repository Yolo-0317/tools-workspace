#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp_dir="$(mktemp -d /tmp/zhixia-story-subtitles.XXXXXX)"
trap 'rm -rf "$tmp_dir"' EXIT

export CLANG_MODULE_CACHE_PATH="$tmp_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$tmp_dir/swift-module-cache"
swift "$project_dir/scripts/render_story_subtitle_cards.swift" \
  "$project_dir/episodes/wen-liu-shijiu/subtitle-plan.json" "$tmp_dir/cards"

for card in 01-opening-dialogue 02-original-dialogue 03-poem-voiceover; do
  test -s "$tmp_dir/cards/$card.png"
  dimensions="$(sips -g pixelWidth -g pixelHeight "$tmp_dir/cards/$card.png" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w"x"h}')"
  test "$dimensions" = "720x1280"
done

swift "$project_dir/scripts/render_story_subtitle_cards.swift" \
  "$project_dir/episodes/lushan/subtitle-plan.json" "$tmp_dir/lushan-cards"

for card in 01-ayan-dialogue 02-zhixia-dialogue 03-ayan-dialogue 04-zhixia-dialogue 05-ayan-poem; do
  test -s "$tmp_dir/lushan-cards/$card.png"
  dimensions="$(sips -g pixelWidth -g pixelHeight "$tmp_dir/lushan-cards/$card.png" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w"x"h}')"
  test "$dimensions" = "720x1280"
done

dialogue_bottom_alpha="$(ffmpeg -v error -i "$tmp_dir/lushan-cards/01-ayan-dialogue.png" \
  -vf 'crop=720:320:0:800,alphaextract,signalstats,metadata=print:file=-' -frames:v 1 -f null - 2>&1 \
  | awk -F= '/lavfi.signalstats.YAVG/{print $2; exit}')"
dialogue_top_alpha="$(ffmpeg -v error -i "$tmp_dir/lushan-cards/01-ayan-dialogue.png" \
  -vf 'crop=720:500:0:0,alphaextract,signalstats,metadata=print:file=-' -frames:v 1 -f null - 2>&1 \
  | awk -F= '/lavfi.signalstats.YAVG/{print $2; exit}')"
poem_left_alpha="$(ffmpeg -v error -i "$tmp_dir/lushan-cards/05-ayan-poem.png" \
  -vf 'crop=300:850:0:0,alphaextract,signalstats,metadata=print:file=-' -frames:v 1 -f null - 2>&1 \
  | awk -F= '/lavfi.signalstats.YAVG/{print $2; exit}')"
poem_right_alpha="$(ffmpeg -v error -i "$tmp_dir/lushan-cards/05-ayan-poem.png" \
  -vf 'crop=300:850:420:0,alphaextract,signalstats,metadata=print:file=-' -frames:v 1 -f null - 2>&1 \
  | awk -F= '/lavfi.signalstats.YAVG/{print $2; exit}')"

awk -v v="$dialogue_bottom_alpha" 'BEGIN { exit !(v > 1.0) }'
awk -v v="$dialogue_top_alpha" 'BEGIN { exit !(v < 0.05) }'
awk -v v="$poem_left_alpha" 'BEGIN { exit !(v > 1.0) }'
awk -v v="$poem_right_alpha" 'BEGIN { exit !(v < 0.05) }'

echo "story subtitle cards: PASS"
