#!/usr/bin/env python3
"""
Bootstrap bilingual_clips from a verified manifest (en text + zh already correct).

Usage:
  python3 scripts/export_bilingual_clips.py --book hp01 --chapter 1
"""

from __future__ import annotations

import argparse
import json

from bilingual_clips import fixes_path, load_fixes
from chapters import manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--chapter", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(manifest_path(args.book, args.chapter).read_text(encoding="utf-8"))
    clips: list[dict] = []
    for line in manifest.get("lines", []):
        en = (line.get("text") or "").strip()
        zh = (line.get("zh") or "").strip()
        if not en:
            continue
        clip: dict = {"en": en, "zh": zh}
        if line.get("kind") == "heading":
            clip["kind"] = "heading"
        clips.append(clip)

    fixes = load_fixes(args.book, args.chapter) or {
        "comment": f"{args.book} ch{args.chapter:02d} · bilingual clips",
        "en_to_zh_text": {},
        "line_splits": [],
        "line_zh_overrides": [],
    }
    fixes["comment"] = f"{args.book} ch{args.chapter:02d} · bilingual_clips (Agent en+zh, program audio)"
    fixes["bilingual_clips"] = clips
    fixes.setdefault("line_splits", [])
    fixes.setdefault("line_zh_overrides", [])

    if args.dry_run:
        print(json.dumps(clips[:3], ensure_ascii=False, indent=2))
        print(f"... {len(clips)} clips total")
        return

    path = fixes_path(args.book, args.chapter)
    path.write_text(json.dumps(fixes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path} — {len(clips)} bilingual_clips")


if __name__ == "__main__":
    main()
