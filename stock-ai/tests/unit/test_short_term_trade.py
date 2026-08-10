from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.short_term_trade import build_trade_candidates


def test_trade_candidates_filter_chase_and_existing_holdings() -> None:
    rows = pd.DataFrame([
        {"代码": "000001", "总分": 80, "涨幅%": 3, "成交额(万)": 20000, "策略标签": "空中加油", "策略来源": "MA5"},
        {"代码": "000002", "总分": 90, "涨幅%": 8, "成交额(万)": 30000, "策略标签": "大底突破", "策略来源": "综合"},
        {"代码": "000003", "总分": 90, "涨幅%": 2, "成交额(万)": 30000, "策略标签": "大底突破", "策略来源": "综合"},
        {"代码": "000004", "总分": 85, "涨幅%": 2, "成交额(万)": 30000, "策略标签": "大底突破", "策略来源": "综合"},
    ])
    out = build_trade_candidates(rows, holding_codes={"000003"})
    assert out["代码"].tolist() == ["000004"]
    assert out.iloc[0]["建议动作"] == "模拟跟踪，盘中五项确认后才可小仓"
    assert out.iloc[0]["候选类型"] == "突破启动"
    assert not bool(out.iloc[0]["盘中确认"])
