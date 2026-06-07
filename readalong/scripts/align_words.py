#!/usr/bin/env python3
"""
Sentence-level forced alignment: EPUB sentences ↔ faster-whisper word timestamps.

Monotonic walk: each sentence maps to a contiguous word span in the transcript.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ascii_quotes(text: str) -> str:
    return (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u2032", "'")
        .replace("\u2014", " ")
        .replace("\u2013", " ")
    )


def _norm(token: str) -> str:
    t = _ascii_quotes(token).lower().strip()
    t = re.sub(r"^[^a-z0-9']+|[^a-z0-9']+$", "", t)
    return t


def _tokens(text: str) -> list[str]:
    text = _ascii_quotes(text)
    raw = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?", text)
    return [_norm(x) for x in raw if _norm(x)]


def _word_tokens(word: str) -> list[str]:
    """Expand a whisper token (may contain dashes / punctuation) to match tokens."""
    cleaned = word.replace("—", " ").replace("–", " ").replace("-", " ")
    cleaned = re.sub(r"[^A-Za-z0-9' ]+", " ", cleaned)
    out: list[str] = []
    for piece in cleaned.split():
        out.extend(_tokens(piece))
    return out


def _lcs_ratio(a: list[str], b: list[str]) -> float:
    if not a:
        return 1.0 if not b else 0.0
    # LCS length / len(a) — sentence should appear in order inside spoken words.
    i = j = matched = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            matched += 1
            i += 1
            j += 1
        else:
            j += 1
    return matched / len(a)


def _find_body_word_index(words: list[dict]) -> int:
    """Skip audiobook intro; body starts at 'Mr. and Mrs. Dursley'."""
    target = ["mr", "and", "mrs", "dursley"]
    for i in range(max(0, len(words) - len(target))):
        chunk = [_norm(words[i + k]["word"]) for k in range(len(target))]
        if chunk == target:
            return i
    return 0


def _fuzzy_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    # US/UK spelling & STT quirks
    pairs = {
        ("mustache", "moustache"),
        ("blonde", "blond"),
        ("dursleyish", "undursleyish"),
        ("sorcerers", "philosophers"),
        ("sorcerer's", "philosopher's"),
    }
    return (a, b) in pairs or (b, a) in pairs


def _match_sentence_tokens(
    sent_tokens: list[str], words: list[dict], start_i: int
) -> tuple[int, int, float] | None:
    """Find ordered token subsequence in word stream; return word indices + coverage."""
    if not sent_tokens or start_i >= len(words):
        return None

    ti = 0
    first_i = last_i = start_i
    max_lookahead = max(len(sent_tokens) * 6, 40)

    for j in range(start_i, min(len(words), start_i + max_lookahead)):
        w_tokens = _word_tokens(words[j]["word"])
        if not w_tokens:
            continue
        matched_any = False
        for w in w_tokens:
            if ti < len(sent_tokens) and _fuzzy_eq(w, sent_tokens[ti]):
                if ti == 0:
                    first_i = j
                last_i = j
                ti += 1
                matched_any = True
                if ti >= len(sent_tokens):
                    break
        if ti >= len(sent_tokens):
            break
        if not matched_any and ti > 0:
            # Allow skipping stray filler words in the audio stream.
            continue

    coverage = ti / len(sent_tokens)
    if coverage < 0.55:
        return None
    return first_i, last_i, coverage


def _align_sentences(sentences: list[str], words: list[dict], start_i: int) -> list[dict]:
    """Map each EPUB sentence to start/end word timestamps via ordered subsequence match."""
    lines: list[dict] = []
    wi = start_i

    for sent in sentences:
        st = _tokens(sent)
        if not st:
            continue
        hit = None
        for skip in range(0, 20):
            if wi + skip >= len(words):
                break
            hit = _match_sentence_tokens(st, words, wi + skip)
            if hit:
                if skip:
                    wi += skip
                break
        if not hit:
            continue
        first_i, last_i, coverage = hit
        spoken = " ".join(words[k]["word"].strip() for k in range(first_i, last_i + 1))
        lines.append(
            {
                "text": sent,
                "start": round(float(words[first_i]["start"]), 3),
                "end": round(float(words[last_i]["end"]), 3),
                "spoken": spoken,
                "confidence": round(coverage, 3),
            }
        )
        wi = last_i + 1

    return lines


def transcribe_words(mp3: Path, model: str, cache: Path) -> tuple[list[dict], float]:
    if cache.is_file():
        data = json.loads(cache.read_text(encoding="utf-8"))
        print(f"Using word cache {cache}")
        return data["words"], float(data["duration"])

    from faster_whisper import WhisperModel

    print(f"Transcribing {mp3} with word timestamps (~5 min first run) …")
    whisper = WhisperModel(model, device="cpu", compute_type="int8")
    segments, info = whisper.transcribe(
        str(mp3),
        language="en",
        word_timestamps=True,
        vad_filter=True,
    )
    words: list[dict] = []
    for seg in segments:
        if not seg.words:
            continue
        for w in seg.words:
            token = (w.word or "").strip()
            if not token:
                continue
            words.append(
                {
                    "word": token,
                    "start": float(w.start),
                    "end": float(w.end),
                }
            )

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps({"duration": float(info.duration), "words": words}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Cached {len(words)} words → {cache}")
    return words, float(info.duration)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter", type=int, default=1)
    parser.add_argument("--audio", type=Path, default=None)
    parser.add_argument("--text", type=Path, default=None)
    parser.add_argument("--word-cache", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--model",
        default=os.environ.get("WHISPER_MODEL", str(Path.home() / ".cache/faster-whisper-small")),
    )
    args = parser.parse_args()

    ch = args.chapter
    audio = args.audio or ROOT / "samples" / f"chapter{ch:02d}.mp3"
    text_path = args.text or ROOT / "output" / f"ch{ch:02d}_sentences.json"
    word_cache = args.word_cache or ROOT / "output" / f"ch{ch:02d}_words.json"
    output = args.output or ROOT / "output" / f"ch{ch:02d}.json"

    text_data = json.loads(text_path.read_text(encoding="utf-8"))
    sentences = text_data["sentences"]
    words, duration = transcribe_words(audio, args.model, word_cache)

    start_i = _find_body_word_index(words)
    print(
        f"Chapter {ch}: {len(sentences)} sentences, {len(words)} words, "
        f"body @ {words[start_i]['start']:.1f}s, audio {duration/60:.1f} min"
    )

    lines = _align_sentences(sentences, words, start_i)
    manifest = {
        "chapter": ch,
        "title": f"Chapter {ch} — {text_data['title']}",
        "audio": f"samples/chapter{ch:02d}.mp3",
        "duration": round(duration, 3),
        "aligned_sentences": len(lines),
        "total_sentences": len(sentences),
        "body_start_sec": round(float(words[start_i]["start"]), 3),
        "lines": lines,
    }
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    confs = [ln["confidence"] for ln in lines]
    avg = sum(confs) / max(len(confs), 1)
    good = sum(1 for c in confs if c >= 0.75)
    print(f"Wrote {output}: {len(lines)}/{len(sentences)} sentences, avg conf {avg:.2f}, high≥0.75: {good}")


if __name__ == "__main__":
    main()
