"""东财股吧 sector 正文生成。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_guba_sector import (
    GUBA_CTA_A,
    _build_guba_splits_from_parts,
    _unique_guba_topic_count,
    compose_guba_title,
    format_guba_topic,
    guba_copy_safe_text,
    guba_exchange_suffix,
    guba_max_stocks_per_post,
    split_guba_post_from_body,
)
from scripts.tools.wechat_mp_hot_stocks import HotStockRow
from scripts.tools.wechat_mp_hot_theme import ThemeScore
from scripts.tools.wechat_mp_sector_stocks import SectorSampleStock


def test_guba_exchange_suffix():
    assert guba_exchange_suffix("605006") == "SH"
    assert guba_exchange_suffix("000681") == "SZ"
    assert guba_exchange_suffix("300418") == "SZ"


def test_guba_copy_safe_text_normalizes_punctuation():
    raw = "6月10日收盘｜光伏→制造 \u200b【标题】东财股吧·收盘，上证+1%"
    out = guba_copy_safe_text(raw)
    assert "｜" not in out
    assert "→" not in out
    assert "【" not in out
    assert "·" not in out
    assert "|" in out
    assert "[标题]" in out
    assert "，" in out


def test_build_guba_draft_article_plain_text_content(monkeypatch, tmp_path):
    from scripts.tools import wechat_mp_guba_sector as mod

    class FakePost:
        trade_label = "6月10日收盘"
        title = "6月10日收盘|测试 $隆基绿能(SH601012)$"
        body = "正文第一行\n正文第二行"
        full_text = "【标题】\n" + title + "\n\n【正文】\n" + body

    monkeypatch.setattr(mod, "_resolve_guba_post", lambda **kw: FakePost())
    monkeypatch.setattr(mod, "GUBA_OUTPUT_PATH", tmp_path / "guba.txt")
    article = mod.build_guba_draft_article()
    content = article["content"]
    assert "<" not in content and "&gt;" not in content
    assert "[标题]" in content
    assert "[正文]" in content
    assert "正文第一行" in content
    assert "content_source_url" not in article


def test_compose_guba_title_keeps_complete_topics():
    stocks = [
        SectorSampleStock("002119", "康强电子", "行业领涨", "半导体材料", ""),
        SectorSampleStock("000631", "顺发恒能", "行业领涨", "其他能源发电", ""),
        SectorSampleStock("600176", "中国巨石", "人气观察", "半导体材料", ""),
        SectorSampleStock("601012", "隆基绿能", "人气观察", "其他能源发电", ""),
    ]
    title = compose_guba_title(
        "6月10日收盘",
        ["半导体材料", "其他能源发电"],
        stocks,
    )
    assert len(title) <= 36
    assert title.count("$") % 2 == 0
    assert "(SZ002119)$" in title or "(SZ000631)$" in title
    assert "(SZ0021" not in title or title.endswith("(SZ002119)$")


def test_guba_cta_names_brand():
    assert "牛马也智能" in GUBA_CTA_A
    assert "搜" in GUBA_CTA_A
    assert "微信" not in GUBA_CTA_A
    assert "公众号" not in GUBA_CTA_A


def test_format_guba_topic():
    s = SectorSampleStock(
        code="605006",
        name="山东玻纤",
        source="行业领涨",
        theme="玻纤",
        detail="板块+9.7%",
    )
    assert format_guba_topic(s) == "$山东玻纤(SH605006)$"


def test_build_guba_sector_post_monkeypatch(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_GUBA_MODE", "sector")
    from scripts.tools import wechat_mp_guba_sector as mod

    theme_list = [
        ThemeScore(name="玻纤", score=3.0, sources=["board"]),
        ThemeScore(name="图片媒体", score=2.5, sources=["board"]),
    ]

    class FakeReport:
        trade_date = "2026-06-09"
        edition = "close"
        themes = theme_list
        primary = "玻纤"

    stocks = [
        SectorSampleStock("605006", "山东玻纤", "行业领涨", "玻纤", "板块+9.7%"),
        SectorSampleStock("600176", "中国巨石", "人气观察", "玻纤", "涨跌+8%"),
        SectorSampleStock("000681", "视觉中国", "行业领涨", "图片媒体", "板块+10%"),
        SectorSampleStock("300418", "昆仑万维", "人气观察", "图片媒体", "涨跌+7%"),
    ]

    monkeypatch.setattr(mod, "discover_sector_hot_themes", lambda **kw: FakeReport())
    monkeypatch.setattr(mod, "pick_focus_themes", lambda *a, **kw: theme_list)
    monkeypatch.setattr(mod, "resolve_sector_trade_date", lambda *a, **kw: __import__("datetime").date(2026, 6, 9))
    monkeypatch.setattr(mod, "_board_theme_chg", lambda names: {"玻纤": "约+9.0%", "图片媒体": "约+10.0%"})
    monkeypatch.setattr(mod, "_index_hook_line", lambda: "上证+1.28%")
    monkeypatch.setattr(mod, "collect_sector_sample_stocks", lambda *a, **kw: stocks)
    monkeypatch.setattr(
        "scripts.tools.fetch_eastmoney_quotes.fetch_hot_industry_board_rows_opencli",
        lambda *a, **kw: [],
    )

    post = mod.build_guba_sector_post(edition="close")
    assert "$山东玻纤(SH605006)$" in post.title or "$山东玻纤(SH605006)$" in post.body
    assert post.body.count("$") >= 8  # 4 topics × 2 $ each
    assert GUBA_CTA_A in post.body
    assert "微信" not in post.body
    assert "公众号" not in post.body
    assert len(post.stocks) == 4

    splits = _build_guba_splits_from_parts(
        trade_label=post.trade_label,
        theme_names=list(post.themes),
        stocks=list(post.stocks),
        chg_map={"玻纤": "约+9.0%", "图片媒体": "约+10.0%"},
        index_line="上证+1.28%",
    )
    assert len(splits) == 2
    assert guba_max_stocks_per_post() == 3
    for sp in splits:
        assert len(sp.title) <= 36
        assert _unique_guba_topic_count(sp.body) <= 3
        assert GUBA_CTA_A in sp.body


def test_split_guba_post_from_body_legacy():
    body = (
        "$兴发集团(SH600141)$、$川金诺(SZ300505)$、$康强电子(SZ002119)$、"
        "$江丰电子(SZ300666)$ 所在链条，6月10日收盘磷肥及磷化工约+5.3%、半导体材料约+4.6%。\n\n"
        "【为什么现在看】\n磷肥及磷化工 约+5.3%偏行业主线一。\n半导体材料 约+4.6%偏行业主线二。\n\n"
        "【盘面样本（仅结构观察）】\n"
        "磷肥及磷化工链：\n$兴发集团(SH600141)$：板块5.29%。\n$川金诺(SZ300505)$：涨跌13.66%。\n"
        "半导体材料链：\n$康强电子(SZ002119)$：板块4.62%。\n$江丰电子(SZ300666)$：涨跌20%。\n"
    )
    post = type(
        "P",
        (),
        {
            "title": "6月10日收盘｜磷肥+半导体 $兴发集团(SH600141)$",
            "body": body,
            "trade_label": "6月10日收盘",
            "themes": (),
            "stocks": (),
        },
    )()
    splits = split_guba_post_from_body(post)
    assert len(splits) == 2
    assert _unique_guba_topic_count(splits[0].body) == 2
    assert _unique_guba_topic_count(splits[1].body) == 2


def test_build_guba_hot_stock_splits(monkeypatch):
    from scripts.tools import wechat_mp_guba_sector as mod
    from scripts.tools.wechat_mp_hot_stocks import HotStockRow

    rows = [
        HotStockRow(rank=i, code=f"{600000 + i:06d}", name=f"样例{i}", change_pct=float(i))
        for i in range(1, 13)
    ]
    samples = [mod._hot_row_to_sample(r) for r in rows]
    fake_ctx = mod.GubaHotEnrichment(
        industry_map={str(600000 + i).zfill(6): "半导体" for i in range(1, 13)},
        top_boards=(("半导体材料", 5.0), ("磷化工", 3.0)),
        sector_themes=("半导体材料",),
        news_by_code={},
        index_parts={
            "上证": "3987（-0.16%）",
            "创业板": "3811（-1.13%）",
            "科创50": "1662（+0.62%）",
        },
        index_breadth="",
        next_trade_weekday="周五",
        all_by_code={str(s.code).zfill(6): s for s in samples},
    )
    monkeypatch.setenv("WECHAT_MP_GUBA_MODE", "hot12")
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_stocks.fetch_hot_stock_rows",
        lambda **kw: rows,
    )
    monkeypatch.setattr(mod, "_collect_guba_hot_enrichment", lambda rows, **kw: fake_ctx)
    splits = mod.build_guba_hot_stock_splits(edition="close")
    assert len(splits) == 4
    assert splits[0].total == 4
    assert splits[0].label.startswith("人气Top")
    for sp in splits:
        assert len(sp.title) <= 36
        assert _unique_guba_topic_count(sp.body) <= 3
        assert GUBA_CTA_A in sp.body
        assert "【当日结构" in sp.body
        assert "1）" in sp.body
        assert "微信" not in sp.body
    assert sum(len(sp.stocks) for sp in splits) == 12
