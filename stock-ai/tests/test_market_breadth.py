"""market_breadth / board_filters 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core_v2"))

from board_filters import (  # noqa: E402
    KCB_BOARD,
    board_action_threshold_overrides,
    should_block_weak_market,
)
from market_breadth import compute_daily_breadth, regime_from_up_ratio  # noqa: E402


def test_regime_from_up_ratio():
    assert regime_from_up_ratio(0.40) == "weak"
    assert regime_from_up_ratio(0.50) == "neutral"
    assert regime_from_up_ratio(0.65) == "strong"


def test_compute_daily_breadth():
    df = pd.DataFrame(
        {
            "ts_code": ["688001", "688002", "688003", "688004"],
            "trade_date": ["2025-01-02"] * 4,
            "pct_chg": [1.0, -1.0, 2.0, -0.5],
        }
    )
    m = compute_daily_breadth(df, min_stocks=3)
    assert m["20250102"] == 0.5


def test_kcb_weak_block():
    assert should_block_weak_market(KCB_BOARD, market_regime="weak")
    assert not should_block_weak_market(KCB_BOARD, market_regime="neutral")
    assert not should_block_weak_market(KCB_BOARD, market_regime="strong")


def test_kcb_threshold_overrides():
    ov = board_action_threshold_overrides(KCB_BOARD)
    assert ov is not None
    assert ov["观察买入"] == 55.0
    ov_n = board_action_threshold_overrides(KCB_BOARD, market_regime="neutral")
    assert ov_n is not None and ov_n["观察买入"] == 58.0
