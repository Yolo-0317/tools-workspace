"""Detect STT results that are likely speaker echo of the teacher's last line."""

from __future__ import annotations

import re


def _norm(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\s']", " ", t)
    return " ".join(t.split())


def _tokens(text: str) -> set[str]:
    return {w for w in _norm(text).split() if len(w) > 1}


def is_likely_teacher_echo(
    user_text: str,
    last_assistant: str | None,
    *,
    expected_child_chunk: str | None = None,
) -> bool:
    """True if user_text is probably TTS picked up by the mic, not the child."""
    if not last_assistant or not user_text.strip():
        return False
    if expected_child_chunk:
        from services.read_along import matches_chunk

        if matches_chunk(user_text, expected_child_chunk):
            return False
    u = _norm(user_text)
    a = _norm(last_assistant)
    if len(u) < 3:
        return False
    if u == a:
        return True
    if len(u) >= 6 and (u in a or a in u):
        return True
    ut, at = _tokens(user_text), _tokens(last_assistant)
    if not ut or not at:
        return False
    overlap = len(ut & at) / max(len(ut), 1)
    if overlap >= 0.85 and len(ut) <= len(at) + 2:
        return True
    return False
