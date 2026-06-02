# coding=utf-8
"""综合选股逻辑复刻（gm 终端版，对齐 core_v2/stock_selection_combined.py）。"""
from __future__ import print_function, absolute_import, unicode_literals

import re

# --- 与 stock_selection_combined.py 保持一致 ---
BOX_PERIOD = 700
BOX_WIDTH_MAX = 80
DIST_FROM_250D_HIGH_MAX = -2
DIST_FROM_250D_LOW_MAX = 100
THREE_UP_MIN_CHG = 1.0
THREE_UP_TOTAL_CHG_MAX = 15.0
THREE_UP_VOL_RATIO = 1.5
PULLBACK_MA20_DIST = 3.0
PULLBACK_PREV_STRENGTH = 20.0
PULLBACK_VOL_DECREASE = 0.8
AMBUSH_NEAR_BOX_TOP_MIN = -8.0
AMBUSH_NEAR_BOX_TOP_MAX = -1.0
AMBUSH_BOX_WIDTH_MAX = 100
AMBUSH_MA20_SLOPE_MIN = 0.0
AMBUSH_VOL_RATIO_MIN = 0.9
AMBUSH_VOL_RATIO_MAX = 1.6
MIN_PRICE = 5
MAX_PRICE = 20
MIN_AMOUNT_QIAN = 50000
LIQUIDITY_SCORE_CAP_WAN = 200000
CHASE_PCT_MAX = 5.0
DROP_EXCLUDE_PCT = -7.0
LIMIT_DOWN_PCT = -9.5
HIGH_POSITION_PCT = 80.0
BREAKOUT_CLOSE_STRENGTH_MIN = 0.55
AMBUSH_SOFT_DIP_PCT = -1.5
SCORE_STRONG_WEAK = 85
SCORE_BUY_WEAK = 70
SCORE_AMBUSH_WEAK = 58
BUY_ACTIONS = frozenset(["强势关注", "观察买入", "小仓埋伏"])
ACTION_WEIGHT = {
    "强势关注": 0.20,
    "观察买入": 0.15,
    "小仓埋伏": 0.05,
    "继续观察": 0.08,
}


def amount_qian_to_wan(amount_qian):
    return float(amount_qian) / 10.0


def liquidity_score_from_wan(amount_wan):
    if amount_wan <= 0:
        return 0.0
    return min(10.0, amount_wan / (LIQUIDITY_SCORE_CAP_WAN / 10.0))


def close_strength_ratio(high, low, close):
    span = float(high) - float(low)
    if span <= 0:
        return 1.0
    return (float(close) - float(low)) / span


def classify_market_regime(up_ratio):
    if up_ratio is None:
        return "neutral"
    if up_ratio < 0.45:
        return "weak"
    if up_ratio > 0.60:
        return "strong"
    return "neutral"


def action_thresholds_for_regime(regime):
    if regime == "weak":
        return {
            "强势关注": SCORE_STRONG_WEAK,
            "观察买入": SCORE_BUY_WEAK,
            "继续观察": 52.0,
            "小仓埋伏": SCORE_AMBUSH_WEAK,
        }
    if regime == "strong":
        return {"强势关注": 78.0, "观察买入": 63.0, "继续观察": 48.0, "小仓埋伏": 53.0}
    return {"强势关注": 80.0, "观察买入": 65.0, "继续观察": 50.0, "小仓埋伏": 55.0}


def assign_action(total_score, is_ambush_only, regime):
    th = action_thresholds_for_regime(regime)
    if is_ambush_only:
        if total_score >= th["小仓埋伏"]:
            return "小仓埋伏"
        if total_score >= th["继续观察"]:
            return "继续观察"
        return "谨慎回避"
    if total_score >= th["强势关注"]:
        return "强势关注"
    if total_score >= th["观察买入"]:
        return "观察买入"
    if total_score >= th["继续观察"]:
        return "继续观察"
    return "谨慎回避"


def cap_action_for_redlines(action, pct_chg, account_position_pct):
    if pct_chg > CHASE_PCT_MAX and action in BUY_ACTIONS:
        return "继续观察"
    if account_position_pct > HIGH_POSITION_PCT and action in BUY_ACTIONS:
        return "继续观察"
    return action


