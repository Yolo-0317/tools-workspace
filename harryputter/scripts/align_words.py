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

from bilingual_clips import load_bilingual_clips, load_granularity  # noqa: E402
from chapters import audio_path, audio_rel  # noqa: E402

# US EPUB sometimes merges multiple spoken beats into one sentence; split before align.
_ALIGN_SUBCLIP_MARKERS: list[str] = [
    # hp01 ch04
    " and as for all this about your parents",
    " But at that moment, Hagrid leapt",
    " In danger of being speared",
    # hp01 ch01
    " Mrs. Dursley was thin",
    " Mr. Dursley hummed",
    " Professor McGonagall flinched",
    "You flatter me,",
    " every child in our world will know his name",
    " Lily an' James dead",
    " Dumbledore stepped",
    " nor when two owls",
]


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


def _preprocess_align_text(text: str) -> str:
    """Normalize PDF wording before tokenizing for STT match."""
    text = _ascii_quotes(text)
    text = re.sub(r"\bseven hundred and thirteen\b", "713", text, flags=re.I)
    text = re.sub(r"\bseven hundred thirteen\b", "713", text, flags=re.I)
    text = re.sub(r"\bI've never known\b", "I never know", text, flags=re.I)
    text = re.sub(r"\btoday\b", "to day", text, flags=re.I)
    text = re.sub(r"\bpate\b", "pale", text, flags=re.I)
    text = re.sub(r"knowin'?(\s)", r"knowing\1", text, flags=re.I)
    text = re.sub(r"wizardin'?(\s)", r"wizarding\1", text, flags=re.I)
    text = re.sub(
        r"you saw what everyone in the leaky cauldron was like when they saw yeh",
        "you saw him in the leaky cauldron",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bline 0' muggles\b", "line of muggles", text, flags=re.I)
    text = re.sub(r"\bgive it a wave\b", "give it away", text, flags=re.I)
    text = re.sub(r"\bschool books\b", "schoolbooks", text, flags=re.I)
    return text


def _tokens(text: str) -> list[str]:
    text = _preprocess_align_text(text)
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


def _spoken_lcs_ratio(expected: list[str], spoken: list[str]) -> float:
    """Ordered coverage using fuzzy token match (guards paragraph false positives)."""
    if not expected:
        return 1.0 if not spoken else 0.0
    i = j = matched = 0
    while i < len(expected) and j < len(spoken):
        if _tokens_match(spoken[j], expected[i]):
            matched += 1
            i += 1
            j += 1
        elif (
            expected[i] == "griphook"
            and spoken[j] == "grip"
            and j + 1 < len(spoken)
            and spoken[j + 1] == "hook"
        ):
            matched += 1
            i += 1
            j += 2
        else:
            j += 1
    return matched / len(expected)


def _spoken_lcs_ratio_flex(expected: list[str], spoken: list[str]) -> float:
    """Best ordered coverage allowing a short skipped head (STT/PDF lead-in drift)."""
    if not expected:
        return 1.0 if not spoken else 0.0
    best = 0.0
    for skip in range(min(6, len(expected))):
        best = max(best, _spoken_lcs_ratio(expected[skip:], spoken))
    return best


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
        ("yeh", "you"),
        ("ye", "you"),
        ("yer", "your"),
        ("an", "and"),
        ("las", "last"),
        ("o", "of"),
        ("meself", "myself"),
        ("couldnt", "couldn't"),
        ("wouldnt", "wouldn't"),
        ("didnt", "didn't"),
        ("wasnt", "wasn't"),
        ("dont", "don't"),
        ("im", "i'm"),
        ("its", "it's"),
        ("demand", "demanded"),
        ("summat", "some"),
        ("summat", "something"),
        ("known", "know"),
        ("toward", "towards"),
        ("downward", "downwards"),
        ("his", "its"),
        ("he", "harry"),
        ("boil", "buy"),
        ("gringotts", "gringots"),
        ("mm", "eh"),
        ("pate", "pale"),
        ("ye", "yeh"),
        ("whippy", "quippy"),
        ("hoover", "vacuum"),
        ("schoolbooks", "school"),
        ("dursley", "dearly"),
        ("prune", "prune"),
        ("smash", "smash"),
        ("ron", "wrong"),
        ("us", "as"),
        ("urgh", "ugh"),
        ("boogers", "bogies"),
    }
    return (a, b) in pairs or (b, a) in pairs


