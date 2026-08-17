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
    _hot_stock_fallback_comment,
    _pick_fallback_comment,
    _sanitize_ai_comment,
    generate_enriched_news_copy,
    is_news_ai_llm_configured,
    news_ai_llm_backend,
    news_enriched_llm_enabled,
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


def test_news_enriched_llm_enabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("WECHAT_MP_NEWS_AI_LLM", raising=False)
    assert news_enriched_llm_enabled() is True


def test_news_ai_backend_is_codex_even_when_legacy_env_requests_deepseek(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_NEWS_AI_BACKEND", "deepseek")
    assert news_ai_llm_backend() == "codex"


def test_generate_enriched_news_copy_skips_llm_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_NEWS_AI_LLM", "0")

    def boom(*args, **kwargs):
        raise AssertionError("call_wechat_mp_llm should not run")

    monkeypatch.setattr("scripts.tools.wechat_mp_news_article.call_wechat_mp_llm", boom)
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_news_article.is_news_ai_llm_configured",
        lambda: True,
    )

    items = [{"title": "国际油价大涨", "sentiment": "bullish", "summary": "布伦特突破 90 美元"}]
    out = generate_enriched_news_copy(items)
    assert len(out) == 1
    headline, summary, ai = out[0]
    assert headline
    assert summary
    assert ai
    for phrase in _AI_COMMENT_BANNED:
        assert phrase not in ai


def test_generate_enriched_news_copy_uses_codex_result(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_NEWS_AI_LLM", "1")

    def fake_wechat_llm(messages, **kwargs):
        assert kwargs == {"max_tokens": 6000}
        return (
            "1. 小标题：国际油价站上新关口\n"
            "摘要：布伦特原油价格上行，能源运输和化工成本的变化需要结合后续库存数据观察。\n"
            "AI点评：油价变化先影响成本预期，再影响板块内部利润分配。下一步应核对库存、运价和炼化价差是否同步，而不是只看一天涨幅。"
        )

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_news_article.call_wechat_mp_llm",
        fake_wechat_llm,
        raising=False,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_news_article.is_news_ai_llm_configured",
        lambda: True,
    )
    items = [{"title": "国际油价大涨", "sentiment": "bullish", "summary": "布伦特突破 90 美元"}]
    out = generate_enriched_news_copy(items)
    assert out[0][0] == "国际油价站上新关口"


def test_hot_stock_fallback_comments_differ_by_code() -> None:
    a = _hot_stock_fallback_comment(
        {
            "matched_stock_name": "工业富联",
            "matched_stock_code": "601138",
            "matched_stock_rank": 1,
            "matched_stock_change_pct": 7.5,
            "title": "工业富联人气榜首",
            "sentiment": "bullish",
        }
    )
    b = _hot_stock_fallback_comment(
        {
            "matched_stock_name": "兆易创新",
            "matched_stock_code": "603986",
            "matched_stock_rank": 2,
            "matched_stock_change_pct": 7.3,
            "title": "榜2兆易创新大涨",
            "sentiment": "bullish",
        }
    )
    assert a != b
    assert "工业富联" in a
    assert "兆易创新" in b


def test_synthetic_batch_summaries_not_identical(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_NEWS_AI_LLM", "0")
    items = [
        {
            "title": f"榜{i}{name}",
            "summary": (
                f"东财人气榜第{i}位，周三收涨约 {chg:+.2f}%。"
                f"就着收盘人气榜聊下一交易日怎么验证：先看周一竞价是否还有资金接力，"
                f"再看首小时量价是否与人气一致。"
            ),
            "sentiment": "bullish",
            "matched_stock_name": name,
            "matched_stock_code": code,
            "matched_stock_rank": i,
            "matched_stock_change_pct": chg,
            "synthetic": True,
        }
        for i, name, code, chg in (
            (1, "工业富联", "601138", 7.5),
            (2, "兆易创新", "603986", 7.3),
            (3, "太极实业", "600667", 10.0),
        )
    ]
    out = generate_enriched_news_copy(items)
    summaries = [s for _, s, _ in out]
    assert len(set(summaries)) == len(summaries)
    comments = [a for _, _, a in out]
    assert len(set(comments)) == len(comments)
    for phrase in _AI_COMMENT_BANNED:
        assert all(phrase not in c for c in comments)