def evaluate_symbol(group, market_regime, market_score_adj):
    """group: pandas DataFrame sorted by date, columns close/open/high/low/amount,pct_chg"""
    import pandas as pd

    if len(group) < 60:
        return None

    latest = group.iloc[-1]
    close_today = float(latest["close"])
    amount_today = float(latest.get("amount") or 0)
    if amount_today <= 0 and "volume" in group.columns:
        amount_today = float(latest.get("volume") or 0) * close_today / 1000.0
    pct_chg_today = float(latest.get("pct_chg") or 0)
    if pct_chg_today == 0 and len(group) >= 2:
        prev = float(group.iloc[-2]["close"])
        if prev > 0:
            pct_chg_today = (close_today / prev - 1.0) * 100.0

    if pct_chg_today <= DROP_EXCLUDE_PCT or pct_chg_today <= LIMIT_DOWN_PCT:
        return None
    if not (MIN_PRICE <= close_today <= MAX_PRICE):
        return None
    if amount_today < MIN_AMOUNT_QIAN:
        return None

    amount_wan = amount_qian_to_wan(amount_today)
    ma5 = group["close"].tail(5).mean()
    ma10 = group["close"].tail(10).mean()
    ma20 = group["close"].tail(20).mean()
    ma60 = group["close"].tail(60).mean()

    is_breakout = False
    if len(group) >= BOX_PERIOD:
        box_data = group.iloc[-BOX_PERIOD:-10]
        box_high = box_data["high"].max()
        box_low = box_data["low"].min()
        box_width = (box_high - box_low) / box_low * 100 if box_low > 0 else 999
        breakout_ratio = (close_today - box_high) / box_high * 100 if box_high > 0 else -999
        high_250d = group["high"].tail(250).max()
        low_250d = group["low"].tail(250).min()
        dist_from_high = (close_today - high_250d) / high_250d * 100 if high_250d > 0 else 0
        dist_from_low = (close_today - low_250d) / low_250d * 100 if low_250d > 0 else 0
        day_high = float(latest["high"])
        day_low = float(latest["low"])
        close_str = close_strength_ratio(day_high, day_low, close_today)
        if (
            box_width <= BOX_WIDTH_MAX
            and breakout_ratio >= 0
            and dist_from_high <= DIST_FROM_250D_HIGH_MAX
            and dist_from_low <= DIST_FROM_250D_LOW_MAX
            and ma5 > ma10 > ma20
            and pct_chg_today > 0
            and close_today > float(latest["open"])
            and close_str >= BREAKOUT_CLOSE_STRENGTH_MIN
        ):
            is_breakout = True

    is_three_up = False
    if len(group) >= 10:
        recent_3 = group.tail(3)
        avg_amount_5 = group["amount"].iloc[-8:-3].mean()
        if avg_amount_5 <= 0:
            avg_amount_5 = 1.0
        cond1 = (recent_3["pct_chg"] >= THREE_UP_MIN_CHG).all()
        cond2 = (recent_3["close"] > recent_3["open"]).all()
        cond3 = (recent_3["amount"] > avg_amount_5 * THREE_UP_VOL_RATIO).any()
        cond4 = (close_today - group["close"].iloc[-4]) / group["close"].iloc[-4] * 100 <= THREE_UP_TOTAL_CHG_MAX
        high_250d = group["high"].tail(250).max()
        is_low = (close_today - high_250d) / high_250d * 100 < -30 if high_250d > 0 else False
        if cond1 and cond2 and cond3 and cond4 and is_low:
            is_three_up = True

    is_pullback = False
    if len(group) >= 30:
        prev_20d_chg = (group["close"].iloc[-5] - group["close"].iloc[-25]) / group["close"].iloc[-25] * 100
        dist_to_ma20 = abs(close_today - ma20) / ma20 * 100 if ma20 > 0 else 999
        avg_amount_5 = group["amount"].iloc[-10:-5].mean()
        if avg_amount_5 <= 0:
            avg_amount_5 = 1.0
        vol_ratio = amount_today / avg_amount_5
        if (
            prev_20d_chg >= PULLBACK_PREV_STRENGTH
            and dist_to_ma20 <= PULLBACK_MA20_DIST
            and vol_ratio <= PULLBACK_VOL_DECREASE
            and close_today >= ma20
            and close_today >= ma5
            and close_today > float(latest["open"])
            and pct_chg_today > 0
        ):
            is_pullback = True

    is_ambush = False
    if len(group) >= max(BOX_PERIOD, 40):
        box_data2 = group.iloc[-BOX_PERIOD:-5]
        box_high2 = box_data2["high"].max()
        box_low2 = box_data2["low"].min()
        box_width2 = (box_high2 - box_low2) / box_low2 * 100 if box_low2 > 0 else 999
        near_box_top = (close_today - box_high2) / box_high2 * 100 if box_high2 > 0 else -999
        ma20_series = group["close"].rolling(20).mean()
        ma20_slope_5d = (
            (ma20_series.iloc[-1] - ma20_series.iloc[-6]) / ma20_series.iloc[-6] * 100
            if len(group) >= 26 and ma20_series.iloc[-6] > 0
            else -999
        )
        avg_amount_5b = group["amount"].iloc[-10:-5].mean()
        if avg_amount_5b <= 0:
            avg_amount_5b = 1.0
        vol_ratio_b = amount_today / avg_amount_5b
        ambush_ok = (
            AMBUSH_NEAR_BOX_TOP_MIN <= near_box_top <= AMBUSH_NEAR_BOX_TOP_MAX
            and box_width2 <= AMBUSH_BOX_WIDTH_MAX
            and ma20_slope_5d >= AMBUSH_MA20_SLOPE_MIN
            and AMBUSH_VOL_RATIO_MIN <= vol_ratio_b <= AMBUSH_VOL_RATIO_MAX
            and close_today >= ma20
        )
        if ambush_ok and pct_chg_today >= 0 and close_today > float(latest["open"]):
            is_ambush = True
        elif ambush_ok and AMBUSH_SOFT_DIP_PCT <= pct_chg_today < 0:
            is_ambush = True

    if not (is_breakout or is_three_up or is_pullback or is_ambush):
        return None

    tags = []
    if is_breakout:
        tags.append("大底突破")
    if is_three_up:
        tags.append("三连阳")
    if is_pullback:
        tags.append("空中加油")
    if is_ambush:
        tags.append("早埋伏")

    signal_score = 0
    if is_breakout:
        signal_score += 18
    if is_three_up:
        signal_score += 14
    if is_pullback:
        signal_score += 13
    if is_ambush:
        signal_score += 12

    trend_score = 0
    if ma5 > ma10:
        trend_score += 8
    if ma10 > ma20:
        trend_score += 8
    if close_today >= ma20:
        trend_score += 9

    risk_penalty = 0
    momentum_score = 0
    if -2 <= pct_chg_today <= CHASE_PCT_MAX:
        momentum_score += 8
    elif CHASE_PCT_MAX < pct_chg_today <= 6:
        momentum_score += 2
    elif pct_chg_today > 6:
        risk_penalty -= 4

    if len(group) >= 25:
        prev_20d_chg_for_score = (group["close"].iloc[-1] - group["close"].iloc[-21]) / group["close"].iloc[-21] * 100
        if 5 <= prev_20d_chg_for_score <= 30:
            momentum_score += 12
        elif prev_20d_chg_for_score > 30:
            momentum_score += 6

    liquidity_score = liquidity_score_from_wan(amount_wan)

    if abs(pct_chg_today) > 8:
        risk_penalty -= 6
    if len(group) >= 10 and "pct_chg" in group.columns:
        recent_vol = group["pct_chg"].tail(10).std()
        if recent_vol > 5:
            risk_penalty -= 5
    if is_ambush and AMBUSH_SOFT_DIP_PCT <= pct_chg_today < 0:
        risk_penalty -= 2
    if len(group) >= 4:
        chg_3d = (close_today / float(group["close"].iloc[-4]) - 1) * 100
        if chg_3d > 12:
            risk_penalty -= 4

    total_score = max(
        0,
        min(
            100,
            round(signal_score + trend_score + momentum_score + liquidity_score + risk_penalty + market_score_adj, 1),
        ),
    )

    is_ambush_only = is_ambush and not (is_breakout or is_three_up or is_pullback)
    action = assign_action(total_score, is_ambush_only=is_ambush_only, regime=market_regime)
    action = cap_action_for_redlines(action, pct_chg_today, 0.0)
    if pct_chg_today > CHASE_PCT_MAX and action in BUY_ACTIONS:
        action = "继续观察"
    if pct_chg_today < 0 and action not in BUY_ACTIONS:
        action = "谨慎回避"
    if action == "谨慎回避":
        return None
    if action not in BUY_ACTIONS:
        return None

    return {
        "score": total_score,
        "tags": tags,
        "action": action,
        "close": close_today,
        "pct_chg": pct_chg_today,
        "weight_hint": ACTION_WEIGHT.get(action, 0.08),
    }


def pick_top(candidates, top_n=5):
    """candidates: list of dict with symbol, score, action, weight_hint"""
    ranked = sorted(candidates, key=lambda x: (-x["score"], -len(x.get("tags") or [])))
    picked = []
    for item in ranked:
        if len(picked) >= top_n:
            break
        picked.append(item)
    return picked


def normalize_weights(picked, cash_reserve):
    if not picked:
        return {}
    raw = {p["symbol"]: p["weight_hint"] for p in picked}
    s = sum(raw.values())
    if s <= 0:
        per = (1.0 - cash_reserve) / len(picked)
        return {p["symbol"]: per for p in picked}
    scale = (1.0 - cash_reserve) / s
    return {sym: w * scale for sym, w in raw.items()}
