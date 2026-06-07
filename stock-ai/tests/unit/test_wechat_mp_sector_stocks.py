"""sector 代表股样本合并。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_stocks import HotStockRow
from scripts.tools.wechat_mp_sector_stocks import (
    collect_sector_sample_stocks,
    theme_matches,
)


def test_theme_matches_partial():
    assert theme_matches("光学光电子", "光学")
    assert theme_matches("橡胶助剂", "橡胶助剂")
    assert not theme_matches("银行", "半导体")


def test_collect_sector_sample_stocks_board_and_hot():
    board_rows = [
        {
            "sector": "玻璃制造",
            "sector_chg": 6.5,
            "leader_name": "三峡新材",
            "leader_chg": 10.0,
            "code": "600293",
        },
        {
            "sector": "半导体",
            "sector_chg": 3.2,
            "leader_name": "北方华创",
            "leader_chg": 5.1,
            "code": "002371",
        },
    ]
    hot_rows = [
        HotStockRow(1, "600293", "三峡新材", 6.5),
        HotStockRow(2, "002371", "北方华创", 4.0),
    ]
    industry_map = {
        "600293": "玻璃制造",
        "002371": "半导体",
    }
    stocks = collect_sector_sample_stocks(
        ["玻璃制造", "半导体"],
        board_rows=board_rows,
        hot_rows=hot_rows,
        industry_map=industry_map,
    )
    codes = [s.code for s in stocks]
    assert "600293" in codes
    assert "002371" in codes
    assert len(stocks) <= 4
    assert all(s.name for s in stocks)


def test_collect_sector_sample_stocks_filters_st():
    board_rows = [
        {
            "sector": "测试行业",
            "leader_name": "*ST测试",
            "code": "600123",
        }
    ]
    stocks = collect_sector_sample_stocks(
        ["测试行业"],
        board_rows=board_rows,
        hot_rows=[],
        industry_map={},
    )
    assert stocks == []
