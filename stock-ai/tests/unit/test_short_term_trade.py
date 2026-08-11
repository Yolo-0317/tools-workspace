from __future__ import annotations

from datetime import date, timedelta
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.short_term_trade import build_trade_candidates


ANALYSIS_DATE = date(2026, 8, 10)


def _bars(kind: str) -> list[dict[str, object]]:
    if kind == "breakout":
        closes = [10.0 + index * 0.025 for index in range(64)] + [12.20]
    else:
        closes = [8.0 + index * (2.5 / 54) for index in range(55)] + [
            10.60, 10.80, 11.00, 11.30, 11.60, 12.00, 11.90, 11.75, 11.65, 11.62,
        ]
    bars: list[dict[str, object]] = []
    for index, close in enumerate(closes):
        last = index == len(closes) - 1
        if kind == "breakout" and last:
            open_price, high, low, amount, pct = 11.68, 12.30, 11.80, 225_000.0, 5.4
        elif kind == "pullback" and last:
            open_price, high, low, amount, pct = 11.50, 11.72, 11.40, 90_000.0, -0.26
        else:
            open_price, high, low, amount, pct = close - 0.03, close + 0.10, close - 0.10, 150_000.0, 0.3
        bars.append(
            {
                "trade_date": (ANALYSIS_DATE - timedelta(days=len(closes) - 1 - index)).isoformat(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "pct_chg": pct,
                "amount": amount,
            }
        )
    return bars


def test_trade_candidates_use_bars_for_both_shapes_and_filter_holdings() -> None:
    rows = pd.DataFrame([
        {"代码": "000001", "总分": 80, "涨幅%": 3, "成交额(万)": 20000, "策略标签": "空中加油", "策略来源": "MA5"},
        {"代码": "000003", "总分": 90, "涨幅%": 2, "成交额(万)": 30000, "策略标签": "大底突破", "策略来源": "综合"},
        {"代码": "000004", "总分": 85, "涨幅%": 2, "成交额(万)": 30000, "策略标签": "大底突破", "策略来源": "综合"},
    ])
    bars_by_code = {
        "000001": _bars("pullback"),
        "000003": _bars("breakout"),
        "000004": _bars("breakout"),
    }

    out = build_trade_candidates(
        rows,
        analysis_date=ANALYSIS_DATE,
        bars_by_code=bars_by_code,
        holding_codes={"000003"},
    )

    assert out["代码"].tolist() == ["000001", "000004"]
    assert out.iloc[0]["建议动作"] == "模拟跟踪，盘中五项确认后才可小仓"
    assert out.iloc[0]["候选类型"] == "强趋势回踩"
    assert out.iloc[1]["候选类型"] == "突破启动"
    assert not bool(out.iloc[0]["盘中确认"])
