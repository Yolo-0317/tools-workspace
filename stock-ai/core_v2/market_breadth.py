"""板块涨跌广度与大盘环境判定（供选股 / 回测复用）。"""

from __future__ import annotations

import pandas as pd

WEAK_UP_RATIO_MAX = 0.45
STRONG_UP_RATIO_MIN = 0.60


def regime_from_up_ratio(up_ratio: float | None) -> str:
    """weak / neutral / strong。"""
    if up_ratio is None:
        return "neutral"
    if up_ratio < WEAK_UP_RATIO_MAX:
        return "weak"
    if up_ratio > STRONG_UP_RATIO_MIN:
        return "strong"
    return "neutral"


def _norm_date(d) -> str:
    if isinstance(d, str):
        return d.replace("-", "")[:8]
    return pd.Timestamp(d).strftime("%Y%m%d")


def compute_daily_breadth(
    df: pd.DataFrame,
    *,
    code_prefixes: tuple[str, ...] | None = ("688", "689"),
    board_kind: str | None = None,
    min_stocks: int = 50,
) -> dict[str, float]:
    """
    按交易日统计上涨家数占比。
    返回 {YYYYMMDD: up_ratio}。
    board_kind: main / kcb / gem — 优先于 code_prefixes（需 board_filters.detect_board）。
    """
    if df.empty or "pct_chg" not in df.columns:
        return {}

    work = df.copy()
    if "code" not in work.columns:
        work["code"] = work["ts_code"].astype(str).str.split(".").str[0].str.zfill(6)
    work["d"] = work["trade_date"].map(_norm_date)
    if board_kind:
        from board_filters import BoardKind, detect_board

        kind = BoardKind(board_kind)
        work = work[work["code"].map(lambda c: detect_board(c) == kind)]
    elif code_prefixes:
        mask = work["code"].str.startswith(code_prefixes)
        work = work[mask]

    out: dict[str, float] = {}
    for d, g in work.groupby("d"):
        if len(g) < min_stocks:
            continue
        out[str(d)] = float((g["pct_chg"] > 0).mean())
    return out


def regime_for_date(
    breadth_map: dict[str, float],
    trade_date: str,
    *,
    fallback: str = "neutral",
) -> str:
    d = _norm_date(trade_date)
    return regime_from_up_ratio(breadth_map.get(d)) if d in breadth_map else fallback
