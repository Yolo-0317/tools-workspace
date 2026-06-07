#!/usr/bin/env bash
# Copy canonical HP1 assets from ~/Downloads into readalong/samples/ (按部 hp01).
# Safe to re-run (skips identical files via cmp when possible).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOOK="${BOOK:-hp01}"
DL="${DOWNLOADS:-$HOME/Downloads}"
AUDIO_SRC="$DL/Harry Potter and the Philosopher's Stone"
SOURCES="$ROOT/samples/SOURCES.json"

EN_EPUB="$DL/Harry Potter and the Sorcerer's - J.K. Rowling.epub"
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

mkdir -p "$ROOT/samples/$BOOK" "$ROOT/samples/epub/en" "$ROOT/samples/epub/zh"
cd "$ROOT"

copy_if_needed "$EN_EPUB" "samples/epub/en/${BOOK}.epub"
copy_if_needed "$ZH_EPUB" "samples/epub/zh/collection.epub"

if [[ -d "$AUDIO_SRC" ]]; then
  for n in $(seq 1 17); do
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

# Remove external symlinks (static server cannot serve them)
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

# Migrate legacy flat layout if present
if [[ -f samples/book.epub ]] && [[ ! -f samples/epub/en/${BOOK}.epub ]]; then
  echo "Migrating samples/book.epub → samples/epub/en/${BOOK}.epub"
  cp samples/book.epub "samples/epub/en/${BOOK}.epub"
fi
if [[ -f samples/book_zh.epub ]] && [[ ! -f samples/epub/zh/collection.epub ]]; then
  echo "Migrating samples/book_zh.epub → samples/epub/zh/collection.epub"
  cp samples/book_zh.epub samples/epub/zh/collection.epub
fi
for n in $(seq 1 17); do
  pad="$(printf '%02d' "$n")"
  legacy="samples/chapter${pad}.mp3"
  dest="samples/${BOOK}/chapter${pad}.mp3"
  if [[ -f "$legacy" ]] && [[ ! -f "$dest" ]]; then
    echo "Migrating $legacy → $dest"
    cp "$legacy" "$dest"
  fi
done

SOURCES_PATH="$SOURCES" BOOK="$BOOK" EN_EPUB="$EN_EPUB" ZH_EPUB="$ZH_EPUB" AUDIO_SRC="$AUDIO_SRC" python3 - <<'PY'
import json, hashlib, os
from datetime import date
from pathlib import Path

sources_path = Path(os.environ["SOURCES_PATH"])
book = os.environ["BOOK"]
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
for n in range(1, 18):
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

doc = {
    "updated": date.today().isoformat(),
    "book_id": book,
    "note": "Canonical copies live here. Do NOT rely on ~/Downloads after import.",
    "original_paths": {
        "en_epub": os.environ["EN_EPUB"],
        "zh_epub": os.environ["ZH_EPUB"],
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
    },
    "chapters": chapters,
}
sources_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
ready = sum(1 for c in chapters if c["present"])
print(f"Wrote {sources_path} — {ready}/17 MP3 in samples/{book}/")
PY

echo "Done. See samples/SOURCES.json and docs/SAMPLES.md"