_CANON = {
    "yeh": "you",
    "ye": "you",
    "yer": "your",
    "ya": "you",
    "an": "and",
    "las": "last",
    "o": "of",
    "meself": "myself",
    "couldnt": "couldn't",
    "wouldnt": "wouldn't",
    "didnt": "didn't",
    "wasnt": "wasn't",
    "dont": "don't",
    "im": "i'm",
    "its": "it's",
}


def _canon_tok(token: str) -> str:
    t = _norm(token)
    return _CANON.get(t, t)


def _tokens_match(spoken: str, expected: str) -> bool:
    if _fuzzy_eq(spoken, expected):
        return True
    if _canon_tok(spoken) == _canon_tok(expected):
        return True
    if expected == "griphook" and spoken == "grip":
        return True
    if expected == "i've" and spoken == "i":
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
    strict: bool = True,
    paragraph: bool = False,
) -> tuple[int, int, float] | None:
    """Find ordered token subsequence in word stream; return word indices + coverage."""
    if not sent_tokens or start_i >= len(words):
        return None

    ti = 0
    first_i = last_i = start_i
    if paragraph:
        max_lookahead = min(max(len(sent_tokens) * 8, 40), 220)
    else:
        max_lookahead = min(max(len(sent_tokens) * (4 if strict else 6), 20), 50 if strict else 65)

    for j in range(start_i, min(len(words), start_i + max_lookahead)):
        w_tokens = _word_tokens(words[j]["word"])
        if not w_tokens:
            continue
        matched_any = False
        for w in w_tokens:
            if ti >= len(sent_tokens):
                break
            max_skip = 0 if ti == 0 and len(sent_tokens) <= 3 else 3
            for skip in range(0, max_skip + 1):
                if ti + skip >= len(sent_tokens):
                    break
                if not _tokens_match(w, sent_tokens[ti + skip]):
                    continue
                if ti == 0:
                    first_i = j
                last_i = j
                ti = ti + skip + 1
                matched_any = True
                break
            if ti >= len(sent_tokens):
                break
        if ti >= len(sent_tokens):
            break
        if not matched_any and ti > 0:
            continue

    coverage = ti / len(sent_tokens)
    if coverage < min_coverage:
        return None
    if len(sent_tokens) <= 2 and coverage < 1.0:
        return None

    span_words = last_i - first_i + 1
    span_sec = float(words[last_i]["end"]) - float(words[first_i]["start"])
    if paragraph:
        max_words = max(int(len(sent_tokens) * 4.5) + 12, 16)
        max_sec = min(max(len(sent_tokens) * 0.58 + 4.0, 10.0), 90.0)
    elif strict:
        max_words = max(int(len(sent_tokens) * 2.4) + 4, 10)
        max_sec = max(len(sent_tokens) * 0.55 + 2.5, 7.0)
    else:
        max_words = max(int(len(sent_tokens) * 3.2) + 8, 14)
        max_sec = min(max(len(sent_tokens) * 0.72 + 3.5, 9.0), 22.0)
    if not paragraph:
        max_sec = min(max_sec, 25.0)
    if span_words > max_words or span_sec > max_sec:
        return None

    if strict:
        spoken_tokens: list[str] = []
        for k in range(first_i, last_i + 1):
            spoken_tokens.extend(_word_tokens(words[k]["word"]))
        if spoken_tokens and _lcs_ratio(sent_tokens, spoken_tokens) < min(0.68, min_coverage + 0.08):
            return None

    return first_i, last_i, coverage


def _split_sentence_at_markers(sentence: str, markers: list[str]) -> list[str]:
    parts = [sentence]
    for marker in markers:
        next_parts: list[str] = []
        for part in parts:
            hit = False
            for m in (marker, marker.lstrip()):
                if m not in part:
                    continue
                before, after = part.split(m, 1)
                before = before.strip()
                after = (m.strip() + after).strip()
                if before:
                    next_parts.append(before)
                if after:
                    next_parts.append(after)
                hit = True
                break
            if not hit:
                next_parts.append(part)
        parts = [p for p in next_parts if p.strip()]
    return parts


