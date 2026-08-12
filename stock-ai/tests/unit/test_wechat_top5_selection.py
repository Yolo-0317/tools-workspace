"""公众号 Top5 多策略按总分重选。"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.selection_results import merge_selection_strategies_df, pick_wechat_top5
from stock_ai.news_impact import NewsEvent


NOW = datetime(2026, 8, 12, 18, 0, tzinfo=timezone(timedelta(hours=8)))


def _coreweave_event() -> NewsEvent:
    return NewsEvent(
        event_id="coreweave-capex",
        title="CoreWeave上调资本开支",
        summary="AI云厂商提高数据中心资本开支",
        published_at=NOW - timedelta(hours=2),
        observed_at=NOW,
        source_url="https://example.com/coreweave",
        source_name="公司官网",
        source_tier="official",
        market="US",
        country="US",
        subjects=("CoreWeave",),
        event_type="capex",
        direction="positive",
        confirmation_state="official",
        scope="overseas",
        evidence="资本开支上调",
    )


def _sample_frames() -> None:
    combined = pd.DataFrame(
        [
            {
                "代码": "000001",
                "收盘价": 10,
                "涨幅%": 1,
                "总分": 70,
                "策略标签": "A",
                "建议动作": "观察买入",
            },
        ]
    )
    ff = pd.DataFrame(
        [
            {
                "代码": "000002",
                "收盘价": 20,
                "涨幅%": 2,
                "总分": 90,
                "策略标签": "B",
                "建议动作": "强势关注",
            },
            {
                "代码": "000001",
                "收盘价": 10,
                "涨幅%": 1,
                "总分": 85,
                "策略标签": "B2",
                "建议动作": "观察买入",
            },
        ]
    )

    def _fake_load(td, *, strategy: str, engine=None):
        del td, engine
        if strategy == "combined":
            return __import__("datetime").date(2026, 6, 2), combined.to_dict("records")
        if strategy == "five_factor":
            return __import__("datetime").date(2026, 6, 2), ff.to_dict("records")
        return __import__("datetime").date(2026, 6, 2), []

    return _fake_load


@patch("scripts.tools.selection_results.latest_selection_trade_date")
@patch("scripts.tools.selection_results.load_selection_daily_results")
def test_merge_keeps_highest_score_per_code(mock_load, mock_latest) -> None:
    from datetime import date

    mock_latest.return_value = date(2026, 6, 2)
    mock_load.side_effect = _sample_frames()

    td, df, src = merge_selection_strategies_df(
        trade_date=date(2026, 6, 2),
        strategies=("combined", "five_factor"),
    )
    assert "merge" in src
    row = df[df["代码"].astype(str).str.zfill(6).str.endswith("000001")].iloc[0]
    assert float(row["总分"]) == 85
    assert "五因子" in str(row["策略来源"])

    top = pick_wechat_top5(df, top_n=2)
    assert len(top) == 2
    assert float(top.iloc[0]["总分"]) >= float(top.iloc[1]["总分"])


@patch("scripts.tools.selection_results.latest_selection_trade_date")
@patch("scripts.tools.selection_results.load_selection_daily_results")
def test_merge_labels_the_bottom_breakout_source(mock_load, mock_latest) -> None:
    from datetime import date

    mock_latest.return_value = date(2026, 8, 10)
    mock_load.return_value = (
        date(2026, 8, 10),
        [{"代码": "600001", "总分": 88, "建议动作": "强势关注"}],
    )

    _, frame, _ = merge_selection_strategies_df(
        trade_date=date(2026, 8, 10),
        strategies=("bottom_breakout",),
    )

    assert frame.iloc[0]["策略来源"] == "底部突破"


@patch("scripts.tools.selection_results.latest_selection_trade_date")
@patch("scripts.tools.selection_results.load_selection_daily_results")
def test_merge_applies_news_before_top5_ranking(mock_load, mock_latest) -> None:
    mock_latest.return_value = date(2026, 8, 12)
    mock_load.return_value = (
        date(2026, 8, 12),
        [
            {
                "代码": "600186",
                "名称": "莲花控股",
                "所属行业": "食品",
                "所属概念": "算力租赁",
                "总分": 70.0,
                "建议动作": "继续观察",
            },
            {
                "代码": "003816",
                "名称": "中国广核",
                "所属行业": "电力",
                "总分": 70.5,
                "建议动作": "继续观察",
            },
        ],
    )

    _, frame, source = merge_selection_strategies_df(
        trade_date=date(2026, 8, 12),
        strategies=("combined",),
        news_events=[_coreweave_event()],
        now=NOW,
    )

    assert "dual-pool" in source
    assert frame.iloc[0]["代码"] == "600186"
    assert frame.iloc[0]["候选池来源"] == "both"
    assert frame.iloc[0]["消息影响分"] == 2.4


def test_top5_excludes_event_watch_and_vetoed_rows() -> None:
    frame = pd.DataFrame(
        [
            {"代码": "000001", "总分": 99, "候选池来源": "event_watch"},
            {"代码": "000002", "总分": 98, "候选池来源": "vetoed"},
            {"代码": "000003", "总分": 80, "候选池来源": "both"},
            {"代码": "000004", "总分": 79, "候选池来源": "technical"},
        ]
    )

    top = pick_wechat_top5(frame, top_n=5, score_only=True)

    assert list(top["代码"]) == ["000003", "000004"]
