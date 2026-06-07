"""Read-along pronunciation marking (text alignment, kid-friendly verdicts)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

from services.read_along import _norm, _tokens, align_child_spoken, matches_chunk

Verdict = Literal["pass", "almost", "retry"]

FUNCTION_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "am",
        "i",
        "you",
        "we",
        "he",
        "she",
        "it",
        "to",
        "of",
        "in",
        "on",
        "at",
        "my",
        "your",
        "and",
        "or",
        "this",
        "that",
    }
)

VERDICT_RANK: dict[str, int] = {"pass": 0, "almost": 1, "retry": 2}


@dataclass
class AssessmentResult:
    verdict: Verdict
    score: int
    highlights: list[dict[str, str]] = field(default_factory=list)
    message: str = ""


def pronunciation_enabled() -> bool:
    return os.getenv("PRONUNCIATION_ASSESS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def strictness() -> str:
    return os.getenv("PRONUNCIATION_STRICTNESS", "gentle").strip().lower()


def should_advance(_verdict: Verdict) -> bool:
    """Always advance; line colors are hints only (user can tap to re-read)."""
    return True


def _ordered_ratio(spoken: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    ei = 0
    matched = 0
    for tok in spoken:
        if ei < len(expected) and tok == expected[ei]:
            matched += 1
            ei += 1
    return matched / len(expected)


def _content_ratio(spoken: list[str], expected: list[str]) -> float:
    content = [w for w in expected if w not in FUNCTION_WORDS]
    if not content:
        return _ordered_ratio(spoken, expected)
    spoken_set = set(spoken)
    hit = sum(1 for w in content if w in spoken_set)
    return hit / len(content)


def _score(spoken: str, expected: str) -> int:
    spoken_t = _tokens(spoken)
    expected_t = _tokens(expected)
    if not expected_t:
        return 100
    if _norm(spoken) == _norm(expected):
        return 100
    seq = _ordered_ratio(spoken_t, expected_t)
    content = _content_ratio(spoken_t, expected_t)
    es, ss = set(expected_t), set(spoken_t)
    set_cov = len(es & ss) / len(es) if es else 0.0
    raw = max(seq, content, set_cov * 0.92)
    return int(round(min(100.0, raw * 100.0)))


def _verdict_from_score(spoken: str, expected: str, score: int) -> Verdict:
    if matches_chunk(spoken, expected):
        return "pass" if score >= 85 else "almost"
    if score >= 85:
        return "pass"
    if score >= 60:
        return "almost"
    return "retry"


def _highlights(spoken: str, expected: str) -> list[dict[str, str]]:
    spoken_t = _tokens(spoken)
    expected_t = _tokens(expected)
    spoken_set = set(spoken_t)
    out: list[dict[str, str]] = []
    for word in expected_t:
        if word in spoken_set:
            out.append({"word": word, "status": "hit"})
        else:
            out.append({"word": word, "status": "miss"})
    return out


def _message(verdict: Verdict) -> str:
    if verdict == "pass":
        return "太棒啦！下一句～"
    if verdict == "almost":
        return "听到啦，下一句～"
    return "没关系，下一句～点句子可重读"


def assess_chunk(
    spoken: str,
    expected: str,
    *,
    next_expected: str | None = None,
) -> AssessmentResult:
    aligned = align_child_spoken(spoken, expected, next_expected)
    score = _score(aligned, expected)
    verdict = _verdict_from_score(aligned, expected, score)
    return AssessmentResult(
        verdict=verdict,
        score=score,
        highlights=_highlights(aligned, expected),
        message=_message(verdict),
    )


def merge_line_verdict(current: Verdict | None, new: Verdict) -> Verdict:
    if current is None:
        return new
    if VERDICT_RANK[new] >= VERDICT_RANK[current]:
        return new
    return current


def result_payload(
    *,
    line_index: int,
    chunk_index: int,
    expected: str,
    spoken: str,
    result: AssessmentResult,
) -> dict[str, Any]:
    return {
        "type": "pronunciation_result",
        "line_index": line_index,
        "chunk_index": chunk_index,
        "expected": expected,
        "spoken": spoken.strip(),
        "aligned": align_child_spoken(spoken, expected).strip(),
        "verdict": result.verdict,
        "score": result.score,
        "highlights": result.highlights,
        "advance": should_advance(result.verdict),
        "message": result.message,
    }
