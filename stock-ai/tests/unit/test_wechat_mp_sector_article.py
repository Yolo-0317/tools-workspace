"""sector 热点行业研究稿。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_theme import HotThemeReport, ThemeScore, pick_focus_themes
from scripts.tools.wechat_mp_sector_article import (
    _template_sector_body,
    build_sector_digest,
    build_sector_title,
    format_sector_trade_label,
    sector_title_hook,
)
from datetime import date


def test_pick_focus_themes_top_two() -> None:
    report = HotThemeReport(
        trade_date="2026-06-03",
        edition="close",
        themes=[
            ThemeScore(name="动力煤", score=10.0, sources=["emotion"]),
            ThemeScore(name="电力", score=3.0, sources=["news"]),
            ThemeScore(name="半导体", score=1.0, sources=["news"]),
        ],
        primary="动力煤",
        title_tags="动力煤+电力",
        research_hook="",
        fetched_at="",
    )
    picked = pick_focus_themes(report, max_themes=2, min_score=1.5)
    assert [t.name for t in picked] == ["动力煤", "电力"]


def test_format_sector_trade_label() -> None:
    assert format_sector_trade_label(date(2026, 6, 3), edition="close") == "6月3日收盘"


def test_sector_digest_uses_trade_label() -> None:
    themes = [ThemeScore(name="半导体", score=1.0, sources=[])]
    digest = build_sector_digest(themes, trade_date=date(2026, 6, 3), edition="close")
    assert "6月3日收盘" in digest
    assert "今日" not in digest


def test_template_sector_body_uses_trade_label() -> None:
    themes = [ThemeScore(name="半导体", score=1.0, sources=[])]
    body = _template_sector_body(
        context="",
        themes=themes,
        trade_day_label="6月3日收盘",
    )
    assert body.startswith("6月3日收盘")
    assert "今日" not in body


def test_sector_title_hook() -> None:
    themes = [
        ThemeScore(name="动力煤", score=1.0, sources=[]),
        ThemeScore(name="电力", score=1.0, sources=[]),
    ]
    assert sector_title_hook(themes) == "动力煤+电力"
    title = build_sector_title(themes)
    assert "动力煤" in title
    assert len(title) <= 32


def test_sector_title_prefers_lead_stock_when_available(monkeypatch) -> None:
    from scripts.tools.wechat_mp_sector_stocks import SectorSampleStock

    themes = [ThemeScore(name="半导体", score=1.0, sources=[])]

    def _fake_collect(theme_names: list[str]) -> list:
        return [
            SectorSampleStock(
                code="600141",
                name="新安股份",
                source="行业领涨",
                theme="半导体",
            )
        ]

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_sector_stocks.collect_sector_sample_stocks",
        _fake_collect,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_sector_stocks.fetch_hot_stock_watch_rows",
        lambda **_: [],
    )
    title = build_sector_title(themes)
    assert "新安股份" in title
    assert "领涨" in title
    assert "产业链怎么拆" in title


def test_sector_title_prefers_hot_top1_over_industry_lead(monkeypatch) -> None:
    from scripts.tools.wechat_mp_hot_stocks import HotStockRow
    from scripts.tools.wechat_mp_sector_stocks import SectorSampleStock

    monkeypatch.delenv("WECHAT_MP_SECTOR_EVENING_DEDUP", raising=False)
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "manual")

    themes = [ThemeScore(name="半导体", score=1.0, sources=[])]
    hot_rows = [
        HotStockRow(rank=1, code="300418", name="昆仑万维", change_pct=7.2),
        HotStockRow(rank=2, code="600176", name="中国巨石", change_pct=5.1),
    ]

    def _fake_collect(theme_names: list[str]) -> list:
        return [
            SectorSampleStock(
                code="600141",
                name="新安股份",
                source="行业领涨",
                theme="半导体",
            )
        ]

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_sector_stocks.collect_sector_sample_stocks",
        _fake_collect,
    )
    title = build_sector_title(themes, hot_watch_rows=hot_rows)
    assert "昆仑万维" in title
    assert "关联观察" in title
    assert "领衔" not in title
    assert "新安股份" not in title


def test_sector_title_evening_dedup_prefers_industry_lead(monkeypatch) -> None:
    from scripts.tools.wechat_mp_hot_stocks import HotStockRow
    from scripts.tools.wechat_mp_sector_stocks import SectorSampleStock

    monkeypatch.setenv("WECHAT_MP_SECTOR_EVENING_DEDUP", "1")

    themes = [ThemeScore(name="半导体", score=1.0, sources=[])]
    hot_rows = [
        HotStockRow(rank=1, code="300418", name="昆仑万维", change_pct=7.2),
    ]

    def _fake_collect(theme_names: list[str]) -> list:
        return [
            SectorSampleStock(
                code="600141",
                name="新安股份",
                source="行业领涨",
                theme="半导体",
            )
        ]

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_sector_stocks.collect_sector_sample_stocks",
        _fake_collect,
    )
    title = build_sector_title(themes, hot_watch_rows=hot_rows)
    assert "新安股份" in title
    assert "昆仑万维" not in title


def test_format_hot_stock_watch_section() -> None:
    from scripts.tools.wechat_mp_hot_stocks import HotStockRow
    from scripts.tools.wechat_mp_sector_stocks import (
        HOT_WATCH_SECTION_TITLE,
        format_hot_stock_watch_section,
    )

    rows = [
        HotStockRow(rank=i, code=f"60000{i}", name=f"样例{i}", change_pct=float(i))
        for i in range(1, 11)
    ]
    block = format_hot_stock_watch_section(rows, trade_label="6月8日收盘")
    assert f"> {HOT_WATCH_SECTION_TITLE}" in block
    assert "6月8日收盘" in block
    assert "Top10" in block
    assert block.count("样例") == 10


def test_inject_hot_stock_watch_before_index_link(monkeypatch) -> None:
    from scripts.tools.wechat_mp_hot_stocks import HotStockRow
    from scripts.tools.wechat_mp_sector_polish import inject_hot_stock_watch_section

    monkeypatch.setenv("WECHAT_MP_SECTOR_EVENING_DEDUP", "0")
    monkeypatch.setenv("WECHAT_MP_SECTOR_HOT_WATCH_TOP_N", "10")

    body = "\n".join(
        [
            "> 盘面里谁在用价格说话",
            "盘面正文。",
            "",
            "> 和指数情绪怎么联动",
            "联动正文。",
        ]
    )
    rows = [HotStockRow(rank=1, code="300418", name="昆仑万维", change_pct=3.0)]
    out = inject_hot_stock_watch_section(body, trade_label="6月8日收盘", rows=rows)
    price_pos = out.index("盘面里谁在用价格说话")
    watch_pos = out.index("当日人气观察")
    link_pos = out.index("和指数情绪怎么联动")
    assert price_pos < watch_pos < link_pos
    assert "昆仑万维" in out
