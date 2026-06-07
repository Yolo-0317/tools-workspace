"""投顾账户诊断单元测试."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.advisor_diagnosis import (
    build_account_diagnosis,
    build_position_snapshots,
    format_diagnosis_briefing,
)


def _pos(code: str, name: str, shares: int, cost: float):
    return SimpleNamespace(code=code, name=name, shares=shares, cost=cost)


def test_phase0_high_position_low_health():
    positions = [
        _pos("600873", "梅花生物", 700, 13.5),
        _pos("600995", "南网储能", 400, 13.0),
    ]
    diag = build_account_diagnosis(
        total_assets=52962,
        position_ratio_pct=84.4,
        available_cash=8262,
        holding_pnl=-2711,
        positions=positions,
        closes={"600873": 9.5, "600995": 15.5},
        phase=0,
    )
    assert diag["health_score"] < 55
    assert diag["health_label"] in ("需改善", "高风险")
    assert any(i["title"] == "仓位超标" for i in diag["issues"])
    assert any(i["title"] == "毒瘤敞口" for i in diag["issues"])


def test_position_snapshots_weights():
    snaps = build_position_snapshots(
        [_pos("600995", "南网储能", 200, 13.0)],
        total_assets=10000,
        closes={"600995": 15.0},
    )
    assert len(snaps) == 1
    assert snaps[0].weight_pct == 30.0


def test_format_diagnosis_briefing():
    diag = build_account_diagnosis(
        total_assets=50000,
        position_ratio_pct=80,
        available_cash=5000,
        positions=[],
        phase=0,
    )
    text = format_diagnosis_briefing(diag)
    assert "【账户诊断】" in text
    assert "健康度" in text
