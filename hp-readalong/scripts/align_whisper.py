#!/usr/bin/env python3
"""
Align Chapter 1 MP3 to EPUB chapter-1 paragraphs (faster-whisper + sequential mapping).

One audio file ↔ one EPUB chapter. No Ollama.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm(text: str) -> str:
    text = text.lower()
    text = text.replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[^a-z0-9'\s-]", " ", text)
    return " ".join(text.split())


def _tokens(text: str) -> list[str]:
    return [t for t in _norm(text).split() if t]


def _overlap_score(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    ordered = 0
    bi = 0
    for tok in ta:
        for j in range(bi, len(tb)):
            if tb[j] == tok:
                ordered += 1
                bi = j + 1
                break
    ord_ratio = ordered / len(ta)
    sa, sb = set(ta), set(tb)
    set_ratio = len(sa & sb) / max(len(sa), len(sb))
    return 0.55 * ord_ratio + 0.45 * set_ratio


def _find_body_start(segments: list[dict], first_paragraph: str) -> int:
    probe = " ".join(_tokens(first_paragraph)[:10])
    best_i, best = 0, 0.0
    for i, seg in enumerate(segments):
        score = _overlap_score(probe, seg["text"])
        if score > best:
            best, best_i = score, i
    return best_i


def _map_units(units: list[str], segments: list[dict], start_idx: int) -> list[dict]:
    """Map each text unit (sentence) to consecutive whisper segments in reading order."""
    lines: list[dict] = []
    seg_i = start_idx

    for unit in units:
        if seg_i >= len(segments):
            break
        target = len(_tokens(unit))
        if target == 0:
            continue

        chunk_texts: list[str] = []
        spoken = 0
        start = segments[seg_i]["start"]
        end = segments[seg_i]["end"]

        while seg_i < len(segments):
            chunk_texts.append(segments[seg_i]["text"].strip())
            spoken += len(_tokens(segments[seg_i]["text"]))
            end = segments[seg_i]["end"]
            seg_i += 1
            if spoken >= max(3, int(target * 0.7)):
                break
            if len(chunk_texts) >= 6:
                break

        transcript = " ".join(chunk_texts)
        score = _overlap_score(unit, transcript)
        lines.append(
            {
                "text": unit,
                "start": round(start, 3),
                "end": round(end, 3),
                "transcript": transcript,
                "confidence": round(score, 3),
            }
        )

    return lines


def transcribe(mp3: Path, model: str, cache: Path) -> tuple[list[dict], float]:
    if cache.is_file():
        data = json.loads(cache.read_text(encoding="utf-8"))
        print(f"Using cached transcript: {cache}")
        return data["segments"], float(data["duration"])

    from faster_whisper import WhisperModel

    print("Running faster-whisper (first run ~5 min for a 32-min chapter) …")
    whisper = WhisperModel(model, device="cpu", compute_type="int8")
    segments_iter, info = whisper.transcribe(
        str(mp3),
        language="en",
        word_timestamps=True,
        vad_filter=True,
    )
    segments = [
        {"start": float(seg.start), "end": float(seg.end), "text": seg.text.strip()}
        for seg in segments_iter
    ]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(
            {"duration": float(info.duration), "segments": segments},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Cached transcript → {cache}")
    return segments, float(info.duration)


def main() -> None:
    parser = argparse.ArgumentParser(description="Align chapter-1 MP3 to EPUB chapter 1")
    parser.add_argument("--audio", type=Path, default=ROOT / "samples" / "chapter01.mp3")
    parser.add_argument("--text", type=Path, default=ROOT / "manifests" / "chapter01_text.json")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "manifests" / "chapter01.json")
    parser.add_argument(
        "--cache",
        type=Path,
        default=ROOT / "manifests" / "chapter01_whisper.json",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("WHISPER_MODEL", str(Path.home() / ".cache/faster-whisper-small")),
    )
    args = parser.parse_args()

    text_data = json.loads(args.text.read_text(encoding="utf-8"))
    units = text_data["sentences"]

    segments, duration = transcribe(args.audio, args.model, args.cache)
    start_idx = _find_body_start(segments, units[0])
    print(
        f"Chapter 1 · audio {duration / 60:.1f} min · {len(segments)} segments · "
        f"body @ {segments[start_idx]['start']:.1f}s · {len(units)} sentences"
    )

    lines = _map_units(units, segments, start_idx)
    manifest = {
        "title": f"Chapter {text_data['chapter']} — {text_data['title']}",
        "audio": "samples/chapter01.mp3",
        "duration": round(duration, 3),
        "aligned_lines": len(lines),
        "total_sentences": len(units),
        "intro_skipped_to_sec": round(segments[start_idx]["start"], 3),
        "lines": lines,
    }
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    avg_conf = sum(l["confidence"] for l in lines) / max(len(lines), 1)
    print(f"Wrote {args.output} — {len(lines)} sentences, avg confidence {avg_conf:.2f}")


if __name__ == "__main__":
    main()
