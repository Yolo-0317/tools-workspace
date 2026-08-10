#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOOK="${BOOK:-hp01}"
CH="${1:?usage: pipeline.sh <chapter_num>  (env BOOK=hp01)}"
CH_PAD="$(printf '%02d' "$CH")"

cd "$ROOT"
mkdir -p "samples/${BOOK}" "samples/epub/en" "samples/epub/zh" "output/${BOOK}"

EN_EPUB="samples/epub/en/${BOOK}.epub"
ZH_EPUB="samples/epub/zh/collection.epub"
BILINGUAL_PDF="samples/pdf/bilingual/${BOOK}.pdf"
BILINGUAL_EPUB="samples/epub/bilingual/${BOOK}.epub"
MP3="samples/${BOOK}/chapter${CH_PAD}.mp3"

if [[ ! -f "$MP3" ]]; then
  echo "Missing $MP3" >&2
  echo "Run: BOOK=$BOOK ./scripts/import_downloads.sh" >&2
  exit 1
fi
if [[ -f "$BILINGUAL_PDF" ]]; then
  echo "Using bilingual PDF (paragraph): $BILINGUAL_PDF"
elif [[ -f "$BILINGUAL_EPUB" ]]; then
  echo "Using bilingual EPUB (paragraph): $BILINGUAL_EPUB"
elif [[ ! -f "$EN_EPUB" || ! -f "$ZH_EPUB" ]]; then
  echo "Missing bilingual PDF/EPUB or EN+ZH epubs" >&2
  echo "Run: BOOK=$BOOK ./scripts/import_downloads.sh" >&2
  exit 1
fi

if [[ -L "$MP3" ]]; then
  target="$(python3 -c "import os; print(os.path.realpath('$MP3'))")"
  case "$target" in
    "$ROOT"/*) ;;
    *)
      echo "Inlining external audio symlink → $MP3"
      cp "$target" "$MP3"
      ;;
  esac
fi

if [[ -d "$ROOT/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
elif [[ -d "$ROOT/../english-buddy/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/../english-buddy/.venv/bin/activate"
fi

if [[ -f "$BILINGUAL_PDF" || -f "$BILINGUAL_EPUB" ]]; then
  python3 scripts/extract_bilingual.py --book "$BOOK" --chapter "$CH"
else
  python3 scripts/extract_sentences.py --book "$BOOK" --chapter "$CH" -o "output/${BOOK}/ch${CH_PAD}_sentences.json"
  python3 scripts/extract_chinese.py --book "$BOOK" --chapter "$CH" -o "output/${BOOK}/ch${CH_PAD}_zh.json"
fi
python3 scripts/align_words.py --book "$BOOK" --chapter "$CH"
python3 scripts/attach_translation.py --book "$BOOK" --chapter "$CH"
python3 scripts/build_catalog.py
python3 scripts/verify_chapter.py --book "$BOOK" --chapter "$CH" || true
echo "Done. Preview: http://127.0.0.1:8791/web/"
