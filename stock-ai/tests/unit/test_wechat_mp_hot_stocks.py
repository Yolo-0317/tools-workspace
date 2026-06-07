"""公众号 Top5 · 东财人气榜过滤与池模式。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_stocks import (
    HotStockRow,
    filter_hot_stock_rows,
    hot_rows_to_picks,
    is_hot_stock_eligible,
    top5_pool_mode,
)


def test_top5_pool_mode_default_hot(monkeypatch):
    monkeypatch.delenv("WECHAT_MP_TOP5_POOL", raising=False)
    assert top5_pool_mode() == "hot"


def test_top5_pool_mode_traffic_alias(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_TOP5_POOL", "traffic")
    assert top5_pool_mode() == "hot"


def test_is_hot_stock_eligible_rejects_st():
    assert not is_hot_stock_eligible("600123", "*ST景谷")
    assert is_hot_stock_eligible("600123", "景谷")


def test_filter_hot_stock_rows_dedup_and_st():
    rows = [
        HotStockRow(1, "000725", "京东方Ａ", 6.5),
        HotStockRow(2, "600123", "*ST测试", 1.0),
        HotStockRow(3, "000725", "京东方Ａ", 6.5),
        HotStockRow(4, "600487", "亨通光电", 4.2),
    ]
    out = filter_hot_stock_rows(rows)
    assert [r.code for r in out] == ["000725", "600487"]


def test_hot_rows_to_picks_score_by_rank():
    picks = hot_rows_to_picks(
        [HotStockRow(1, "000725", "京东方Ａ"), HotStockRow(5, "600487", "亨通光电")],
        top_n=2,
    )
    assert picks[0].code == "000725"
    assert picks[0].score == 100.0
    assert picks[0].label == "东财人气榜"
    assert picks[1].score == 96.0
