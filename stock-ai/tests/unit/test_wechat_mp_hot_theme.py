"""wechat_mp_hot_theme：多源热门主题挖掘。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_theme import (
    HotThemeReport,
    ThemeScore,
    discover_hot_themes,
    discover_sector_hot_themes,
    format_title_tags,
    pick_focus_themes,
)


def test_discover_uses_news_keywords_when_other_sources_empty(monkeypatch):
    def fake_news(*_a, **_k):
        return [
            {"title": "费城半导体指数大涨，光模块龙头受关注", "summary": "CPO 订单"},
        ]

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_market_edition.load_top_news_for_edition",
        fake_news,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_theme._collect_emotion_themes",
        lambda _s: None,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_theme._collect_selection_themes",
        lambda _s: None,
    )

    report = discover_hot_themes(edition="close", include_opencli=False)
    names = [t.name for t in report.themes]
    assert "半导体" in names
    assert report.primary == "半导体"
    assert "半导体" in report.title_tags


def test_discover_merges_emotion_and_selection(monkeypatch):
    from scripts.tools.wechat_mp_hot_theme import _get

    def fake_emotion(scores):
        _get(scores, "电力").add(4.0, "emotion_main_theme")

    def fake_selection(scores):
        _get(scores, "半导体").add(2.5, "selection_top5")

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_theme._collect_emotion_themes",
        fake_emotion,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_theme._collect_selection_themes",
        fake_selection,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_theme._collect_news_themes",
        lambda *_a, **_k: None,
    )

    report = discover_hot_themes(edition="close", include_opencli=False)
    assert report.primary == "电力"
    assert any(t.name == "半导体" for t in report.themes)


def test_sector_hot_themes_use_opencli_rank_not_emotion(monkeypatch):
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_theme._fetch_eastmoney_industry_board_themes",
        lambda **_: [
            ThemeScore(name="半导体", score=10.0, sources=["eastmoney_industry_board"]),
            ThemeScore(name="光学光电子", score=9.25, sources=["eastmoney_industry_board"]),
        ],
    )

    report = discover_sector_hot_themes(edition="close")
    assert report.primary == "半导体"
    assert report.themes[0].sources == ["eastmoney_industry_board"]
    picked = pick_focus_themes(report, max_themes=2)
    assert [t.name for t in picked] == ["半导体", "光学光电子"]


def test_sector_board_name_filter_rejects_nav_tabs():
    from scripts.tools.wechat_mp_hot_theme import _is_valid_sector_board_name

    assert not _is_valid_sector_board_name("资金流")
    assert not _is_valid_sector_board_name("沪深京板块")
    assert not _is_valid_sector_board_name("行业板块资金流今日排行")
    assert _is_valid_sector_board_name("半导体")
    assert _is_valid_sector_board_name("其他塑料制品")


def test_sector_fallback_when_board_junk(monkeypatch):
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_theme._fetch_eastmoney_industry_board_themes",
        lambda **_: [],
    )

    def fake_selection(scores):
        from scripts.tools.wechat_mp_hot_theme import _get

        _get(scores, "其他塑料制品").add(2.5, "selection_top5")

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_theme._collect_selection_themes",
        fake_selection,
    )

    report = discover_sector_hot_themes(edition="close")
    assert report.primary == "其他塑料制品"


def test_format_title_tags_truncates():
    report = HotThemeReport(
        trade_date="2026-06-03",
        edition="close",
        themes=[ThemeScore(name="半导体", score=3.0, sources=["x"])],
        primary="半导体",
        title_tags="半导体+电力设备",
        research_hook="",
        fetched_at="",
    )
    assert format_title_tags(report, max_len=10) == "半导体+电力设备"[:10]
