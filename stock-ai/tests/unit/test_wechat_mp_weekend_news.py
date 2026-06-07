"""周末要闻：热股榜 × 快讯匹配。"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_stocks import HotStockRow
from scripts.tools.wechat_mp_news_article import _sanitize_news_reader_meta
from scripts.tools.wechat_mp_news_article import news_display_headline
from scripts.tools.wechat_mp_weekend_news import (
    _news_matches_stock,
    match_hot_stocks_to_news,
    synthetic_display_title,
    weekend_hot_stock_count,
)

TZ = ZoneInfo("Asia/Shanghai")


def test_sanitize_news_reader_meta_strips_pipeline_jargon():
    raw = (
        "周末未匹配到该股专属 7×24 快讯，本条按「人气股 + 休市舆情」占位："
        "下一交易日看竞价。"
    )
    out = _sanitize_news_reader_meta(raw)
    for bad in ("未匹配", "7×24", "占位", "休市舆情"):
        assert bad not in out
    assert "竞价" in out


def test_synthetic_display_title_uses_price_action_not_template():
    title = synthetic_display_title(
        HotStockRow(rank=1, code="002421", name="达实智能", change_pct=9.92)
    )
    assert "达实智能" in title
    assert "周五人气关注" not in title
    assert "榜首" in title or "涨停" in title


def test_news_display_headline_uses_kuaixun_title():
    item = {
        "title": "派瑞股份：公司股票被实施其他风险警示",
        "matched_stock_name": "派瑞股份",
        "matched_stock_code": "300831",
        "synthetic": False,
    }
    head = news_display_headline(item)
    assert "派瑞股份" in head
    assert "风险警示" in head
    assert "周五人气关注" not in head


def test_weekend_hot_stock_default_is_ten():
    assert weekend_hot_stock_count() == 10


def test_news_matches_stock_by_name_or_code():
    stock = HotStockRow(rank=1, code="600141", name="新安股份", change_pct=1.2)
    item = {"title": "新安股份获机构调研", "summary": "公司回应市场关切"}
    assert _news_matches_stock(item, stock)
    item2 = {"title": "600141 公告", "summary": ""}
    assert _news_matches_stock(item2, stock)


def test_match_hot_stocks_to_news_one_per_stock():
    hot = [
        HotStockRow(rank=1, code="600141", name="新安股份", change_pct=1.0),
        HotStockRow(rank=2, code="601899", name="紫金矿业", change_pct=2.0),
    ]
    pool = [
        {
            "href": "https://finance.eastmoney.com/a/1.html",
            "title": "新安股份发布异动公告",
            "summary": "详情",
            "news_time": "06-07 10:00",
        },
        {
            "href": "https://finance.eastmoney.com/a/2.html",
            "title": "紫金矿业海外项目进展",
            "summary": "详情",
            "news_time": "06-07 11:00",
        },
    ]
    out = match_hot_stocks_to_news(
        hot,
        pool,
        engagement={},
        now=datetime(2026, 6, 7, 12, 0, tzinfo=TZ),
    )
    assert len(out) == 2
    assert out[0]["matched_stock_name"] == "新安股份"
    assert "新安股份" in out[0]["title"]
    assert out[1]["matched_stock_name"] == "紫金矿业"
    assert out[0]["href"] != out[1]["href"]


def test_match_uses_synthetic_when_no_news():
    hot = [HotStockRow(rank=3, code="000001", name="平安银行", change_pct=0.5)]
    anchor = date(2026, 6, 5)
    out = match_hot_stocks_to_news(
        hot,
        [],
        engagement={},
        now=datetime(2026, 6, 7, tzinfo=TZ),
        anchor=anchor,
        anchor_label="6月5日收盘",
    )
    assert len(out) == 1
    assert out[0]["synthetic"] is True
    assert "平安银行" in out[0]["title"]
    assert "周五人气关注" not in out[0]["title"]
    summary = out[0]["summary"]
    for bad in ("未匹配", "7×24", "占位", "专属快讯", "休市舆情", "流水线"):
        assert bad not in summary, f"pipeline jargon in summary: {bad}"
    assert "周五" in summary
    assert "竞价" in summary
