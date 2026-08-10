"""board_filters 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core_v2"))

from board_filters import (  # noqa: E402
    KCB_BOARD,
    MAIN_BOARD,
    detect_board,
    get_board_params,
    passes_base_filter,
    passes_crash_filter,
)


def test_detect_board():
    assert detect_board("688256") == detect_board("688256.SH")
    assert detect_board("300750") != detect_board("688256")


def test_kcb_price_range():
    assert passes_base_filter("688256", 200.0, KCB_BOARD.min_amount_qian)
    assert not passes_base_filter("688256", 200.0, KCB_BOARD.min_amount_qian, legacy_unified=True)
    assert not passes_base_filter("688256", 8.0, 60_000)
    assert not passes_base_filter("688256", 200.0, 30_000)  # 低于 3000 万门槛


def test_kcb_crash_limits():
    assert passes_crash_filter("688256", -10.0)
    assert not passes_crash_filter("688256", -15.0)
    assert passes_crash_filter("600000", -5.0)
    assert not passes_crash_filter("600000", -8.0)


def test_legacy_unified():
    p = get_board_params("688981", legacy_unified=True)
    assert p.max_price == MAIN_BOARD.max_price
