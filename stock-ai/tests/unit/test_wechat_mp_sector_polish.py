"""wechat_mp_sector_polish 单元测试."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_sector_polish import (
    sanitize_sector_llm_leaks,
    sanitize_sector_reader_voice,
)


def test_sanitize_sector_reader_voice_strips_ai_flavor_triggers() -> None:
    raw = "首先看磷化工。数据流水线会更新。其次看钛白粉。推荐 ♡"
    out = sanitize_sector_reader_voice(raw)
    assert "流水线" not in out
    assert "首先" not in out
    assert "其次" not in out
    assert "♡" not in out
    assert "先看磷化工" in out


def test_sanitize_sector_llm_leaks_meta_phrases() -> None:
    raw = (
        "根据你提供的6月4日指数，沪指收涨0.2%。\n"
        "我们认为，产业链仍有机会。"
    )
    out = sanitize_sector_llm_leaks(raw)
    assert "根据你提供的" not in out
    assert "沪指收涨" in out or "我们认为" in out
