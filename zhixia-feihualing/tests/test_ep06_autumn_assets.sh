#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
episode_dir="$project_dir/episodes/ep06"

required_files=(
  "$episode_dir/one-character-two-poems.md"
  "$episode_dir/subtitle-copy.md"
  "$episode_dir/voice-lines.json"
  "$episode_dir/prompts/content-15s.md"
  "$episode_dir/assets/README.md"
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { echo "缺少文件：$file"; exit 1; }
done

rg -q "树树皆秋色，山山唯落晖" "$episode_dir"
rg -q "秋风生渭水，落叶满长安" "$episode_dir"
rg -q "0—1.8秒" "$episode_dir/one-character-two-poems.md"
rg -q "1.8—7.8秒" "$episode_dir/one-character-two-poems.md"
rg -q "7.8—14.6秒" "$episode_dir/one-character-two-poems.md"
rg -q "14.6—15.0秒" "$episode_dir/one-character-two-poems.md"

python3 - "$episode_dir/voice-lines.json" <<'PY'
import json
import pathlib
import sys

data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["episode"] == "ep06"
assert data["theme"] == "秋"
assert data["audio_slug"] == "ep06-autumn"
assert [line["role"] for line in data["lines"]] == ["zhixia", "ayan"]
assert [line["start_ms"] for line in data["lines"]] == [1800, 7800]
assert data["lines"][0]["text"] == "树树皆秋色，山山唯落晖。"
assert data["lines"][1]["text"] == "秋风生渭水，落叶满长安。"
assert all(line["id"] not in {"01-opening", "04-outro"} for line in data["lines"])
PY

prompt="$episode_dir/prompts/content-15s.md"
rg -q "参考图1为栀夏" "$prompt"
rg -q "参考图2为阿砚" "$prompt"
rg -q "第一帧" "$prompt"
rg -q "人物与诗境保持约1:1" "$prompt"
rg -q "不做说话口型" "$prompt"
rg -q "不要生成字幕" "$prompt"
rg -q "0—1.8秒" "$prompt"
rg -q "1.8—7.8秒" "$prompt"
rg -q "7.8—14.6秒" "$prompt"
rg -q "14.6—15.0秒" "$prompt"
! rg -q "两句写秋，第三句" "$episode_dir"
rg -q "15秒" "$prompt"
rg -q "720P" "$prompt"
rg -q "设计中" "$project_dir/episodes/README.md"

echo "EP06秋字素材验证通过"
