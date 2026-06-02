"""B 轨观察池：宽松早埋伏 + MA5 贴近（不进 Top5 / 不触发 SOP）。"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from stock_selection_combined import (
    AMBUSH_VOL_RATIO_MAX,
    AMBUSH_VOL_RATIO_MIN,
    BUY_ACTIONS,
    CHASE_PCT_MAX,
    DROP_EXCLUDE_PCT,
    EXCLUDE_BJ,
    EXCLUDE_ST,
    LIMIT_DOWN_PCT,
    MAX_PRICE,
    MIN_AMOUNT_QIAN,
    MIN_PRICE,
    amount_qian_to_wan,
    liquidity_score_from_wan,
    _cap_action_for_redlines,
    _resolve_industry,
)

WATCH_MAX_OUTPUT = 30
WATCH_BOX_LOOKBACK = 250
WATCH_NEAR_TOP_MIN = -10.0
WATCH_NEAR_TOP_MAX = 0.5
WATCH_MA5_DEV_MAX = 2.5
WATCH_MA5_DEV_MIN = -1.5
WATCH_PCT_MIN = -2.0
WATCH_PCT_MAX = 4.0


def _ma5_pullback_lite(
    close: float,
    pct_chg: float,
    ma5: float,
    ma10: float,
    ma20: float,
) -> bool:
    if not (ma5 > ma10 > ma20):
        return False
    if ma5 <= 0:
        return False
    dev = (close - ma5) / ma5 * 100
    if not (WATCH_MA5_DEV_MIN <= dev <= WATCH_MA5_DEV_MAX):
        return False
    return WATCH_PCT_MIN <= pct_chg <= WATCH_PCT_MAX


def _ambush_relaxed(
    group: pd.DataFrame,
    latest: pd.Series,
    close: float,
    pct_chg: float,
    amount_today: float,
    ma20: float,
) -> bool:
    if len(group) < WATCH_BOX_LOOKBACK + 5:
        return False
    box = group.iloc[-WATCH_BOX_LOOKBACK:-5]
    box_high = float(box["high"].max())
    if box_high <= 0:
        return False
    near_top = (close - box_high) / box_high * 100
    ma20_series = group["close"].rolling(20).mean()
    ma20_slope = -999.0
    if len(group) >= 26 and float(ma20_series.iloc[-6]) > 0:
        ma20_slope = (
            (float(ma20_series.iloc[-1]) - float(ma20_series.iloc[-6]))
            / float(ma20_series.iloc[-6])
            * 100
        )
    avg_amt = float(group["amount"].iloc[-10:-5].mean())
    vol_ratio = amount_today / avg_amt if avg_amt > 0 else 0
    return (
        WATCH_NEAR_TOP_MIN <= near_top <= WATCH_NEAR_TOP_MAX
        and ma20_slope >= -0.5
        and AMBUSH_VOL_RATIO_MIN * 0.85 <= vol_ratio <= AMBUSH_VOL_RATIO_MAX * 1.2
        and close >= ma20
        and pct_chg >= WATCH_PCT_MIN
    )


def run_watch_track(
    df_all: pd.DataFrame,
    *,
    trade_date: str,
    industry_map: dict[str, str],
    st_codes: set[str],
    market_regime: str,
    holdings_codes: set[str],
    account_position_pct: float,
) -> list[dict[str, Any]]:
    """扫描 B 轨，返回与 combined CSV 列兼容的字典列表。"""
    results: list[dict[str, Any]] = []
    td_norm = trade_date.replace("-", "")[:8]

    for ts_code, group in df_all.groupby("ts_code"):
        group = group.sort_values("trade_date")
        if len(group) < 60:
            continue
        latest = group.iloc[-1]
        lat = str(latest["trade_date"]).replace("-", "")[:8]
        if lat != td_norm:
            continue

        close = float(latest["close"])
        amount_today = float(latest["amount"])
        code_str = str(ts_code).split(".")[0].zfill(6)
        pct_chg = float(latest["pct_chg"])

        if EXCLUDE_ST and code_str in st_codes:
            continue
        if EXCLUDE_BJ and code_str.startswith("92"):
            continue
        if pct_chg <= DROP_EXCLUDE_PCT or pct_chg <= LIMIT_DOWN_PCT:
            continue
        if not (MIN_PRICE <= close <= MAX_PRICE) or amount_today < MIN_AMOUNT_QIAN:
            continue

        amount_wan = amount_qian_to_wan(amount_today)
        ma5 = float(group["close"].tail(5).mean())
        ma10 = float(group["close"].tail(10).mean())
        ma20 = float(group["close"].tail(20).mean())

        tags: list[str] = []
        if _ambush_relaxed(group, latest, close, pct_chg, amount_today, ma20):
            tags.append("观察-早埋伏")
        if _ma5_pullback_lite(close, pct_chg, ma5, ma10, ma20):
            tags.append("观察-MA5回踩")
        if not tags:
            continue

        signal_score = 10 * len(tags)
        trend_score = 0
        if ma5 > ma10:
            trend_score += 8
        if ma10 > ma20:
            trend_score += 8
        if close >= ma20:
            trend_score += 4
        momentum_score = 6 if pct_chg >= 0 else 2
        liquidity_score = liquidity_score_from_wan(amount_wan)
        total_score = min(
            78.0,
            round(signal_score + trend_score + momentum_score + liquidity_score, 1),
        )

        if total_score >= 62 and pct_chg >= 0:
            action = "小仓埋伏"
        elif total_score >= 52:
            action = "继续观察"
        else:
            action = "谨慎回避"

        if code_str in holdings_codes:
            action = "持有" if action in BUY_ACTIONS else action
        else:
            action = _cap_action_for_redlines(action, pct_chg, account_position_pct)
            if pct_chg > CHASE_PCT_MAX and action in BUY_ACTIONS:
                action = "继续观察"

        if action == "谨慎回避":
            continue

        industry = _resolve_industry(str(ts_code), industry_map)
        results.append(
            {
                "代码": ts_code,
                "收盘价": close,
                "涨幅%": pct_chg,
                "成交额(万)": round(amount_wan, 2),
                "策略标签": ",".join(tags),
                "标签数": len(tags),
                "总分": total_score,
                "信号分": signal_score,
                "趋势分": trend_score,
                "动量分": momentum_score,
                "流动性分": round(liquidity_score, 1),
                "风险调整": 0,
                "大盘调整": 0,
                "板块调整": 0,
                "共振加分": 0,
                "大盘环境": market_regime,
                "所属行业": industry,
                "建议动作": action,
                "建议买入(股)": 0,
                "预计金额(元)": 0,
                "超大单净流入(万)": 0,
                "超大单占比%": 0,
            }
        )

    results.sort(
        key=lambda r: (r["总分"], r["标签数"], r["成交额(万)"]),
        reverse=True,
    )
    return results[:WATCH_MAX_OUTPUT]