def _expand_sentences_for_align(
    sentences: list[str], kinds: list[str]
) -> tuple[list[str], list[str]]:
    expanded: list[str] = []
    expanded_kinds: list[str] = []
    for sent, kind in zip(sentences, kinds):
        for part in _split_sentence_at_markers(sent, _ALIGN_SUBCLIP_MARKERS):
            expanded.append(part)
            expanded_kinds.append(kind)
    return expanded, expanded_kinds


def _find_chapter_start(words: list[dict], sentences: list[str], kinds: list[str]) -> int:
    """Anchor on first body sentence (skip spoken chapter-title intro)."""
    first_body = next((s for s, k in zip(sentences, kinds) if k != "heading"), "")
    if not first_body:
        return _find_body_word_index(words)
    probe = _tokens(first_body)[:10]
    if not probe:
        return _find_body_word_index(words)
    for i in range(min(len(words), 120)):
        hit = _match_sentence_tokens(probe, words, i, min_coverage=0.7)
        if hit:
            return hit[0]
    return _find_body_word_index(words)


def _line_from_hit(
    sent: str, words: list[dict], hit: tuple[int, int, float], *, kind: str = "body"
) -> dict:
    first_i, last_i, coverage = hit
    spoken = " ".join(words[k]["word"].strip() for k in range(first_i, last_i + 1))
    line = {
        "text": sent,
        "start": round(float(words[first_i]["start"]), 3),
        "end": round(float(words[last_i]["end"]), 3),
        "spoken": spoken,
        "confidence": round(coverage, 3),
    }
    if kind != "body":
        line["kind"] = kind
    return line


def _align_heading(sent: str, words: list[dict]) -> tuple[int, int, float] | None:
    """Match EPUB chapter banner to Stephen Fry's 'Chapter N … Title' intro."""
    st = _tokens(sent)
    if not st:
        return None
    start_i = 0
    for i, w in enumerate(words[:80]):
        if _norm(w["word"]) == "chapter":
            start_i = i
            break
    for cov in (0.45, 0.35):
        hit = _match_sentence_tokens(st, words, start_i, min_coverage=cov)
        if hit:
            return hit
    # Title words only (after "Chapter N ·")
    title_tokens = [t for t in st if t not in {"chapter", "·"} and not t.isdigit()]
    if title_tokens:
        for cov in (0.55, 0.4):
            hit = _match_sentence_tokens(title_tokens, words, start_i, min_coverage=cov)
            if hit:
                return hit
    return None


def _interpolate_gaps(
    sentences: list[str], slots: list[dict | None], duration: float
) -> list[dict]:
    n = len(sentences)
    out: list[dict | None] = list(slots)

    def _fill_range(gap_start: int, gap_end: int, t0: float, t1: float, conf: float) -> None:
        if gap_end <= gap_start:
            return
        n_gap = gap_end - gap_start
        min_seg = 0.12
        span = t1 - t0
        if span < min_seg * n_gap:
            span = min_seg * n_gap
            t1 = t0 + span
        weights = [max(len(_tokens(sentences[j])), 1) for j in range(gap_start, gap_end)]
        total_w = sum(weights) or len(weights)
        cursor = t0
        for j, w in zip(range(gap_start, gap_end), weights):
            seg = max(span * (w / total_w), min_seg)
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
            elif t1 - t0 > 120:
                # Bad anchors far apart — spread across full gap instead of cramming.
                _fill_range(gap_start, gap_end, t0, t1, 0.3)
                continue
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


_SFX_RE = re.compile(
    r"^(?:boom|smash|crash|bang|knock|pause)\.?$",
    re.I,
)


def _sfx_line(sent: str, words: list[dict], wi: int) -> dict | None:
    """Onomatopoeia / beats with no STT tokens — use gap before next spoken word."""
    st = _tokens(sent)
    if not st or not _SFX_RE.match(" ".join(st)):
        return None
    if wi >= len(words):
        return None
    t0 = float(words[wi - 1]["end"]) if wi > 0 else 0.0
    t1 = float(words[wi]["start"])
    if t1 <= t0:
        t1 = t0 + 0.4
    return {
        "text": sent,
        "start": round(t0, 3),
        "end": round(t1, 3),
        "spoken": "",
        "confidence": 0.55,
        "sfx": True,
    }


