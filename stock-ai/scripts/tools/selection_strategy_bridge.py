#!/usr/bin/env python3
"""将 ma5 / 五因子结果规范化并写入 selection_daily_results。"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _code6(ts_code: str) -> str:
    return str(ts_code).split(".")[0].zfill(6)


def _action_from_score(score: float, pct_chg: float) -> str:
    if pct_chg > 5.0:
        return "继续观察"
    if score >= 72:
        return "观察买入"
    if score >= 58:
        return "小仓埋伏"
    return "继续观察"


def ma5_rows_for_db(df: pd.DataFrame) -> list[dict[str, Any]]:
    """stock_selection_ma5 apply_strategy 输出 → 统一列名。"""
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        code = str(r.get("ts_code", ""))
        pct = float(r.get("pct_chg", 0))
        score = float(r.get("composite_score", 0))
        amt_wan = float(r.get("amount", 0)) / 10.0
        rows.append(
            {
                "代码": code,
                "收盘价": float(r.get("close", 0)),
                "涨幅%": pct,
                "成交额(万)": round(amt_wan, 2),
                "策略标签": "MA5回踩",
                "标签数": 1,
                "总分": round(min(100.0, score), 1),
                "信号分": round(float(r.get("early_stage_score", 0)), 1),
                "趋势分": round(float(r.get("ma10_growth_rate", 0)), 1),
                "动量分": round(float(r.get("pct_chg_5d", 0)), 1),
                "流动性分": 0,
                "风险调整": 0,
                "大盘调整": 0,
                "板块调整": 0,
                "共振加分": 0,
                "大盘环境": "—",
                "所属行业": "N/A",
                "建议动作": _action_from_score(score, pct),
                "建议买入(股)": 0,
                "预计金额(元)": 0,
                "超大单净流入(万)": 0,
                "超大单占比%": 0,
            }
        )
    return rows


def bottom_breakout_rows_for_db(df: pd.DataFrame) -> list[dict[str, Any]]:
    """筑底+放量突破（eastmoney 技术面模块）→ 统一列名。"""
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        code = str(r.get("代码", ""))
        pct = float(r.get("涨幅%", 0))
        score = float(r.get("技术分", r.get("总分", 0)))
        tags = str(r.get("策略标签", "筑底,放量突破"))
        rows.append(
            {
                "代码": code,
                "收盘价": float(r.get("收盘价", 0)),
                "涨幅%": pct,
                "成交额(万)": float(r.get("成交额(万)", 0)),
                "策略标签": tags,
                "标签数": len([t for t in tags.split(",") if t.strip()]),
                "总分": round(score, 1),
                "信号分": float(r.get("信号分", 0)),
                "趋势分": float(r.get("趋势分", 0)),
                "动量分": float(r.get("突破分", 0)),
                "流动性分": round(float(r.get("今日量/5日量", 0)) * 10, 1),
                "风险调整": 0,
                "大盘调整": 0,
                "板块调整": 0,
                "共振加分": 0,
                "大盘环境": "—",
                "所属行业": "N/A",
                "建议动作": _action_from_score(score, pct),
                "建议买入(股)": 0,
                "预计金额(元)": 0,
                "超大单净流入(万)": 0,
                "超大单占比%": 0,
            }
        )
    return rows


def five_factor_rows_for_db(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        code = str(r.get("代码", r.get("ts_code", "")))
        pct = float(r.get("涨幅%", 0))
        score = float(r.get("总分", 0))
        rows.append(
            {
                "代码": code,
                "收盘价": float(r.get("收盘价", 0)),
                "涨幅%": pct,
                "成交额(万)": float(r.get("成交额(万)", 0)),
                "策略标签": str(r.get("策略标签", "五因子")),
                "标签数": len(str(r.get("策略标签", "")).split(",")),
                "总分": score,
                "信号分": float(r.get("形态分(25)", 0)),
                "趋势分": float(r.get("趋势分(25)", 0)),
                "动量分": float(r.get("动量分(20)", 0)),
                "流动性分": float(r.get("量能分(15)", 0)),
                "风险调整": 0,
                "大盘调整": 0,
                "板块调整": 0,
                "共振加分": 0,
                "大盘环境": "—",
                "所属行业": "N/A",
                "建议动作": _action_from_score(score, pct),
                "建议买入(股)": 0,
                "预计金额(元)": 0,
                "超大单净流入(万)": 0,
                "超大单占比%": 0,
            }
        )
    return rows


def persist_strategy_rows(
    trade_date: str | date,
    rows: list[dict[str, Any]],
    strategy: str,
    *,
    csv_stem: str | None = None,
) -> int:
    from scripts.tools.portfolio_db import load_account, save_selection_daily_results

    account_position_pct = 0.0
    try:
        from stock_ai.advisor_selection import parse_advisor_phase, reapply_advisor_to_rows

        acct = load_account()
        if acct and acct.position_ratio is not None:
            r = float(acct.position_ratio)
            account_position_pct = r * 100 if r <= 1.0 else r
        if rows:
            phase = parse_advisor_phase()
            reapply_advisor_to_rows(
                rows, phase=phase, account_position_pct=account_position_pct
            )
            rows = [r for r in rows if r.get("建议动作") != "禁止"]
    except ImportError:
        pass

    n = save_selection_daily_results(trade_date, rows, strategy=strategy)
    td = (
        trade_date.strftime("%Y%m%d")
        if isinstance(trade_date, date)
        else str(trade_date).replace("-", "")[:8]
    )
    if csv_stem:
        out = ROOT / "output" / f"{csv_stem}_{td}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"{strategy} CSV: {out}")
    print(f"MySQL selection_daily_results ({strategy}): {n} 条")
    return n
