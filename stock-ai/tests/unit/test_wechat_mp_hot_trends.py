"""微博/百度热搜 → hotspot 选题。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_trends import (
    TrendRow,
    merge_and_rank_trends,
)
from scripts.tools.wechat_mp_hotspot_article import hotspot_merged_llm, hotspot_source, pick_hotspot_topics


def test_merge_and_rank_prefers_discussion_over_finance():
    weibo = [
        TrendRow(title="A股科技退潮", source="weibo", rank=18),
        TrendRow(title="九门开播", source="weibo", rank=2),
    ]
    baidu = [
        TrendRow(title="A股存储芯片概念震荡回升", source="baidu", rank=15),
        TrendRow(title="功夫女足票房逆跌", source="baidu", rank=8),
    ]
    items = merge_and_rank_trends(weibo, baidu, limit=5)
    assert items
    titles = [str(x["title"]) for x in items]
    assert titles[0] in {"九门开播", "功夫女足票房逆跌"}
    assert all("A股" not in t for t in titles[:1])


def test_hotspot_source_defaults_trends(monkeypatch):
    monkeypatch.delenv("WECHAT_MP_HOTSPOT_SOURCE", raising=False)
    assert hotspot_source() == "trends"


def test_hotspot_merged_llm_off_for_trends(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_HOTSPOT_SOURCE", "trends")
    monkeypatch.delenv("WECHAT_MP_HOTSPOT_MERGED_LLM", raising=False)
    assert hotspot_merged_llm() is False


def test_pick_hotspot_from_trend_items(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_HOTSPOT_LLM_PICK", "0")
    items = [
        {
            "title": "A股科技退潮",
            "summary": "微博热搜",
            "href": "trend://weibo",
            "attention_score": 2000.0,
            "sentiment": "neutral",
        },
        {
            "title": "九门开播",
            "summary": "微博热搜",
            "href": "trend://weibo",
            "attention_score": 500.0,
            "sentiment": "neutral",
        },
    ]
    topics = pick_hotspot_topics(items, limit=1, trade_label="7月30日收盘")
    assert len(topics) == 1
    assert "A股" in topics[0].section_title or "科技" in topics[0].section_title