def _try_match_sentence(
    sent: str, words: list[dict], wi: int
) -> tuple[int, int, float] | None:
    st = _tokens(sent)
    if not st:
        return None
    hit = None
    for skip in range(0, 30):
        if wi + skip >= len(words):
            break
        for cov in (0.55, 0.45):
            hit = _match_sentence_tokens(st, words, wi + skip, min_coverage=cov, strict=True)
            if not hit:
                hit = _match_sentence_tokens(
                    st, words, wi + skip, min_coverage=max(0.4, cov - 0.05), strict=False
                )
            if hit:
                return hit
    # EPUB sometimes merges several spoken lines — anchor on the opening clause.
    clauses = re.split(r'(?<=[.!?…][""\'])\s+', sent.strip())
    if len(clauses) > 1 and clauses[0].strip():
        st0 = _tokens(clauses[0])
        if st0 and len(st0) >= 3:
            for skip in range(0, 20):
                if wi + skip >= len(words):
                    break
                hit = _match_sentence_tokens(
                    st0, words, wi + skip, min_coverage=0.5, strict=False
                )
                if hit:
                    return hit
    # Whisper sometimes drops a clause; anchor on the closing fragment.
    if len(st) >= 4:
        tail = st[-4:]
        for skip in range(0, 20):
            if wi + skip >= len(words):
                break
            hit = _match_sentence_tokens(
                tail, words, wi + skip, min_coverage=0.75, strict=False
            )
            if hit:
                return hit
    return None


def _word_index_near_time(words: list[dict], t: float, *, start_i: int = 0) -> int:
    for i in range(start_i, len(words)):
        if words[i]["start"] >= t:
            return max(start_i, i - 2)
    return max(start_i, len(words) - 1)


def _try_match_with_resync(
    sent: str,
    words: list[dict],
    wi: int,
    *,
    idx: int,
    n: int,
    start_i: int,
    duration: float,
    last_match_time: float,
    fail_streak: int,
) -> tuple[int, int, float] | None:
    hit = _try_match_sentence(sent, words, wi)
    if not hit and fail_streak >= 2:
        progress = idx / max(n - 1, 1)
        body_start = float(words[start_i]["start"])
        target_t = body_start + progress * max(duration - body_start, 1.0)
        guess = _word_index_near_time(words, target_t - 8.0, start_i=start_i)
        if guess > wi:
            hit = _try_match_sentence(sent, words, guess)
    if not hit:
        return None

    t0 = float(words[hit[0]]["start"])
    if t0 < last_match_time - 1.5:
        return None
    st = _tokens(sent)
    remaining = n - idx - 1
    if (
        len(st) <= 2
        and remaining >= 12
        and t0 - last_match_time < 4.0
        and hit[2] < 0.9
    ):
        return None
    return hit


_PREFIX_STOP = {
    "said",
    "mr",
    "mrs",
    "ms",
    "dr",
    "the",
    "a",
    "an",
    "and",
    "but",
    "or",
    "he",
    "she",
    "it",
    "they",
    "his",
    "her",
    "their",
    "was",
    "were",
    "had",
    "has",
    "have",
    "been",
    "that",
    "this",
    "with",
    "for",
    "not",
    "you",
    "as",
    "at",
    "in",
    "on",
    "to",
    "of",
    "is",
    "be",
    "i",
    "we",
    "him",
    "who",
    "what",
    "when",
    "where",
    "how",
    "if",
    "so",
    "up",
    "out",
    "all",
    "just",
    "very",
    "then",
    "there",
    "into",
    "about",
}


def _distinctive_prefix(tokens: list[str], *, max_len: int = 8) -> list[str]:
    picked: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if t in _PREFIX_STOP or len(t) <= 2:
            continue
        if t in seen:
            continue
        seen.add(t)
        picked.append(t)
        if len(picked) >= max_len:
            break
    if len(picked) >= 3:
        return picked
    return tokens[: min(max_len, len(tokens))]


