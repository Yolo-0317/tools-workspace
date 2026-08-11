"""A 股市场代码口径（沪深 vs 北交所）。"""

from __future__ import annotations


def normalize_code6(ts_code: str) -> str:
    raw = str(ts_code).split(".")[0]
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 6:
        return digits[:6]
    return raw.zfill(6) if raw.isdigit() else digits.zfill(6) if digits else raw


def is_bj_bse_code(ts_code: str) -> bool:
    """北交所（含 920xxx 新码与 83/87/43 等旧码）。"""
    s = str(ts_code).strip().upper()
    if s.endswith(".BJ"):
        return True
    c = normalize_code6(ts_code)
    if c.startswith("92"):
        return True
    return c.startswith(("83", "87", "88", "43", "40", "82", "81"))


def is_sh_sz_a_share(ts_code: str) -> bool:
    """沪深 A 股范围（排除北交所）。"""
    return not is_bj_bse_code(ts_code)


def is_sh_sz_main_board_code(ts_code: str) -> bool:
    """沪深主板 A 股代码，排除 B 股、创业板、科创板和北交所。"""
    code = normalize_code6(ts_code)
    return code.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))
