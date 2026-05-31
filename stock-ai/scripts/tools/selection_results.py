#!/usr/bin/env python3
"""选股结果读取：MySQL selection_daily_results 优先，CSV 兜底。"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from scripts.tools.portfolio_db import (
    latest_selection_trade_date,
    load_selection_daily_results,
    save_selection_daily_results,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output"


def parse_trade_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip().replace("-", "")
    if len(s) >= 8 and s[:8].isdigit():
        return datetime.strptime(s[:8], "%Y%m%d").date()
    return datetime.fromisoformat(str(value)[:10]).date()


def trade_date_to_str(value: date | str) -> str:
    d = parse_trade_date(value)
    if d is None:
        raise ValueError(f"无效 trade_date: {value}")
    return d.strftime("%Y%m%d")


def find_latest_selection_csv(output_dir: Path | None = None) -> Path | None:
    output_dir = output_dir or OUTPUT_DIR
    files = sorted(output_dir.glob("stock_selection_combined_*.csv"))
    return files[-1] if files else None


def parse_trade_date_from_csv(path: Path) -> date:
    m = re.search(r"(\d{8})$", path.stem)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    return datetime.now().date()


def sort_selection_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    sort_cols = [c for c in ("总分", "标签数", "成交额(万)", "形态分(25)", "涨幅%") if c in df.columns]
    if not sort_cols:
        return df
    return df.sort_values(by=sort_cols, ascending=False)


def import_csv_to_db(csv_path: Path | str, *, strategy: str = "combined") -> int:
    """一次性将 CSV 导入 MySQL（供迁移或补录）。"""
    path = Path(csv_path)
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return 0
    trade_date = parse_trade_date_from_csv(path)
    df = df.where(pd.notnull(df), None)
    rows = df.to_dict(orient="records")
    return save_selection_daily_results(trade_date, rows, strategy=strategy)


def resolve_selection_df(
    *,
    trade_date: date | str | None = None,
    csv_path: Path | str | None = None,
    strategy: str = "combined",
) -> tuple[date, pd.DataFrame, str]:
    """返回 (trade_date, 已排序 DataFrame, 来源标识)。"""
    explicit = parse_trade_date(trade_date) if trade_date else None
    strat = (strategy or "combined").strip() or "combined"

    if csv_path:
        path = Path(csv_path)
        df = pd.read_csv(path, encoding="utf-8-sig")
        td = explicit or parse_trade_date_from_csv(path)
        return td, sort_selection_df(df), f"csv:{path.name}"

    if explicit:
        td, rows = load_selection_daily_results(explicit, strategy=strat)
        if rows:
            return explicit, sort_selection_df(pd.DataFrame(rows)), f"mysql:{strat}"
        fallback = OUTPUT_DIR / f"stock_selection_combined_{explicit.strftime('%Y%m%d')}.csv"
        if strat == "combined" and fallback.exists():
            df = pd.read_csv(fallback, encoding="utf-8-sig")
            return explicit, sort_selection_df(df), f"csv-fallback:{fallback.name}"
        if strat == "five_factor":
            ff = OUTPUT_DIR / f"stock_selection_five_factor_{explicit.strftime('%Y%m%d')}.csv"
            if ff.exists():
                df = pd.read_csv(ff, encoding="utf-8-sig")
                return explicit, sort_selection_df(df), f"csv-fallback:{ff.name}"
        raise FileNotFoundError(f"未找到 {explicit} 的选股结果（MySQL / CSV，strategy={strat}）")

    latest = latest_selection_trade_date(strategy=strat)
    if latest:
        td, rows = load_selection_daily_results(latest, strategy=strat)
        if rows:
            return td or latest, sort_selection_df(pd.DataFrame(rows)), f"mysql:{strat}"

    if strat == "five_factor":
        files = sorted(OUTPUT_DIR.glob("stock_selection_five_factor_*.csv"))
    else:
        files = sorted(OUTPUT_DIR.glob("stock_selection_combined_*.csv"))
    path = files[-1] if files else None
    if path is None:
        raise FileNotFoundError(
            f"未找到选股结果（MySQL selection_daily_results 或 CSV，strategy={strat}）"
        )
    df = pd.read_csv(path, encoding="utf-8-sig")
    return parse_trade_date_from_csv(path), sort_selection_df(df), f"csv:{path.name}"
