#!/usr/bin/env python3
"""公众号 Top5 · 东财人气榜候选（流量优先，搜一搜票名对齐）。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.selection_watchlist import SelectionPick, enrich_pick_names


@dataclass(frozen=True)
class HotStockRow:
    rank: int
    code: str
    name: str
    change_pct: float = 0.0


def top5_pool_mode() -> str:
    """hot=东财人气（默认）| selection=多策略总分 | blend=先热股不足再补选股。"""
    raw = os.getenv("WECHAT_MP_TOP5_POOL", "hot").strip().lower()
    if raw in ("traffic", "sousou", "search"):
        return "hot"
    return raw or "hot"


def hot_fetch_top_n() -> int:
    try:
        return max(5, min(20, int(os.getenv("WECHAT_MP_TOP5_HOT_N", "10"))))
    except ValueError:
        return 10


def is_hot_stock_eligible(code: str, name: str) -> bool:
    """合规与流量兼顾：去掉 ST、禁码、北交所（可选）。"""
    c = str(code).split(".")[0].zfill(6)
    n = (name or "").strip()
    if not re.fullmatch(r"\d{6}", c) or len(n) < 2:
        return False
    if re.search(r"ST|\*ST", n, re.I):
        return False
    if os.getenv("WECHAT_MP_TOP5_HOT_SKIP_BJ", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        if c.startswith(("4", "8")):
            return False
    try:
        from stock_ai.advisor_selection import EXCLUDE_CODES

        if c in EXCLUDE_CODES:
            return False
    except ImportError:
        pass
    return True


def normalize_hot_stock_name(raw: str, code: str) -> str:
    """东财人气页 DOM 常把「板 建筑节能 数字孪生」等概念标签粘在股名前，需纠正。"""
    name = (raw or "").strip()
    if not name:
        return name
    try:
        from scripts.tools.portfolio_db import load_stock_names_by_codes

        canonical = (load_stock_names_by_codes([code]) or {}).get(code.zfill(6), "").strip()
        if canonical and len(canonical) <= 12:
            return canonical
    except Exception:
        pass
    if "板" in name or len(name) > 8 or " " in name:
        parts = re.split(r"[\s板]+", name)
        parts = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]
        suffixes = (
            "股份",
            "集团",
            "科技",
            "智能",
            "电子",
            "能源",
            "谐波",
            "数科",
            "传媒",
            "药业",
            "新材",
            "装备",
        )
        for part in reversed(parts):
            if any(part.endswith(s) for s in suffixes):
                return part
        if parts:
            return parts[-1]
    return name


def filter_hot_stock_rows(rows: list[HotStockRow]) -> list[HotStockRow]:
    out: list[HotStockRow] = []
    seen: set[str] = set()
    for row in rows:
        if row.code in seen:
            continue
        if not is_hot_stock_eligible(row.code, row.name):
            continue
        seen.add(row.code)
        out.append(row)
    return out


def _resolve_top5_trade_date(trade_date: date | None) -> date:
    if trade_date is not None:
        return trade_date
    try:
        from scripts.tools.selection_results import latest_selection_trade_date

        latest = latest_selection_trade_date(strategy="combined")
        if latest:
            return latest
    except Exception:
        pass
    from datetime import date as _date

    return _date.today()


def fetch_hot_stock_rows(*, top_n: int | None = None) -> list[HotStockRow]:
    from scripts.tools.fetch_eastmoney_quotes import fetch_hot_stocks_opencli

    n = top_n if top_n is not None else hot_fetch_top_n()
    raw = fetch_hot_stocks_opencli(top_n=max(n, 12))
    rows = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not item.get("code"):
            continue
        code = str(item["code"]).zfill(6)
        raw_name = str(item.get("name") or "").strip()
        rows.append(
            HotStockRow(
                rank=int(item.get("rank") or i + 1),
                code=code,
                name=normalize_hot_stock_name(raw_name, code),
                change_pct=float(item.get("change_pct") or 0.0),
            )
        )
    return filter_hot_stock_rows(rows)


def hot_rows_to_picks(rows: list[HotStockRow], *, top_n: int = 5) -> list[SelectionPick]:
    picks: list[SelectionPick] = []
    for row in rows[:top_n]:
        picks.append(
            SelectionPick(
                code=row.code,
                name=row.name,
                close=0.0,
                change_pct=row.change_pct,
                score=float(101 - row.rank),
                label="东财人气榜",
                action="继续观察",
                in_holdings=False,
            )
        )
    return picks


def load_wechat_top5_hot_picks(
    *,
    top_n: int = 5,
    trade_date: date | None = None,
) -> tuple[date, list[SelectionPick], str]:
    """东财人气 TopN → 过滤 → 取 top_n 只；失败或不足时抛错由上层回退选股。"""
    td = _resolve_top5_trade_date(trade_date)
    rows = fetch_hot_stock_rows(top_n=hot_fetch_top_n())
    if len(rows) < top_n:
        raise ValueError(
            f"东财人气榜可用 {len(rows)} 只（需 {top_n}），请检查 OpenCLI 或放宽过滤"
        )
    picks = enrich_pick_names(hot_rows_to_picks(rows, top_n=top_n))
    tag = f"eastmoney_hot_rank:top{hot_fetch_top_n()}"
    return td, picks, tag


def load_wechat_top5_selection_picks(
    *,
    top_n: int = 5,
    trade_date: date | None = None,
) -> tuple[date, list[SelectionPick], str]:
    """原多策略合并 + 总分重选。"""
    from scripts.tools.selection_results import merge_selection_strategies_df, pick_wechat_top5

    td, universe, source = merge_selection_strategies_df(trade_date=trade_date)
    top_df = pick_wechat_top5(universe, top_n=top_n)
    if top_df.empty:
        raise ValueError(f"合并候选后 Top{top_n} 为空（{source}）")

    picks: list[SelectionPick] = []
    for _, row in top_df.iterrows():
        code = str(row["代码"]).split(".")[0].zfill(6)
        label = str(row.get("策略标签", "") or "")
        src = str(row.get("策略来源", "") or "")
        if src and src not in label:
            label = f"{label}·{src}" if label else src
        picks.append(
            SelectionPick(
                code=code,
                name="",
                close=float(row["收盘价"]),
                change_pct=float(row["涨幅%"]),
                score=float(row.get("总分", 0)),
                label=label,
                action=str(row.get("建议动作", "")),
                in_holdings=False,
            )
        )
    return td, enrich_pick_names(picks), source
