"""Read-along: teacher line ↔ child line, no filler; each step ≤ MAX_CHUNK_WORDS."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_CHUNK_WORDS = 10


def _norm(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\s']", " ", t)
    return " ".join(t.split())


def _tokens(text: str) -> list[str]:
    return [w for w in _norm(text).split() if w]


def _word_count(text: str) -> int:
    return len(_tokens(text))


def _split_long_sentence(sentence: str) -> list[str]:
    """Break a sentence into parts of at most MAX_CHUNK_WORDS words."""
    tokens = re.findall(r"[A-Za-z']+(?:[.!?])?", sentence.strip())
    if not tokens:
        return []
    parts: list[str] = []
    i = 0
    while i < len(tokens):
        piece = tokens[i : i + MAX_CHUNK_WORDS]
        parts.append(" ".join(piece))
        i += MAX_CHUNK_WORDS
    return parts


def material_chunks(material: str) -> list[str]:
    """
    One step = one pasted line (one sentence), if ≤ MAX_CHUNK_WORDS.
    Long lines split into consecutive ≤10-word parts (not single-word steps).
    """
    chunks: list[str] = []
    for raw_line in material.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _word_count(line) <= MAX_CHUNK_WORDS:
            chunks.append(line)
        else:
            chunks.extend(_split_long_sentence(line))
    return chunks


def _subsequence_positions(tokens: list[str], expected: list[str]) -> list[int] | None:
    if not expected:
        return []
    positions: list[int] = []
    ei = 0
    for i, tok in enumerate(tokens):
        if ei < len(expected) and tok == expected[ei]:
            positions.append(i)
            ei += 1
    if ei < len(expected):
        return None
    return positions


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
    function_words = frozenset(
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
    content = [w for w in expected if w not in function_words]
    if not content:
        return _ordered_ratio(spoken, expected)
    spoken_set = set(spoken)
    hit = sum(1 for w in content if w in spoken_set)
    return hit / len(content)


def merge_child_spoken(prior: str, new: str) -> str:
    """Merge two STT clips from the same child turn (pause / say in two parts)."""
    p, n = _norm(prior), _norm(new)
    if not p:
        return new.strip()
    if not n:
        return prior.strip()
    if p == n:
        return prior.strip()
    if n.startswith(p + " ") or p in n.split():
        return new.strip()
    if p.endswith(" " + n) or (len(n) >= 4 and n in p):
        return prior.strip()

    pt, nt = _tokens(prior), _tokens(new)
    overlap = 0
    for k in range(1, min(len(pt), len(nt)) + 1):
        if pt[-k:] == nt[:k]:
            overlap = k
    if overlap:
        return " ".join(pt + nt[overlap:])
    return f"{prior.strip()} {new.strip()}"


def _dedupe_repeated_expected(tokens: list[str], expected_t: list[str]) -> list[str]:
    """Child said the same line twice in one utterance."""
    if len(expected_t) < 2 or len(tokens) < len(expected_t) * 2:
        return tokens
    pos1 = _subsequence_positions(tokens, expected_t)
    if not pos1:
        return tokens
    tail = tokens[pos1[-1] + 1 :]
    if not tail:
        return tokens
    pos2 = _subsequence_positions(tail, expected_t)
    if pos2 and pos2[0] <= 2:
        return tokens[: pos1[-1] + 1]
    return tokens


def _trim_bleed_into_next(
    tokens: list[str],
    expected_t: list[str],
    next_t: list[str] | None,
) -> list[str]:
    """Keep current line; drop trailing words that start the next sentence."""
    if not next_t:
        return tokens
    pos = _subsequence_positions(tokens, expected_t)
    if not pos:
        return tokens
    cut = pos[-1] + 1
    rest = tokens[cut:]
    if not rest:
        return tokens
    bleed = min(len(rest), len(next_t))
    if rest[:bleed] == next_t[:bleed]:
        return tokens[:cut]
    return tokens


def align_child_spoken(
    spoken: str,
    expected: str,
    next_expected: str | None = None,
) -> str:
    """
    Normalize STT for scoring: tolerate repeat, trailing next-line bleed,
    pick the span that best matches the expected line.
    """
    tokens = _tokens(spoken)
    expected_t = _tokens(expected)
    if not tokens or not expected_t:
        return spoken.strip()

    tokens = _dedupe_repeated_expected(tokens, expected_t)
    next_t = _tokens(next_expected) if next_expected else None
    tokens = _trim_bleed_into_next(tokens, expected_t, next_t)

    pos = _subsequence_positions(tokens, expected_t)
    if pos:
        return " ".join(tokens[: pos[-1] + 1])

    return spoken.strip()


def child_attempt_coverage(spoken: str, expected: str) -> float:
    aligned = align_child_spoken(spoken, expected)
    spoken_t = _tokens(aligned)
    expected_t = _tokens(expected)
    if not expected_t:
        return 1.0
    return max(
        _ordered_ratio(spoken_t, expected_t),
        _content_ratio(spoken_t, expected_t),
    )


def is_sufficient_child_attempt(
    spoken: str,
    expected: str,
    *,
    next_expected: str | None = None,
) -> bool:
    """Enough to advance (whole line); partial clips stay on same sentence."""
    aligned = align_child_spoken(spoken, expected, next_expected)
    if matches_chunk(aligned, expected):
        return True
    if child_attempt_coverage(aligned, expected) >= 0.72:
        return True
    return False


def matches_chunk(spoken: str, expected: str) -> bool:
    """True if the child likely read the expected line."""
    if not spoken.strip() or not expected.strip():
        return False
    s = _tokens(spoken)
    e = _tokens(expected)
    if not e:
        return False
    if not s:
        return False
    if _norm(spoken) == _norm(expected):
        return True
    ei = 0
    for tok in s:
        if ei < len(e) and tok == e[ei]:
            ei += 1
    if ei >= len(e):
        return True
    es, ss = set(e), set(s)
    if es and len(es & ss) / len(es) >= 0.75:
        return True
    return False


def expected_chunk_at(chunks: list[str], index: int) -> str | None:
    if 0 <= index < len(chunks):
        return chunks[index]
    return None


@dataclass
class ReadAlongState:
    chunks: list[str] = field(default_factory=list)
    line_start_chunk: list[int] = field(default_factory=list)
    index: int = 0

    def reset(self, material: str) -> None:
        self.chunks = material_chunks(material)
        self.line_start_chunk = []
        chunk_i = 0
        for raw_line in material.strip().splitlines():
            line = raw_line.strip()
            if not line:
                continue
            self.line_start_chunk.append(chunk_i)
            if _word_count(line) <= MAX_CHUNK_WORDS:
                chunk_i += 1
            else:
                chunk_i += len(_split_long_sentence(line))
        self.index = 0

    @property
    def done(self) -> bool:
        return not self.chunks or self.index >= len(self.chunks)

    def current_expected(self) -> str | None:
        return expected_chunk_at(self.chunks, self.index)

    def chunk_span_for_line(self, line_index: int) -> tuple[int, int] | None:
        """Return [start, end) chunk indices for a material line."""
        if (
            not self.chunks
            or line_index < 0
            or line_index >= len(self.line_start_chunk)
        ):
            return None
        start = self.line_start_chunk[line_index]
        end = (
            self.line_start_chunk[line_index + 1]
            if line_index + 1 < len(self.line_start_chunk)
            else len(self.chunks)
        )
        return start, end

    def material_line_text(self, line_index: int) -> str | None:
        """Full pasted-line text (joins multi-chunk lines)."""
        span = self.chunk_span_for_line(line_index)
        if not span:
            return None
        start, end = span
        text = " ".join(self.chunks[start:end]).strip()
        return text or None

    def opening_line(self) -> str:
        return self.material_line_text(0) or ""

    def material_line_index_at(self, chunk_index: int | None = None) -> int:
        """Map chunk index → pasted material line (0-based)."""
        ci = self.index if chunk_index is None else chunk_index
        if not self.line_start_chunk:
            return 0
        for i, start in enumerate(self.line_start_chunk):
            end = (
                self.line_start_chunk[i + 1]
                if i + 1 < len(self.line_start_chunk)
                else len(self.chunks)
            )
            if start <= ci < end:
                return i
        if ci >= len(self.chunks):
            return max(0, len(self.line_start_chunk) - 1)
        return 0

    def jump_to_line(self, line_index: int) -> tuple[str | None, int]:
        """Re-read one pasted line; returns (teacher text, material line index)."""
        if not self.chunks or line_index < 0 or line_index >= len(
            self.line_start_chunk
        ):
            return None, line_index
        span = self.chunk_span_for_line(line_index)
        if not span:
            return None, line_index
        start, _end = span
        self.index = start
        text = self.material_line_text(line_index)
        return (text, line_index)

    def after_child_spoke(self, spoken: str) -> tuple[str | None, bool, bool]:
        """
        Returns (teacher_line, lesson_done, unclear).
        Child spoke → next line only; never re-read current line.
        Always advances (unclear is always False; user can tap to re-read).
        """
        if self.done:
            return None, True, False

        if not self.current_expected():
            return None, True, False

        self.index += 1
        if self.index >= len(self.chunks):
            return None, True, False
        return self.chunks[self.index], False, False


def llm_user_wrapper(spoken: str, expected: str | None, material: str) -> str:
    """Fallback LLM — still no filler words."""
    exp = expected or "(lesson done)"
    return (
        "[Read-along — CHILD spoke]\n"
        f"Child: \"{spoken.strip()}\"\n"
        f"They should have read: \"{exp}\"\n"
        "Reply with ONLY the next sentence from the material (max 10 words). "
        "No Good, Your turn, praise, or Chinese. Do NOT repeat what the child said.\n"
        f"Material:\n{material.strip()}"
    )
