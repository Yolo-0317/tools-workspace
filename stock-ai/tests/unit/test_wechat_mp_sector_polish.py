"""wechat_mp_sector_polish 单元测试."""

from __future__ import annotations

from scripts.tools.wechat_mp_sector_polish import sanitize_sector_llm_leaks


def test_sanitize_sector_llm_leaks_meta_phrases() -> None:
    raw = (
        "根据你提供的6月4日指数，沪指收涨0.2%。\n"
        "我们认为，产业链仍有机会。"
    )
    out = sanitize_sector_llm_leaks(raw)
    assert "根据你提供的" not in out
    assert "沪指收涨" in out or "我们认为" in out
