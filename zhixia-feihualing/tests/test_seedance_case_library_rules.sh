#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LIBRARY_DIR="$PROJECT_DIR/docs/seedance-case-library"
PHASE="${CASE_LIBRARY_PHASE:-final}"

required_files=(
  README.md
  01-characters-and-portraits.md
  02-multi-character-interaction.md
  03-dance-and-body-movement.md
  04-action-and-performance.md
  05-landscape-and-environment.md
  06-camera-and-one-take.md
  07-effects-and-physics.md
  08-sound-dialogue-and-rhythm.md
  09-multimodal-reference.md
  camera-phrases.md
  character-dance-phrases.md
)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for filename in "${required_files[@]}"; do
  [[ -f "$LIBRARY_DIR/$filename" ]] || fail "missing docs/seedance-case-library/$filename"
done

rg -q 'docs/seedance-case-library/README.md' "$PROJECT_DIR/README.md" \
  || fail "project README is missing the case-library navigation link"

if [[ "$PHASE" == "scaffold" ]]; then
  echo "PASS: Seedance case-library scaffold is complete"
  exit 0
fi

case_files=("$LIBRARY_DIR"/0[1-9]-*.md)
headings="$(rg --no-filename '^## CASE-[0-9]{3} ' "${case_files[@]}" || true)"
case_count="$(printf '%s\n' "$headings" | awk 'NF { count++ } END { print count + 0 }')"
(( case_count >= 60 )) || fail "expected at least 60 unique cases, found $case_count"

ids="$(printf '%s\n' "$headings" | sed -E 's/^## (CASE-[0-9]{3}).*/\1/' | awk 'NF')"
duplicates="$(printf '%s\n' "$ids" | sort | uniq -d)"
[[ -z "$duplicates" ]] || fail "duplicate case IDs: $duplicates"

required_fields=(
  '来源'
  '证据等级'
  '输入方式'
  '中文结构化改写'
  '可复用写法'
  '失败风险'
  '栀夏适用性'
)

for file in "${case_files[@]}"; do
  while IFS=: read -r start heading; do
    [[ -n "$start" ]] || continue
    next="$(awk -v begin="$start" 'NR > begin && /^## CASE-[0-9][0-9][0-9] / { print NR; exit }' "$file")"
    if [[ -n "$next" ]]; then
      end=$((next - 1))
    else
      end="$(wc -l < "$file")"
    fi
    block="$(sed -n "${start},${end}p" "$file")"
    id="$(sed -E 's/^## (CASE-[0-9]{3}).*/\1/' <<< "$heading")"
    for field in "${required_fields[@]}"; do
      rg -q "^- \\*\\*${field}：\\*\\*" <<< "$block" || fail "$id in ${file##*/} is missing field: $field"
    done
    rg -q '^- \*\*来源：\*\* \[[^]]+\]\(https?://[^)]+\)' <<< "$block" \
      || fail "$id in ${file##*/} has no direct HTTP source link"
    rg -q '^- \*\*证据等级：\*\* [ABC]$' <<< "$block" \
      || fail "$id in ${file##*/} has an invalid evidence grade"
  done < <(rg -n '^## CASE-[0-9]{3} ' "$file" || true)
done

all_case_text="$(cat "${case_files[@]}")"
for phrase_file in "$LIBRARY_DIR/camera-phrases.md" "$LIBRARY_DIR/character-dance-phrases.md"; do
  phrase_count="$(rg -c '^## PHRASE-[A-Z]+-[0-9]{2} ' "$phrase_file" || true)"
  phrase_count="${phrase_count:-0}"
  (( phrase_count >= 8 )) || fail "${phrase_file##*/} must contain at least 8 reusable phrases, found $phrase_count"
  while read -r id; do
    [[ -n "$id" ]] || continue
    case_block="$(awk -v target="$id" '
      $0 ~ "^## " target " " { found=1 }
      found && $0 ~ /^## CASE-[0-9][0-9][0-9] / && $0 !~ target { exit }
      found { print }
    ' <<< "$all_case_text")"
    [[ -n "$case_block" ]] || fail "${phrase_file##*/} references missing case $id"
    rg -q '^- \*\*证据等级：\*\* [AB]$' <<< "$case_block" \
      || fail "${phrase_file##*/} references non-A/B case $id"
  done < <(rg -o 'CASE-[0-9]{3}' "$phrase_file" | sort -u || true)
done

echo "PASS: Seedance case library has $case_count validated cases"
