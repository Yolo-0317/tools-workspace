"""综合选股成交额单位与流动性分（D 阶段）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()
sys.path.insert(0, str(ROOT / "core_v2"))

import importlib

_mod = importlib.import_module("stock_selection_combined")
LIQUIDITY_SCORE_CAP_WAN = _mod.LIQUIDITY_SCORE_CAP_WAN
MIN_AMOUNT_QIAN = _mod.MIN_AMOUNT_QIAN
amount_qian_to_wan = _mod.amount_qian_to_wan
liquidity_score_from_wan = _mod.liquidity_score_from_wan


def test_amount_qian_to_wan():
    assert amount_qian_to_wan(50_000) == 5_000.0
    assert amount_qian_to_wan(10) == 1.0


def test_min_amount_qian_is_5000_wan():
    assert MIN_AMOUNT_QIAN == 50_000


def test_liquidity_score_cap():
    assert liquidity_score_from_wan(0) == 0.0
    assert liquidity_score_from_wan(100_000) == 5.0  # 10 亿元
    assert liquidity_score_from_wan(LIQUIDITY_SCORE_CAP_WAN) == 10.0  # 20 亿元
    assert liquidity_score_from_wan(LIQUIDITY_SCORE_CAP_WAN * 2) == 10.0


def test_market_regime_and_action():
    assert _mod.classify_market_regime(0.35) == "weak"
    assert _mod.classify_market_regime(0.55) == "neutral"
    assert _mod.classify_market_regime(0.65) == "strong"
    assert abs(_mod.close_strength_ratio(10.0, 9.0, 9.9) - 0.9) < 1e-9
    assert (
        _mod.assign_action(64, is_ambush_only=False, regime="weak") == "继续观察"
    )
    assert _mod.assign_action(72, is_ambush_only=False, regime="weak") == "观察买入"
