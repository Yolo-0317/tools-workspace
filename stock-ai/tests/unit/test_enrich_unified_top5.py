"""合并 Top5 选股代码解析（enrich 用）。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools.selection_results import pick_unified_top5


def test_pick_unified_top5_dedup_highest_score(monkeypatch):
    td = date(2026, 6, 3)
    universe = pd.DataFrame(
        [
            {"代码": "600483", "总分": 80.0, "建议动作": "继续观察", "策略来源": "综合"},
            {"代码": "600483", "总分": 70.0, "建议动作": "继续观察", "策略来源": "五因子"},
            {"代码": "600863", "总分": 75.0, "建议动作": "继续观察", "策略来源": "综合"},
            {"代码": "600110", "总分": 90.0, "建议动作": "继续观察", "策略来源": "观察池"},
            {"代码": "002815", "总分": 85.0, "建议动作": "继续观察", "策略来源": "观察池"},
            {"代码": "603697", "总分": 84.0, "建议动作": "继续观察", "策略来源": "观察池"},
            {"代码": "601939", "总分": 83.0, "建议动作": "继续观察", "策略来源": "观察池"},
        ]
    )

    def fake_merge(*, trade_date=None, strategies=None):
        return td, universe, "test@2026-06-03"

    monkeypatch.setattr(
        "scripts.tools.selection_results.merge_selection_strategies_df",
        fake_merge,
    )

    got_td, codes, source = pick_unified_top5(trade_date=td, top_n=5)
    assert got_td == td
    assert source == "test@2026-06-03"
    assert codes == ["600110", "002815", "603697", "601939", "600483"]


def test_pick_unified_top5_empty_universe(monkeypatch):
    td = date(2026, 6, 3)
    empty = pd.DataFrame(columns=["代码", "总分", "建议动作"])

    def fake_merge(*, trade_date=None, strategies=None):
        return td, empty, "empty"

    monkeypatch.setattr(
        "scripts.tools.selection_results.merge_selection_strategies_df",
        fake_merge,
    )

    got_td, codes, _ = pick_unified_top5(trade_date=td, top_n=5)
    assert got_td == td
    assert codes == []
