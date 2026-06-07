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

from chapters import audio_path, audio_rel  # noqa: E402


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
    # US/UK spelling, STT quirks, US EPUB vs UK audiobook (Stephen Fry)
    pairs = {
        ("mustache", "moustache"),
        ("blonde", "blond"),
        ("dursleyish", "undursleyish"),
        ("sorcerers", "philosophers"),
        ("sorcerer's", "philosopher's"),
        ("airplane", "aeroplane"),
        ("video", "cine"),
        ("mail", "post"),
        ("neighbor", "neighbour"),
        ("favorite", "favourite"),
        ("canceled", "cancelled"),
        ("vacationing", "holidaying"),
        ("vacationing", "holiday"),
        ("sweater", "jumper"),
        ("cookies", "biscuits"),
        ("mom", "mum"),
        ("apartment", "flat"),
        ("trunk", "boot"),
        ("elevator", "lift"),
        ("figg", "fig"),
        ("surrey", "surrey"),
        ("toilet's", "toilets"),
        ("toilet's", "toilet"),
        ("aaaaarrrgh", "aaaah"),
        ("aaaaarrrgh", "arrgh"),
        ("4", "four"),
    }
    return (a, b) in pairs or (b, a) in pairs


def _tokens_match(spoken: str, expected: str) -> bool:
    if _fuzzy_eq(spoken, expected):
        return True
    # Prefix match for STT truncation: "holiday" vs "holidaying"
    if len(expected) >= 5 and spoken.startswith(expected[:4]):
        return True
    if len(spoken) >= 5 and expected.startswith(spoken[:4]):
        return True
    return False


def _match_sentence_tokens(
    sent_tokens: list[str],
    words: list[dict],
    start_i: int,
    *,
    min_coverage: float = 0.55,
) -> tuple[int, int, float] | None:
    """Find ordered token subsequence in word stream; return word indices + coverage."""
    if not sent_tokens or start_i >= len(words):
        return None

    ti = 0
    first_i = last_i = start_i
    max_lookahead = max(len(sent_tokens) * 10, 80)

    for j in range(start_i, min(len(words), start_i + max_lookahead)):
        w_tokens = _word_tokens(words[j]["word"])
        if not w_tokens:
            continue
        matched_any = False
        for w in w_tokens:
            if ti < len(sent_tokens) and _tokens_match(w, sent_tokens[ti]):
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
            continue

    coverage = ti / len(sent_tokens)
    if coverage < min_coverage:
        return None
    return first_i, last_i, coverage


def _find_chapter_start(words: list[dict], sentences: list[str]) -> int:
    """Anchor on first EPUB sentence (skip 'CHAPTER N' audiobook intro)."""
    if not sentences:
        return 0
    probe = _tokens(sentences[0])[:10]
    if not probe:
        return _find_body_word_index(words)
    for i in range(min(len(words), 120)):
        hit = _match_sentence_tokens(probe, words, i, min_coverage=0.7)
        if hit:
            return hit[0]
    return _find_body_word_index(words)


def _line_from_hit(sent: str, words: list[dict], hit: tuple[int, int, float]) -> dict:
    first_i, last_i, coverage = hit
    spoken = " ".join(words[k]["word"].strip() for k in range(first_i, last_i + 1))
    return {
        "text": sent,
        "start": round(float(words[first_i]["start"]), 3),
        "end": round(float(words[last_i]["end"]), 3),
        "spoken": spoken,
        "confidence": round(coverage, 3),
    }