def _match_prefix_tokens(
    sent_tokens: list[str],
    words: list[dict],
    start_i: int,
    *,
    prefix_len: int = 10,
    min_coverage: float = 0.5,
) -> tuple[int, int, float] | None:
    """Anchor long paragraph on opening tokens (strict order, no probe-token skip)."""
    probe = _distinctive_prefix(sent_tokens, max_len=prefix_len)
    if len(probe) < 3 and len(sent_tokens) >= 3:
        probe = sent_tokens[:3]
    if not probe or start_i >= len(words):
        return None

    ti = 0
    first_i = last_i = start_i
    max_lookahead = min(len(words) - start_i, max(len(probe) * 12, 150))

    for j in range(start_i, start_i + max_lookahead):
        w_tokens = _word_tokens(words[j]["word"])
        if not w_tokens:
            continue
        matched_any = False
        for w in w_tokens:
            if ti >= len(probe):
                break
            if not _tokens_match(w, probe[ti]):
                continue
            if ti == 0:
                first_i = j
            last_i = j
            ti += 1
            matched_any = True
            break
        if ti >= len(probe):
            break
        if not matched_any and ti > 0:
            continue

    coverage = ti / len(probe)
    if coverage < min_coverage:
        return None
    return first_i, last_i, coverage


def _try_match_paragraph_span(
    sent: str, words: list[dict], wi: int, *, last_match_time: float
) -> tuple[int, int, float] | None:
    """Full-span match for PDF paragraphs (relaxed limits, monotonic time)."""
    st = _tokens(sent)
    if not st:
        return None
    max_skip = 8 if len(st) <= 18 else 50
    for skip in range(0, max_skip):
        if wi + skip >= len(words):
            break
        for cov in (0.58, 0.5, 0.45, 0.4, 0.36):
            hit = _match_sentence_tokens(
                st, words, wi + skip, min_coverage=cov, strict=False, paragraph=True
            )
            if not hit:
                continue
            t0 = float(words[hit[0]]["start"])
            if t0 < last_match_time - 0.8:
                continue
            spoken_tokens: list[str] = []
            for k in range(hit[0], hit[1] + 1):
                spoken_tokens.extend(_word_tokens(words[k]["word"]))
            if spoken_tokens:
                lcs = _spoken_lcs_ratio(st, spoken_tokens)
                flex = _spoken_lcs_ratio_flex(st, spoken_tokens)
                cov = hit[2]
                if cov < 0.72 and lcs < 0.42 and flex < 0.55:
                    continue
                if cov < 0.88 and flex < 0.48:
                    continue
                if flex < 0.30 and cov < 0.95:
                    continue
                probe = st[: min(3, len(st))]
                if (
                    cov < 0.88
                    and probe
                    and not any(
                        _tokens_match(spoken_tokens[j], probe[0])
                        for j in range(min(6, len(spoken_tokens)))
                    )
                ):
                    continue
            return hit
    return None


