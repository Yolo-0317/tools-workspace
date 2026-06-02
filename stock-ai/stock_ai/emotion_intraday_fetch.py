"""盘中情绪数据：OpenCLI 东财涨停/炸板/跌停池。"""

from __future__ import annotations

from datetime import date
from typing import Any


def fetch_topic_pool(
    kind: str,
    trade_date: date | str,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """拉取题材池；kind=zt|zb|dt。单次 OpenCLI 会话拉齐三类。"""
    from scripts.tools.fetch_eastmoney_quotes import fetch_emotion_topic_pools_opencli

    td = trade_date.isoformat() if isinstance(trade_date, date) else str(trade_date)[:10]
    pools = fetch_emotion_topic_pools_opencli(trade_date=td, close_browser=True)
    return list(pools.get(kind) or [])


def fetch_all_topic_pools(trade_date: date | str) -> dict[str, list[dict[str, Any]]]:
    from scripts.tools.fetch_eastmoney_quotes import fetch_emotion_topic_pools_opencli

    td = trade_date.isoformat() if isinstance(trade_date, date) else str(trade_date)[:10]
    return fetch_emotion_topic_pools_opencli(trade_date=td, close_browser=True)


def fetch_change_pct_batch(codes: list[str]) -> dict[str, float]:
    """批量盘中涨跌幅 %（OpenCLI 个股页快照）。"""
    if not codes:
        return {}
    from scripts.tools.fetch_eastmoney_quotes import fetch_quotes_opencli

    out: dict[str, float] = {}
    chunk = 12
    for i in range(0, len(codes), chunk):
        part = codes[i : i + chunk]
        quotes = fetch_quotes_opencli(part, close_browser=(i + chunk >= len(codes)))
        for code, q in quotes.items():
            out[code] = float(q.change_pct)
    return out


def parse_zt_row(row: dict[str, Any]) -> dict[str, Any]:
    """标准化涨停池一行。"""
    code = str(row.get("c") or "").split(".")[0].zfill(6)
    name = str(row.get("n") or code).strip()
    amount = float(row.get("amount") or 0)
    pct = float(row.get("zdp") or 0)
    board_height = int(row.get("lbc") or 0)
    theme = str(row.get("hybk") or "").strip()
    if board_height <= 0:
        zttj = row.get("zttj") or {}
        if isinstance(zttj, dict):
            board_height = int(zttj.get("ct") or zttj.get("days") or 1)
    return {
        "code": code,
        "name": name,
        "pct_chg": pct,
        "amount_wan": amount / 10_000.0,
        "board_height": max(board_height, 1),
        "main_theme": theme,
    }