def _interpolate_gaps(
    sentences: list[str], slots: list[dict | None], duration: float
) -> list[dict]:
    n = len(sentences)
    out: list[dict | None] = list(slots)

    def _fill_range(gap_start: int, gap_end: int, t0: float, t1: float, conf: float) -> None:
        if gap_end <= gap_start or t1 <= t0:
            return
        weights = [max(len(_tokens(sentences[j])), 1) for j in range(gap_start, gap_end)]
        total_w = sum(weights) or len(weights)
        cursor = t0
        for j, w in zip(range(gap_start, gap_end), weights):
            seg = (t1 - t0) * (w / total_w)
            out[j] = {
                "text": sentences[j],
                "start": round(cursor, 3),
                "end": round(cursor + seg, 3),
                "spoken": "",
                "confidence": conf,
                "interpolated": True,
            }
            cursor += seg

    i = 0
    while i < n:
        if out[i] is not None:
            i += 1
            continue
        gap_start = i
        while i < n and out[i] is None:
            i += 1
        gap_end = i
        prev = out[gap_start - 1] if gap_start > 0 else None
        nxt = out[gap_end] if gap_end < n else None
        if prev and nxt:
            t0, t1 = prev["end"], nxt["start"]
            if t1 <= t0:
                t1 = min(t0 + 0.8, duration)
            _fill_range(gap_start, gap_end, t0, t1, 0.35)
        elif prev:
            t1 = max(duration, prev["end"] + 0.5)
            _fill_range(gap_start, gap_end, prev["end"], t1, 0.25)
        elif nxt:
            _fill_range(gap_start, gap_end, 0.0, nxt["start"], 0.25)

    remaining = [i for i in range(n) if out[i] is None]
    if remaining:
        anchors = [i for i in range(n) if out[i] is not None]
        t0 = out[anchors[0]]["start"] if anchors else 0.0
        t1 = out[anchors[-1]]["end"] if anchors else duration
        if t1 <= t0:
            t1 = duration
        weights = [max(len(_tokens(sentences[j])), 1) for j in remaining]
        total_w = sum(weights) or len(weights)
        span = max(t1 - t0, len(remaining) * 0.4)
        cursor = t0
        for idx, w in zip(remaining, weights):
            seg = span * (w / total_w)
            out[idx] = {
                "text": sentences[idx],
                "start": round(cursor, 3),
                "end": round(min(cursor + seg, duration), 3),
                "spoken": "",
                "confidence": 0.2,
                "interpolated": True,
            }
            cursor += seg

    return [out[i] for i in range(n)]


def _align_sentences(
    sentences: list[str], words: list[dict], start_i: int, duration: float
) -> list[dict]:
    """Map EPUB sentences to timestamps; interpolate gaps when audiobook wording diverges."""
    n = len(sentences)
    slots: list[dict | None] = [None] * n
    wi = start_i

    for idx, sent in enumerate(sentences):
        st = _tokens(sent)
        if not st:
            continue
        hit = None
        for skip in range(0, 30):
            if wi + skip >= len(words):
                break
            for cov in (0.55, 0.45):
                hit = _match_sentence_tokens(st, words, wi + skip, min_coverage=cov)
                if hit:
                    if skip:
                        wi += skip
                    break
            if hit:
                break
        if not hit:
            continue
        slots[idx] = _line_from_hit(sent, words, hit)
        wi = hit[1] + 1

    lines = _interpolate_gaps(sentences, slots, duration)
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
    parser.add_argument("--book", default="hp01")
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

    book_id = args.book
    ch = args.chapter
    ch_pad = f"{ch:02d}"
    audio = args.audio or audio_path(book_id, ch)
    text_path = args.text or ROOT / "output" / f"ch{ch_pad}_sentences.json"
    word_cache = args.word_cache or ROOT / "output" / f"ch{ch_pad}_words.json"
    output = args.output or ROOT / "output" / f"ch{ch_pad}.json"

    text_data = json.loads(text_path.read_text(encoding="utf-8"))
    sentences = text_data["sentences"]
    words, duration = transcribe_words(audio, args.model, word_cache)

    start_i = _find_chapter_start(words, sentences) if ch > 1 else _find_body_word_index(words)
    print(
        f"{book_id} ch{ch}: {len(sentences)} sentences, {len(words)} words, "
        f"body @ {words[start_i]['start']:.1f}s, audio {duration/60:.1f} min"
    )

    lines = _align_sentences(sentences, words, start_i, duration)
    manifest = {
        "book_id": book_id,
        "chapter": ch,
        "title": f"Chapter {ch} — {text_data['title']}",
        "audio": audio_rel(book_id, ch),
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
