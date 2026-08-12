from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.dual_pool_selection import merge_dual_pool_rows
from stock_ai.news_impact import NewsEvent


NOW = datetime(2026, 8, 12, 18, 0, tzinfo=timezone(timedelta(hours=8)))


def _event(**changes) -> NewsEvent:
    values = {
        "event_id": "coreweave-capex",
        "title": "CoreWeave上调资本开支",
        "summary": "AI云厂商提高数据中心资本开支",
        "published_at": NOW - timedelta(hours=2),
        "observed_at": NOW,
        "source_url": "https://example.com/coreweave",
        "source_name": "公司官网",
        "source_tier": "official",
        "market": "US",
        "country": "US",
        "subjects": ("CoreWeave",),
        "event_type": "capex",
        "direction": "positive",
        "confirmation_state": "official",
        "scope": "overseas",
        "evidence": "资本开支上调",
    }
    values.update(changes)
    return NewsEvent(**values)


TECH_LOTUS = {
    "代码": "600186",
    "名称": "莲花控股",
    "所属行业": "食品",
    "所属概念": "算力租赁,数据中心",
    "总分": 80.0,
    "标签数": 3,
    "成交额(万)": 18000,
    "策略来源": "综合",
    "建议动作": "继续观察",
}


def test_positive_news_enriches_score_but_does_not_upgrade_action():
    result = merge_dual_pool_rows([TECH_LOTUS], [_event()], now=NOW)

    row = result.technical_rows[0]
    assert row["候选池来源"] == "both"
    assert row["建议动作"] == "继续观察"
    assert row["技术原始分"] == 80.0
    assert row["消息影响分"] == 2.4
    assert row["总分"] == 81.2
    assert row["消息事件数"] == 1
    assert row["消息主题"] == "ai_cloud"


def test_event_only_stocks_are_non_actionable_watch_rows():
    result = merge_dual_pool_rows([], [_event()], now=NOW)

    lotus = next(row for row in result.event_watch_rows if row["代码"] == "600186")
    assert lotus["候选池来源"] == "event_watch"
    assert lotus["建议动作"] == "消息观察，等待技术确认"
    assert lotus["交易资格"] == "无技术信号，不进入可执行Top5"
    assert lotus["消息主题"] == "ai_cloud"


def test_official_material_negative_vetoes_new_risk():
    bad = _event(
        event_id="lotus-investigation",
        title="莲花控股被立案调查",
        summary="监管机构正式立案",
        source_name="交易所公告",
        market="CN",
        country="CN",
        subjects=("莲花控股",),
        event_type="investigation",
        direction="negative",
        scope="a_share",
    )

    row = merge_dual_pool_rows([TECH_LOTUS], [bad], now=NOW).technical_rows[0]
    assert row["候选池来源"] == "vetoed"
    assert row["建议动作"] == "禁止新交易"
    assert "莲花控股被立案调查" in row["消息否决原因"]


def test_empty_news_preserves_technical_scores_and_order():
    rows = [
        TECH_LOTUS,
        {
            **TECH_LOTUS,
            "代码": "003816",
            "名称": "中国广核",
            "所属行业": "电力",
            "所属概念": "核电",
            "总分": 78.0,
        },
    ]

    result = merge_dual_pool_rows(rows, [], now=NOW, coverage_status="不足")

    assert [row["代码"] for row in result.technical_rows] == ["600186", "003816"]
    assert [row["总分"] for row in result.technical_rows] == [80.0, 78.0]
    assert all(row["候选池来源"] == "technical" for row in result.technical_rows)
    assert all(row["消息覆盖状态"] == "不足" for row in result.technical_rows)
    assert result.event_watch_rows == ()


def test_positive_news_adjustment_is_capped_at_six_points():
    events = [
        _event(event_id=f"event-{index}", subjects=(subject,))
        for index, subject in enumerate(("CoreWeave", "Nebius", "Supermicro"))
    ]

    row = merge_dual_pool_rows([TECH_LOTUS], events, now=NOW).technical_rows[0]
    assert row["总分"] - row["技术原始分"] <= 6.0


def test_expired_news_does_not_create_event_watch_rows():
    stale = _event(published_at=NOW - timedelta(hours=25))

    result = merge_dual_pool_rows([], [stale], now=NOW)
    assert result.event_watch_rows == ()
