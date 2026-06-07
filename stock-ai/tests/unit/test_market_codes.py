from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.market_codes import is_bj_bse_code, is_sh_sz_a_share, normalize_code6


def test_normalize_code6():
    assert normalize_code6("920128.BJ") == "920128"
    assert normalize_code6("000592.SZ") == "000592"


def test_bj_bse_codes():
    assert is_bj_bse_code("920128")
    assert is_bj_bse_code("920128.BJ")
    assert is_bj_bse_code("430047")
    assert is_bj_bse_code("831010")


def test_sh_sz_codes():
    assert is_sh_sz_a_share("600821")
    assert is_sh_sz_a_share("000592.SZ")
    assert is_sh_sz_a_share("300002")
    assert not is_sh_sz_a_share("920128")
