"""公众号 Top5 多策略按总分重选。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.selection_results import merge_selection_strategies_df, pick_wechat_top5


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
