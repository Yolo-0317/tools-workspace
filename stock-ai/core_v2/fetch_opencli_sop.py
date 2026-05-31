"""
东财多维数据：仅 OpenCLI Browser SOP（禁止 HTTP/API 直联）。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd

from scripts.tools.fetch_eastmoney_quotes import (
    EastmoneySopSnapshot,
    fetch_domestic_market_opencli,
    fetch_macro_news_opencli,
    fetch_sop_snapshots,
    parse_fund_flow_text,
)

_sop_cache: dict[str, EastmoneySopSnapshot] = {}


def _code6(code: str) -> str:
    return re.sub(r"\D", "", str(code))[:6].zfill(6)


def prefetch_sop_snapshots(codes: list[str], *, wait_seconds: float = 2.0) -> None:
    global _sop_cache
    snaps = fetch_sop_snapshots(codes, wait_seconds=wait_seconds)
    _sop_cache.update(snaps)


def clear_sop_cache() -> None:
    _sop_cache.clear()


def _get_snapshot(code: str) -> EastmoneySopSnapshot | None:
    c = _code6(code)
    if c in _sop_cache:
        return _sop_cache[c]
    snaps = fetch_sop_snapshots([c])
    if c in snaps:
        _sop_cache[c] = snaps[c]
        return snaps[c]
    return None


def get_stock_fundamental(stock_code: str) -> dict[str, Any]:
    snap = _get_snapshot(stock_code)
    if not snap:
        return {"code": _code6(stock_code), "error": "SOP 采集失败"}

    def _num(label: str) -> float | None:
        raw = snap.label(label)
        if not raw:
            return None
        raw = raw.replace(",", "").replace("%", "").strip()
        try:
            return float(raw)
        except ValueError:
            return None

    pe = _num("市盈(动)") or _num("市盈率(动)") or _num("市盈率")
    pb = _num("市净") or _num("市净率")
    total_mv = _num("总市值")
    circ_mv = _num("流通市值")
    turnover = _num("换手") or _num("换手率")
    vol_ratio = _num("量比")

    return {
        "code": snap.code,
        "name": snap.name,
        "price": snap.price,
        "change_pct": snap.change_pct,
        "pe_ttm": pe,
        "pb": pb,
        "total_mv": total_mv,
        "circ_mv": circ_mv,
        "turnover_rate": turnover,
        "volume_ratio": vol_ratio,
        "source": snap.source,
        "raw_info": snap.info_text,
        "市盈率-动态": pe,
        "市净率": pb,
        "总市值": total_mv,
        "流通市值": circ_mv,
        "换手": turnover,
        "量比": vol_ratio,
    }


def get_stock_fund_flow(stock_code: str) -> dict[str, Any]:
    snap = _get_snapshot(stock_code)
    if not snap:
        return {"code": _code6(stock_code), "error": "SOP 采集失败"}

    parsed = parse_fund_flow_text(snap.fund_flow_text or "")
    main_net = parsed.get("main_net_inflow")
    main_pct = parsed.get("main_net_pct")

    return {
        "code": snap.code,
        "main_net_inflow": main_net,
        "main_net_pct": main_pct,
        "raw": (snap.fund_flow_text or "")[:500],
        "source": snap.source,
        "今日主力净流入": main_net,
        "主力净流入占比": main_pct,
    }


def get_stock_news(stock_code: str, limit: int = 5) -> list[dict[str, str]]:
    _ = stock_code, limit
    return []


def get_market_sentiment() -> dict[str, Any]:
    """指数 + 全 A 涨跌家数：OpenCLI 东财。"""
    indices, breadth_raw = fetch_domestic_market_opencli(
        ["000001", "399001", "399006"],
        include_breadth=True,
    )

    def _fmt(code: str, label: str) -> dict[str, Any]:
        q = indices.get(code)
        if not q:
            return {"name": label, "close": None, "pct_chg": None}
        return {
            "name": label,
            "close": q.price,
            "pct_chg": q.change_pct,
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
        }

    breadth = None
    if breadth_raw and isinstance(breadth_raw.get("total"), dict):
        t = breadth_raw["total"]
        breadth = {
            "up": int(t.get("up", 0)),
            "down": int(t.get("down", 0)),
            "flat": int(t.get("flat", 0)),
            "shanghai": breadth_raw.get("shanghai"),
            "shenzhen": breadth_raw.get("shenzhen"),
        }

    result: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "indices": {
            "shanghai": _fmt("000001", "上证指数"),
            "shenzhen": _fmt("399001", "深证成指"),
            "chinext": _fmt("399006", "创业板指"),
        },
        "breadth": breadth,
        "source": "eastmoney-opencli",
    }
    sh = result["indices"]["shanghai"]
    if sh.get("close") is not None:
        pct = sh.get("pct_chg")
        pct_s = f"{pct:+.2f}%" if pct is not None else "N/A"
        result["上证指数"] = f"{sh['close']} ({pct_s})"
    else:
        result["上证指数"] = "N/A"
    if breadth:
        result["涨跌分布"] = (
            f"上涨{breadth['up']} / 下跌{breadth['down']} / 平{breadth['flat']}"
        )
        total = breadth["up"] + breadth["down"] + breadth["flat"]
        result["up_ratio"] = round(breadth["up"] / total, 4) if total else None
    else:
        result["涨跌分布"] = "N/A"
    return result


def get_all_a_snapshot(limit: int = 100) -> pd.DataFrame:
    _ = limit
    return pd.DataFrame(columns=["code", "close", "pct_chg"])


def get_sector_performance() -> pd.DataFrame:
    return pd.DataFrame(columns=["板块", "涨跌幅"])


def get_macro_news(limit: int = 15) -> list[dict[str, str]]:
    return fetch_macro_news_opencli(limit=limit)
