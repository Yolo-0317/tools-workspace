"""要闻 AI 点评：禁套话、fallback 差异化。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_news_article import (
    _AI_COMMENT_BANNED,
    _finalize_ai,
    _infer_news_angle,
    _pick_fallback_comment,
    _sanitize_ai_comment,
)


def test_sanitize_ai_comment_strips_banned_phrases():
    raw = (
        "对 A 股而言，短线资金往往会先做情绪定价，"
        "若与当前主线共振则结构分化，向后看建议跟踪龙头。"
    )
    out = _sanitize_ai_comment(raw)
    for phrase in _AI_COMMENT_BANNED:
        assert phrase not in out


def test_finalize_ai_does_not_pad_with_template_cliches():
    item = {"title": "伊朗局势升级", "sentiment": "bearish"}
    out = _finalize_ai("油服可能先动。", item)
    for phrase in _AI_COMMENT_BANNED:
        assert phrase not in out
    assert len(out) >= 60


def test_fallback_comments_vary_by_topic():
    energy = _pick_fallback_comment({"title": "国际油价大涨", "sentiment": "bullish"})
    chip = _pick_fallback_comment({"title": "半导体设备订单激增", "sentiment": "bullish"})
    assert energy != chip
    for text in (energy, chip):
        for phrase in _AI_COMMENT_BANNED:
            assert phrase not in text


def test_infer_news_angle_has_concrete_watch():
    angle = _infer_news_angle({"title": "美联储维持利率不变", "sentiment": "neutral"})
    assert "北向" in angle["watch"] or "美债" in angle["watch"]
    assert len(angle["comments"]) >= 2
