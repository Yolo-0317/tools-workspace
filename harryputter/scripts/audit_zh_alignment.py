#!/usr/bin/env python3
"""Quick audit: missing ZH, consecutive duplicate ZH, triple-repeat long ZH."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from chapters import manifest_path  # noqa: E402


def audit_chapter(book_id: str, ch: int) -> dict:
    m = json.loads(manifest_path(book_id, ch).read_text(encoding="utf-8"))
    lines = m.get("lines", [])
    body = [ln for ln in lines if ln.get("kind") != "heading"]
    no_zh = sum(1 for ln in body if not (ln.get("zh") or "").strip())
    consec = sum(
        1
        for i in range(1, len(lines))
        if lines[i].get("zh") and lines[i].get("zh") == lines[i - 1].get("zh")
    )
    long_zh = [ln.get("zh", "") for ln in lines if ln.get("zh") and len(ln.get("zh", "")) > 30]
    dup3 = sum(1 for _, c in Counter(long_zh).items() if c >= 3)
    merged = sum(1 for ln in lines if ln.get("merged_count"))
    return {
        "chapter": ch,
        "lines": len(lines),
        "no_zh": no_zh,
        "consec_dup": consec,
        "dup3_long": dup3,
        "merged_rows": merged,
        "method": m.get("translation_method", ""),
        "ok": no_zh == 0 and consec == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--from", dest="from_ch", type=int, default=1)
    parser.add_argument("--to", type=int, default=17)
    args = parser.parse_args()

    rows = [audit_chapter(args.book, ch) for ch in range(args.from_ch, args.to + 1)]
    fail = [r for r in rows if not r["ok"]]
    print(f"=== {args.book} ch{args.from_ch:02d}–ch{args.to:02d} ZH alignment ===\n")
    for r in rows:
        flag = "OK  " if r["ok"] else "FAIL"
        print(
            f"{flag} Ch{r['chapter']:02d}: lines={r['lines']} no_zh={r['no_zh']} "
            f"consec_dup={r['consec_dup']} dup3={r['dup3_long']} merged={r['merged_rows']}"
        )
    print(f"\nSummary: {len(rows) - len(fail)}/{len(rows)} pass (no_zh=0, consec_dup=0)")
    if fail:
        print("Fail:", [r["chapter"] for r in fail])


if __name__ == "__main__":
    main()
