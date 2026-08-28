#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
episode="$project_dir/episodes/yesu-shansi"

for required in "$episode/README.md" "$episode/voice-lines.json"; do
  test -s "$required"
done

python3 - "$episode/voice-lines.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)

assert data["episode"] == "yesu-shansi"
assert data["format"] == "one-poem-story"
assert data["audio_slug"] == "yesu-shansi"
lines = data["lines"]
assert len(lines) == 5
assert [line["role"] for line in lines] == ["ayan", "zhixia", "ayan", "zhixia", "ayan"]
assert [line["start_ms"] for line in lines] == [0, 2800, 5400, 8200, 12100]
assert [line["revision"] for line in lines] == [2, 3, 2, 3, 2]
assert [line["text"] for line in lines] == [
    "这楼怎么钻进云里了？",
    "因为我们在山顶呀。",
    "再高些……能摸到星星吗？",
    "轻声些，山顶太静了。",
    "那天上的人……听得见我吗？",
]
PY

test -s "$episode/prompts/scene-cards.md"
for card in \
  01-ayan-frontal-close \
  02-zhixia-frontal-close \
  03-climb-medium \
  04-open-ending-two-shot; do
  file="$episode/assets/scene-cards/$card.png"
  test -s "$file"
  dimensions="$(sips -g pixelWidth -g pixelHeight "$file" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w"x"h}')"
  test "$dimensions" = "720x1280" -o "$dimensions" = "941x1672" -o "$dimensions" = "1024x1536"
done

echo "yesu shansi production package: PASS"