def _align_paragraphs(
    sentences: list[str],
    kinds: list[str],
    words: list[dict],
    start_i: int,
    duration: float,
) -> list[dict]:
    """One bilingual paragraph ↔ one audio span (prefer full Whisper span)."""
    n = len(sentences)
    slots: list[dict | None] = [None] * n
    wi = start_i
    last_match_time = float(words[start_i]["start"])

    for idx, sent in enumerate(sentences):
        kind = kinds[idx] if idx < len(kinds) else "body"
        if kind == "heading":
            hit = _align_heading(sent, words)
            if hit:
                slots[idx] = _line_from_hit(sent, words, hit, kind="heading")
                slots[idx]["paragraph_align"] = True
                wi = hit[1] + 1
                last_match_time = float(words[hit[0]]["start"])
            continue

        hit = _try_match_paragraph_span(sent, words, wi, last_match_time=last_match_time)
        prefix_hit = False
        if not hit:
            st = _tokens(sent)
            for skip in range(0, 45):
                if wi + skip >= len(words):
                    break
                for pl in (10, 8, 6, 4):
                    for cov in (0.6, 0.5, 0.42):
                        cand = _match_prefix_tokens(
                            st, words, wi + skip, prefix_len=pl, min_coverage=cov
                        )
                        if not cand:
                            continue
                        t0 = float(words[cand[0]]["start"])
                        if t0 < last_match_time - 0.8:
                            continue
                        hit = cand
                        prefix_hit = True
                        break
                    if hit:
                        break
                if hit:
                    break
            if prefix_hit and hit:
                full = _match_sentence_tokens(
                    st, words, hit[0], min_coverage=0.55, strict=False, paragraph=True
                )
                if full:
                    spoken: list[str] = []
                    for k in range(full[0], full[1] + 1):
                        spoken.extend(_word_tokens(words[k]["word"]))
                    if _spoken_lcs_ratio_flex(st, spoken) >= 0.48:
                        hit = full
                        prefix_hit = False

        if not hit and idx > 0:
            progress = idx / max(n - 1, 1)
            body_start = float(words[start_i]["start"])
            target_t = body_start + progress * max(duration - body_start, 1.0)
            guess = _word_index_near_time(words, target_t - 6.0, start_i=wi)
            hit = _try_match_paragraph_span(
                sent, words, guess, last_match_time=last_match_time
            )

        if not hit:
            continue

        line = _line_from_hit(sent, words, hit, kind=kind if kind != "heading" else "body")
        line["paragraph_align"] = True
        slots[idx] = line
        wi = hit[1] + 1
        last_match_time = float(words[hit[0]]["start"])

    # Prefix-only long spans: extend end to next matched start (avoid swallowing dialogue).
    next_starts: list[int | None] = [None] * n
    for idx, slot in enumerate(slots):
        if slot is None:
            continue
        t0 = float(slot["start"])
        for j in range(idx + 1, n):
            if slots[j] is not None and float(slots[j]["start"]) > t0 + 0.5:
                next_starts[idx] = j
                break
    for idx, slot in enumerate(slots):
        if slot is None or next_starts[idx] is None:
            continue
        nxt = slots[next_starts[idx]]
        if float(slot["end"]) > float(nxt["start"]) - 0.15:
            slot["end"] = round(float(nxt["start"]) - 0.05, 3)

    # Prefix-only anchors: extend only when the span is clearly too short.
    for idx in range(n):
        slot = slots[idx]
        if slot is None:
            continue
        est = max(len(_tokens(sentences[idx])) * 0.28, 2.5)
        actual = float(slot["end"]) - float(slot["start"])
        for j in range(idx + 1, n):
            nxt = slots[j]
            if nxt is None:
                continue
            gap = float(nxt["start"]) - float(slot["end"])
            if gap > 2.0 and actual < est * 0.55:
                slot["end"] = round(float(nxt["start"]) - 0.05, 3)
            break

    lines = _interpolate_gaps(sentences, slots, duration)

    # Dialogue-heavy gaps: spread consecutive interpolated runs; fix overlaps.
    min_seg = 1.2
    i = 0
    while i < len(lines):
        if not lines[i].get("interpolated"):
            i += 1
            continue
        run_start = i
        while i < len(lines) and lines[i].get("interpolated"):
            i += 1
        run_end = i
        prev_end = float(lines[run_start - 1]["end"]) if run_start > 0 else 0.0
        next_start = float(lines[run_end]["start"]) if run_end < len(lines) else duration
        span = max(next_start - prev_end, min_seg * (run_end - run_start))
        cursor = prev_end
        weights = [max(len(_tokens(lines[j]["text"])), 1) for j in range(run_start, run_end)]
        total_w = sum(weights) or len(weights)
        for j, w in zip(range(run_start, run_end), weights):
            seg = max(span * (w / total_w), min_seg)
            lines[j]["start"] = round(cursor, 3)
            lines[j]["end"] = round(min(cursor + seg, duration), 3)
            cursor += seg
        if run_end < len(lines) and cursor > float(lines[run_end]["start"]):
            lines[run_end]["start"] = round(cursor + 0.05, 3)

    for idx in range(1, len(lines)):
        if float(lines[idx]["start"]) < float(lines[idx - 1]["end"]):
            mid = (float(lines[idx - 1]["end"]) + float(lines[idx]["start"])) / 2
            lines[idx - 1]["end"] = round(mid - 0.02, 3)
            lines[idx]["start"] = round(mid + 0.02, 3)

    for idx, line in enumerate(lines):
        kind = kinds[idx] if idx < len(kinds) else "body"
        if kind != "body" and "kind" not in line:
            line["kind"] = kind
    return lines


