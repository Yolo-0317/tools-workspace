"""点击吸引力优化：仍以事实和明确披露为边界。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_rewrite_clickworthy_title_makes_abstract_question_concrete() -> None:
    from scripts.tools.wechat_mp_clickworthy import rewrite_clickworthy_title

    assert rewrite_clickworthy_title(
        "董明珠任校长，格力技校能改命吗？",
        topic_label="董明珠任格力技校校长",
        enabled=True,
    ) == "董明珠当校长，技校生毕业真能进格力吗？"


def test_rewrite_clickworthy_title_keeps_title_when_mode_is_off() -> None:
    from scripts.tools.wechat_mp_clickworthy import rewrite_clickworthy_title

    assert rewrite_clickworthy_title(
        "董明珠任校长，格力技校能改命吗？",
        topic_label="董明珠任格力技校校长",
        enabled=False,
    ) == "董明珠任校长，格力技校能改命吗？"


def test_rewrite_clickworthy_title_turns_abstract_impact_into_reader_stakes() -> None:
    from scripts.tools.wechat_mp_clickworthy import rewrite_clickworthy_title

    assert rewrite_clickworthy_title(
        "一项新规影响大吗？",
        topic_label="外卖平台新规",
        enabled=True,
    ) == "一项新规，会先影响谁的钱包和选择？"


def test_composite_opening_discloses_its_status_and_lands_on_fact() -> None:
    from scripts.tools.wechat_mp_clickworthy import prepend_disclosed_composite_opening

    out = prepend_disclosed_composite_opening(
        "后文继续解释这所学校的安排。",
        topic_label="格力技校",
        fact_lines=["格力宣布参与技校办学。"],
        enabled=True,
    )

    assert "合成情境" in out
    assert "不对应具体当事人" in out
    assert "格力宣布参与技校办学。" in out


def test_composite_opening_does_not_appear_without_research_fact() -> None:
    from scripts.tools.wechat_mp_clickworthy import prepend_disclosed_composite_opening

    assert prepend_disclosed_composite_opening(
        "原来的开头。",
        topic_label="格力技校",
        fact_lines=[],
        enabled=True,
    ) == "原来的开头。"


def test_hotspot_opening_only_uses_verified_research_hits() -> None:
    from scripts.tools.wechat_mp_content import _hotspot_clickworthy_opening

    out = _hotspot_clickworthy_opening(
        "原来的开头。",
        topic_label="格力技校",
        research_hits=[{"title": "格力参与技校办学", "snippet": "公开发布会披露"}],
        enabled=True,
    )

    assert "合成情境" in out
    assert "格力参与技校办学" in out


def test_codex_hotspot_minimum_can_be_lowered_for_one_run(monkeypatch) -> None:
    from scripts.tools.wechat_mp_hotspot_article import codex_hotspot_min_body_gate

    monkeypatch.setenv("WECHAT_MP_CODEX_HOTSPOT_MIN_BODY", "1500")
    assert codex_hotspot_min_body_gate() == 1500


def test_codex_hotspot_default_minimum_prioritizes_completion_rate(monkeypatch) -> None:
    from scripts.tools.wechat_mp_hotspot_article import codex_hotspot_min_body_gate

    monkeypatch.delenv("WECHAT_MP_CODEX_HOTSPOT_MIN_BODY", raising=False)
    assert codex_hotspot_min_body_gate() == 1800
