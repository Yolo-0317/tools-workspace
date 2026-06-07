import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services.pronunciation.assess import (  # noqa: E402
    assess_chunk,
    merge_line_verdict,
    should_advance,
)


def test_exact_match_pass():
    r = assess_chunk("I like red.", "I like red.")
    assert r.verdict == "pass"
    assert r.score >= 85


def test_close_almost():
    r = assess_chunk("I like wed", "I like red")
    assert r.verdict in ("almost", "retry")


def test_unrelated_retry():
    r = assess_chunk("hello cat", "I like red")
    assert r.verdict == "retry"


def test_gentle_advances_retry(monkeypatch):
    monkeypatch.delenv("PRONUNCIATION_STRICTNESS", raising=False)
    assert should_advance("retry") is True


def test_always_advances_regardless_of_verdict(monkeypatch):
    monkeypatch.setenv("PRONUNCIATION_STRICTNESS", "normal")
    assert should_advance("retry") is True
    assert should_advance("almost") is True
    assert should_advance("pass") is True


def test_merge_line_verdict_worst_wins():
    assert merge_line_verdict("pass", "almost") == "almost"
    assert merge_line_verdict("almost", "retry") == "retry"
    assert merge_line_verdict("retry", "pass") == "retry"