def _align_sentences(
    sentences: list[str],
    kinds: list[str],
    words: list[dict],
    start_i: int,
    duration: float,
) -> list[dict]:
    """Map EPUB sentences to timestamps; interpolate gaps when audiobook wording diverges."""
    n = len(sentences)
    slots: list[dict | None] = [None] * n
    wi = start_i
    last_match_time = float(words[start_i]["start"])
    fail_streak = 0

    for idx, sent in enumerate(sentences):
        kind = kinds[idx] if idx < len(kinds) else "body"
        if kind == "heading":
            hit = _align_heading(sent, words)
            if hit:
                slots[idx] = _line_from_hit(sent, words, hit, kind="heading")
                wi = max(wi, hit[1] + 1)
                last_match_time = float(words[hit[0]]["start"])
                fail_streak = 0
            continue

        sfx = _sfx_line(sent, words, wi)
        if sfx:
            slots[idx] = sfx
            fail_streak = 0
            continue

        hit = _try_match_with_resync(
            sent,
            words,
            wi,
            idx=idx,
            n=n,
            start_i=start_i,
            duration=duration,
            last_match_time=last_match_time,
            fail_streak=fail_streak,
        )
        if not hit:
            fail_streak += 1
            continue
        slots[idx] = _line_from_hit(sent, words, hit, kind="body")
        wi = hit[1] + 1
        last_match_time = float(words[hit[0]]["start"])
        fail_streak = 0

    lines = _interpolate_gaps(sentences, slots, duration)
    for idx, line in enumerate(lines):
        kind = kinds[idx] if idx < len(kinds) else "body"
        if kind != "body" and "kind" not in line:
            line["kind"] = kind
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
    from chapters import manifest_path, sentences_path, words_cache_path  # noqa: E402

    text_path = args.text or sentences_path(book_id, ch)
    word_cache = args.word_cache or words_cache_path(book_id, ch)
    output = args.output or manifest_path(book_id, ch)

    text_data = json.loads(text_path.read_text(encoding="utf-8"))
    epub_sentences = text_data["sentences"]
    epub_kinds = text_data.get("kinds") or ["body"] * len(epub_sentences)
    if len(epub_kinds) != len(epub_sentences):
        epub_kinds = ["body"] * len(epub_sentences)

    clips = load_bilingual_clips(book_id, ch)
    granularity = "sentence"
    if clips:
        granularity = load_granularity(book_id, ch)
        from bilingual_clips import clips_for_align  # noqa: E402

        align_sents, align_kinds = clips_for_align(clips)
        align_mode = "bilingual_clips"
        print(
            f"{book_id} ch{ch}: {len(clips)} bilingual_clips "
            f"({granularity or 'sentence'} granularity)"
        )
    else:
        align_sents, align_kinds = _expand_sentences_for_align(epub_sentences, epub_kinds)
        align_mode = "epub_sentences"
        n_subclips = len(align_sents) - len(epub_sentences)
        if n_subclips:
            print(
                f"Expanded {len(epub_sentences)} EPUB sentences → {len(align_sents)} align clips (+{n_subclips} subclips)"
            )

    words, duration = transcribe_words(audio, args.model, word_cache)
    start_i = _find_chapter_start(words, align_sents, align_kinds)

    print(
        f"{book_id} ch{ch}: align {len(align_sents)} units ({sum(1 for k in align_kinds if k == 'heading')} heading), "
        f"{len(words)} words, body @ {words[start_i]['start']:.1f}s, audio {duration/60:.1f} min"
    )

    if granularity == "paragraph":
        lines = _align_paragraphs(align_sents, align_kinds, words, start_i, duration)
    else:
        lines = _align_sentences(align_sents, align_kinds, words, start_i, duration)
    manifest = {
        "book_id": book_id,
        "chapter": ch,
        "title": f"Chapter {ch} — {text_data['title']}",
        "audio": audio_rel(book_id, ch),
        "duration": round(duration, 3),
        "aligned_sentences": len(lines),
        "epub_sentences": len(epub_sentences),
        "align_mode": align_mode,
        "align_granularity": granularity,
        "total_sentences": len(lines),
        "body_start_sec": round(float(words[start_i]["start"]), 3),
        "lines": lines,
    }
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    confs = [ln["confidence"] for ln in lines]
    avg = sum(confs) / max(len(confs), 1)
    good = sum(1 for c in confs if c >= 0.75)
    print(f"Wrote {output}: {len(lines)}/{len(align_sents)} units, avg conf {avg:.2f}, high≥0.75: {good}")


if __name__ == "__main__":
    main()
