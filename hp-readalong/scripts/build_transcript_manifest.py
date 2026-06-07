#!/usr/bin/env python3
"""Build a read-along manifest directly from cached whisper segments (best sync)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "manifests" / "chapter01_whisper.json"
OUT = ROOT / "manifests" / "chapter01_transcript.json"
INTRO_END = 12.0  # skip title / author / chapter heading


def main() -> None:
    data = json.loads(CACHE.read_text(encoding="utf-8"))
    segments = data["segments"]
    lines = [
        {
            "text": s["text"].strip(),
            "start": round(s["start"], 3),
            "end": round(s["end"], 3),
        }
        for s in segments
        if s["end"] > INTRO_END and s["text"].strip()
    ]
    manifest = {
        "title": "Chapter 1 — The Boy Who Lived (transcript)",
        "audio": "samples/chapter01.mp3",
        "duration": data["duration"],
        "aligned_lines": len(lines),
        "source": "faster-whisper segments",
        "lines": lines,
    }
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} — {len(lines)} lines")


if __name__ == "__main__":
    main()
