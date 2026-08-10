#!/usr/bin/env bash
# Copy canonical HP assets from ~/Downloads into harryputter/samples/ (按部 hp01/hp02).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOOK="${BOOK:-hp01}"
DL="${DOWNLOADS:-$HOME/Downloads}"
SOURCES="$ROOT/samples/SOURCES.json"

case "$BOOK" in
  hp01)
    EN_EPUB="$DL/Harry Potter and the Sorcerer's - J.K. Rowling.epub"
    BILINGUAL_EPUB="$DL/中英翻譯對照版1.哈利波特與魔法石-Harry Potter and the Sorcerers Stone (Rowling, J.K.) (z-library.sk, 1lib.sk, z-lib.sk).epub"
    BILINGUAL_PDF="$DL/I哈利·波特与魔法石(中英对照版) (J.K.Rowling) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    AUDIO_SRC="$DL/Harry Potter and the Philosopher's Stone"
    MAX_CH=17
    ;;
  hp02)
    EN_EPUB="$DL/Harry Potter and the Chamber of - J.K. Rowling.epub"
    BILINGUAL_PDF="$DL/II哈利·波特与密室(中英对照版) (J.K.Rowling) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    AUDIO_SRC="$DL/Harry Potter and the Chamber of Secrets"
    MAX_CH=18
    ;;
  *)
    echo "Unknown BOOK=$BOOK (supported: hp01, hp02)" >&2
    exit 1
    ;;
esac

ZH_EPUB="$DL/哈利.波特_珍藏版_七册全_.epub"

copy_if_needed() {
  local src="$1" dst="$2"
  if [[ ! -f "$src" ]]; then
    echo "SKIP missing: $src" >&2
    return 1
  fi
  mkdir -p "$(dirname "$dst")"
  if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
    echo "OK (unchanged) $dst"
  else
    cp "$src" "$dst"
    echo "COPIED → $dst"
  fi
}

mkdir -p "$ROOT/samples/$BOOK" "$ROOT/samples/epub/en" "$ROOT/samples/epub/zh" "$ROOT/samples/epub/bilingual" "$ROOT/samples/pdf/bilingual"
cd "$ROOT"

copy_if_needed "$EN_EPUB" "samples/epub/en/${BOOK}.epub"
copy_if_needed "$ZH_EPUB" "samples/epub/zh/collection.epub"
if [[ -n "${BILINGUAL_EPUB:-}" ]]; then
  copy_if_needed "$BILINGUAL_EPUB" "samples/epub/bilingual/${BOOK}.epub" || true
fi
if [[ -n "${BILINGUAL_PDF:-}" ]]; then
  copy_if_needed "$BILINGUAL_PDF" "samples/pdf/bilingual/${BOOK}.pdf" || true
fi

if [[ -d "$AUDIO_SRC" ]]; then
  for n in $(seq 1 "$MAX_CH"); do
    pad="$(printf '%02d' "$n")"
    src="$(find "$AUDIO_SRC" -maxdepth 1 \( -iname "Chapter ${pad} - *.mp3" -o -iname "Chapter ${n} - *.mp3" -o -iname "Chapter ${pad} -*.mp3" -o -iname "Chapter ${n} -*.mp3" \) 2>/dev/null | head -1)"
    if [[ -z "$src" ]]; then
      echo "WARN: no MP3 for chapter $n in $AUDIO_SRC" >&2
      continue
    fi
    copy_if_needed "$src" "samples/${BOOK}/chapter${pad}.mp3"
  done
else
  echo "WARN: audio folder missing: $AUDIO_SRC" >&2
fi

for f in samples/"$BOOK"/chapter*.mp3; do
  [[ -e "$f" ]] || continue
  [[ -L "$f" ]] || continue
  target="$(python3 -c "import os; print(os.path.realpath('$f'))")"
  case "$target" in
    "$ROOT"/*) ;;
    *)
      echo "Replacing external symlink: $f"
      rm "$f"
      cp "$target" "$f"
      ;;
  esac
done

SOURCES_PATH="$SOURCES" BOOK="$BOOK" MAX_CH="$MAX_CH" EN_EPUB="$EN_EPUB" ZH_EPUB="$ZH_EPUB" BILINGUAL_EPUB="${BILINGUAL_EPUB:-}" BILINGUAL_PDF="${BILINGUAL_PDF:-}" AUDIO_SRC="$AUDIO_SRC" python3 - <<'PY'
import json, hashlib, os
from datetime import date
from pathlib import Path

sources_path = Path(os.environ["SOURCES_PATH"])
book = os.environ["BOOK"]
max_ch = int(os.environ["MAX_CH"])
root = sources_path.parent

def md5(p):
    if not os.path.isfile(p):
        return None
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

chapters = []
for n in range(1, max_ch + 1):
    pad = f"{n:02d}"
    mp3 = root / book / f"chapter{pad}.mp3"
    chapters.append({
        "chapter": n,
        "file": f"samples/{book}/chapter{pad}.mp3",
        "present": mp3.is_file(),
        "bytes": mp3.stat().st_size if mp3.is_file() else None,
        "md5": md5(mp3) if mp3.is_file() else None,
    })

en_epub = root / "epub" / "en" / f"{book}.epub"
zh_epub = root / "epub" / "zh" / "collection.epub"
bilingual_epub = root / "epub" / "bilingual" / f"{book}.epub"
bilingual_pdf = root / "pdf" / "bilingual" / f"{book}.pdf"

doc = {
    "updated": date.today().isoformat(),
    "book_id": book,
    "note": "Canonical copies live here. Do NOT rely on ~/Downloads after import.",
    "original_paths": {
        "en_epub": os.environ["EN_EPUB"],
        "zh_epub": os.environ["ZH_EPUB"],
        "bilingual_epub": os.environ.get("BILINGUAL_EPUB") or None,
        "bilingual_pdf": os.environ.get("BILINGUAL_PDF") or None,
        "audio_dir": os.environ["AUDIO_SRC"],
    },
    "samples": {
        f"epub/en/{book}.epub": {
            "md5": md5(en_epub),
            "bytes": en_epub.stat().st_size if en_epub.is_file() else None,
        },
        "epub/zh/collection.epub": {
            "md5": md5(zh_epub),
            "bytes": zh_epub.stat().st_size if zh_epub.is_file() else None,
        },
        f"epub/bilingual/{book}.epub": {
            "md5": md5(bilingual_epub),
            "bytes": bilingual_epub.stat().st_size if bilingual_epub.is_file() else None,
        },
        f"pdf/bilingual/{book}.pdf": {
            "md5": md5(bilingual_pdf),
            "bytes": bilingual_pdf.stat().st_size if bilingual_pdf.is_file() else None,
        },
    },
    "chapters": chapters,
}
sources_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
ready = sum(1 for c in chapters if c["present"])
print(f"Wrote {sources_path} — {ready}/{max_ch} MP3 in samples/{book}/")
PY

echo "Done. See samples/SOURCES.json and docs/SAMPLES.md"
