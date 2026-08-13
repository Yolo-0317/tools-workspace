from __future__ import annotations

import json

import pandas as pd

from scripts.selection.stock_selection_limit_up_gene import run_selection


def _panel() -> pd.DataFrame:
    raw = [
        ("2026-07-20", 10.00, 10.20, 9.90, 10.10, 1.0, 100_000),
        ("2026-07-21", 10.10, 10.30, 10.00, 10.20, 1.0, 105_000),
        ("2026-07-22", 10.20, 10.40, 10.10, 10.30, 1.0, 110_000),
        ("2026-07-23", 10.30, 10.50, 10.20, 10.40, 1.0, 115_000),
        ("2026-07-24", 10.40, 10.60, 10.30, 10.50, 1.0, 120_000),
        ("2026-07-27", 10.50, 10.70, 10.40, 10.60, 1.0, 125_000),
        ("2026-07-28", 10.60, 10.80, 10.50, 10.70, 1.0, 130_000),
        ("2026-07-29", 10.70, 10.90, 10.60, 10.80, 1.0, 135_000),
        ("2026-07-30", 10.80, 11.00, 10.70, 10.90, 1.0, 140_000),
        ("2026-07-31", 10.90, 12.00, 10.80, 12.00, 10.0, 400_000),
        ("2026-08-03", 12.00, 12.20, 11.95, 12.10, 0.8, 300_000),
        ("2026-08-04", 12.10, 12.35, 10.90, 12.25, 1.2, 260_000),
        ("2026-08-05", 12.25, 12.45, 12.10, 12.30, 0.4, 210_000),
        ("2026-08-06", 12.30, 12.50, 12.15, 12.35, 0.4, 180_000),
        ("2026-08-07", 12.35, 12.55, 12.20, 12.40, 0.4, 160_000),
        ("2026-08-10", 12.40, 12.55, 12.25, 12.42, 0.2, 150_000),
        ("2026-08-11", 12.42, 12.55, 12.28, 12.44, 0.2, 140_000),
        ("2026-08-12", 12.44, 12.65, 12.30, 12.46, 0.2, 130_000),
        ("2026-08-13", 12.46, 13.71, 12.46, 13.71, 10.0, 500_000),
    ]
    return pd.DataFrame(
        [
            {
                "ts_code": "600000.SH",
                "trade_date": day,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "pct_chg": pct,
                "amount": amount,
            }
            for day, open_price, high, low, close, pct, amount in raw
        ]
    )


def test_runner_uses_only_bars_through_trade_date() -> None:
    rows = run_selection(
        _panel(),
        trade_date="2026-08-12",
        names={"600000": "测试股份"},
        risks={},
    )

    assert len(rows) == 1
    assert rows.iloc[0]["数据截止"] == "2026-08-12"
    assert rows.iloc[0]["建议动作"] == "蓄势观察，等待次日确认"
    assert "2026-08-13" not in rows.iloc[0]["原始指标"]
    assert rows.iloc[0]["决策周期"] == "3-5个交易日"
    assert rows.iloc[0]["当前仓位建议"] == "0%（观察期）"
    assert "突破" in rows.iloc[0]["入场触发"]
    assert "不追" in rows.iloc[0]["追高纪律"]


def test_material_risk_veto_removes_preselected_candidate() -> None:
    rows = run_selection(
        _panel(),
        trade_date="2026-08-12",
        names={"600000": "测试股份"},
        risks={"600000": (True, ("重大风险公告",))},
    )

    assert rows.empty


def test_output_discloses_missing_confirmation_fields() -> None:
    rows = run_selection(
        _panel(),
        trade_date="2026-08-12",
        names={"600000": "测试股份"},
        risks={},
    )

    missing = json.loads(rows.iloc[0]["缺失字段"])
    assert "auction_strength" in missing
    assert "seal_quality" in missing
    raw = json.loads(rows.iloc[0]["原始指标"])
    assert raw["auction_strength"] is None
