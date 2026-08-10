"""综合选股单股评估（供日线选股与回测复用）。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from board_filters import (
    BoardFilterParams,
    board_action_threshold_overrides,
    code6,
    detect_board,
    get_board_params,
    liquidity_score_from_wan,
    passes_base_filter,
    passes_crash_filter,
    should_block_weak_market,
)
from stock_selection_combined import (
    AMBUSH_MA20_SLOPE_MIN,
    AMBUSH_NEAR_BOX_TOP_MAX,
    AMBUSH_NEAR_BOX_TOP_MIN,
    AMBUSH_SOFT_DIP_PCT,
    AMBUSH_VOL_RATIO_MAX,
    AMBUSH_VOL_RATIO_MIN,
    AMBUSH_BOX_WIDTH_MAX,
    BOX_PERIOD,
    BOX_WIDTH_MAX,
    BREAKOUT_CLOSE_STRENGTH_MIN,
    BUY_ACTIONS,
    DIST_FROM_250D_HIGH_MAX,
    DIST_FROM_250D_LOW_MAX,
    PULLBACK_MA20_DIST,
    PULLBACK_VOL_DECREASE,
    THREE_UP_MIN_CHG,
    THREE_UP_VOL_RATIO,
    amount_qian_to_wan,
    assign_action,
    close_strength_ratio,
    _cap_action_for_redlines,
    _position_suggestion,
    _resolve_industry,
    _sector_matches,
)


def _cap_action_for_board(
    action: str,
    pct_chg: float,
    account_position_pct: float,
    board: BoardFilterParams,
) -> str:
    return _cap_action_for_redlines(
        action,
        pct_chg,
        account_position_pct,
        chase_pct_max=board.chase_pct_max,
    )


def evaluate_combined_candidate(
    group: pd.DataFrame,
    ts_code: str,
    *,
    market_score_adj: int = 0,
    hot_sectors: list[str] | None = None,
    market_regime: str = "neutral",
    holdings_codes: set[str] | None = None,
    account_position_pct: float = 0.0,
    industry_map: dict[str, str] | None = None,
    advisor_phase: int = 0,
    legacy_unified_filter: bool = False,
    skip_advisor: bool = False,
    skip_account_caps: bool = False,
    board_market_regime: str | None = None,
    skip_weak_market_block: bool = False,
) -> dict[str, Any] | None:
    """
    对单只股票截至 group 最后一根 K 线做 combined 信号检测与评分。
    legacy_unified_filter=True：全市场统一主板 5–20 元（回测对照组）。
    """
    hot_sectors = hot_sectors or []
    holdings_codes = holdings_codes or set()
    industry_map = industry_map or {}

    group = group.sort_values("trade_date")
    if len(group) < 60:
        return None

    code_str = code6(ts_code)
    board = get_board_params(ts_code, legacy_unified=legacy_unified_filter)
    latest = group.iloc[-1]
    close_today = float(latest["close"])
    amount_today = float(latest["amount"])
    pct_chg_today = float(latest["pct_chg"])

    if not passes_crash_filter(ts_code, pct_chg_today, legacy_unified=legacy_unified_filter):
        return None
    if not passes_base_filter(
        ts_code, close_today, amount_today, legacy_unified=legacy_unified_filter
    ):
        return None
    if pct_chg_today > board.signal_day_pct_max:
        return None

    if (
        not skip_weak_market_block
        and code_str not in holdings_codes
        and should_block_weak_market(
            board,
            market_regime=market_regime,
            board_market_regime=board_market_regime,
        )
    ):
        return None

    amount_wan = amount_qian_to_wan(amount_today)

    ma5 = float(group["close"].tail(5).mean())
    ma10 = float(group["close"].tail(10).mean())
    ma20 = float(group["close"].tail(20).mean())

    is_breakout = False
    if len(group) >= BOX_PERIOD:
        box_data = group.iloc[-BOX_PERIOD:-10]
        box_high = float(box_data["high"].max())
        box_low = float(box_data["low"].min())
        box_width = (box_high - box_low) / box_low * 100 if box_low > 0 else 999
        breakout_ratio = (close_today - box_high) / box_high * 100 if box_high > 0 else -999

        high_250d = float(group["high"].tail(250).max())
        low_250d = float(group["low"].tail(250).min())
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
    if board.enable_three_up and len(group) >= 10:
        recent_3 = group.tail(3)
        avg_amount_5 = float(group["amount"].iloc[-8:-3].mean())
        cond1 = (recent_3["pct_chg"] >= THREE_UP_MIN_CHG).all()
        cond2 = (recent_3["close"] > recent_3["open"]).all()
        cond3 = (recent_3["amount"] > avg_amount_5 * THREE_UP_VOL_RATIO).any()
        cond4 = (
            (close_today - float(group["close"].iloc[-4]))
            / float(group["close"].iloc[-4])
            * 100
            <= board.three_up_total_chg_max
        )
        high_250d = float(group["high"].tail(250).max())
        is_low = (close_today - high_250d) / high_250d * 100 < -30 if high_250d > 0 else False
        if cond1 and cond2 and cond3 and cond4 and is_low:
            is_three_up = True

    is_pullback = False
    if len(group) >= 30:
        prev_20d_chg = (
            (float(group["close"].iloc[-5]) - float(group["close"].iloc[-25]))
            / float(group["close"].iloc[-25])
            * 100
        )
        dist_to_ma20 = abs(close_today - ma20) / ma20 * 100 if ma20 > 0 else 999
        avg_amount_5 = float(group["amount"].iloc[-10:-5].mean())
        vol_ratio = amount_today / avg_amount_5 if avg_amount_5 > 0 else 0
        if (
            prev_20d_chg >= board.pullback_prev_strength
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
        box_high2 = float(box_data2["high"].max())
        box_low2 = float(box_data2["low"].min())
        box_width2 = (box_high2 - box_low2) / box_low2 * 100 if box_low2 > 0 else 999
        near_box_top = (close_today - box_high2) / box_high2 * 100 if box_high2 > 0 else -999
        ma20_series = group["close"].rolling(20).mean()
        ma20_slope_5d = -999.0
        if len(group) >= 26 and float(ma20_series.iloc[-6]) > 0:
            ma20_slope_5d = (
                (float(ma20_series.iloc[-1]) - float(ma20_series.iloc[-6]))
                / float(ma20_series.iloc[-6])
                * 100
            )
        avg_amount_5b = float(group["amount"].iloc[-10:-5].mean())
        vol_ratio_b = amount_today / avg_amount_5b if avg_amount_5b > 0 else 0
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

    is_surge = False
    if not (is_breakout or is_three_up or is_pullback or is_ambush or is_surge):
        return None

    tags: list[str] = []
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
    chase = board.chase_pct_max
    if -2 <= pct_chg_today <= chase:
        momentum_score += 8
    elif chase < pct_chg_today <= chase + 2:
        momentum_score += 2
    elif pct_chg_today > chase + 2:
        risk_penalty -= 4

    if len(group) >= 25:
        prev_20d_chg_for_score = (
            (float(group["close"].iloc[-1]) - float(group["close"].iloc[-21]))
            / float(group["close"].iloc[-21])
            * 100
        )
        if 5 <= prev_20d_chg_for_score <= 30:
            momentum_score += 12
        elif prev_20d_chg_for_score > 30:
            momentum_score += 6

    liquidity_score = liquidity_score_from_wan(amount_wan, board)

    if abs(pct_chg_today) > board.momentum_risk_pct:
        risk_penalty -= 6
    if len(group) >= 10:
        recent_vol = float(group["pct_chg"].tail(10).std())
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
            round(
                signal_score
                + trend_score
                + momentum_score
                + liquidity_score
                + risk_penalty
                + market_score_adj,
                1,
            ),
        ),
    )

    sector_score_adj = 0
    industry = _resolve_industry(str(ts_code), industry_map)
    if _sector_matches(industry, hot_sectors):
        sector_score_adj = 5
        total_score = min(100, total_score + sector_score_adj)

    resonance_score = 0
    if market_score_adj > 0 and sector_score_adj > 0 and (
        len(tags) > 1 or signal_score >= 18
    ):
        resonance_score = 10
        total_score = min(100, total_score + resonance_score)
        tags.append("三力合一")

    if is_pullback and board.pullback_score_bonus > 0:
        total_score = min(100.0, total_score + board.pullback_score_bonus)

    if board.max_entry_score is not None and total_score > board.max_entry_score:
        return None

    is_ambush_only = is_ambush and not (is_breakout or is_three_up or is_pullback or is_surge)
    action_regime = board_market_regime or market_regime
    threshold_overrides = board_action_threshold_overrides(
        board, market_regime=action_regime
    )
    action = assign_action(
        total_score,
        is_ambush_only=is_ambush_only,
        regime=action_regime,
        threshold_overrides=threshold_overrides,
    )

    if code_str in holdings_codes:
        action = "持有" if action in BUY_ACTIONS else action
    elif not skip_account_caps:
        action = _cap_action_for_board(
            action, pct_chg_today, account_position_pct, board
        )
        if pct_chg_today > board.chase_pct_max and action in BUY_ACTIONS:
            action = "继续观察"
        if pct_chg_today < 0 and action not in BUY_ACTIONS:
            action = "谨慎回避"

    if code_str not in holdings_codes and action == "谨慎回避":
        return None

    if not skip_advisor:
        try:
            from stock_ai.advisor_selection import (
                advisor_industry_score_bonus,
                apply_advisor_to_results_row,
            )

            total_score = min(
                100.0,
                total_score + advisor_industry_score_bonus(industry, phase=advisor_phase),
            )
        except ImportError:
            pass

    _, buy_shares, buy_amount_yuan = _position_suggestion(action, close_today)

    row: dict[str, Any] = {
        "代码": code_str,
        "收盘价": close_today,
        "涨幅%": pct_chg_today,
        "成交额(万)": round(amount_wan, 2),
        "策略标签": ",".join(tags),
        "标签数": len(tags),
        "总分": total_score,
        "信号分": signal_score,
        "趋势分": trend_score,
        "动量分": momentum_score,
        "流动性分": round(liquidity_score, 1),
        "风险调整": risk_penalty,
        "大盘调整": market_score_adj,
        "板块调整": sector_score_adj,
        "共振加分": resonance_score,
        "大盘环境": action_regime,
        "所属行业": industry,
        "建议动作": action,
        "建议买入(股)": buy_shares,
        "预计金额(元)": buy_amount_yuan,
        "超大单净流入(万)": 0,
        "超大单占比%": 0,
        "板块类型": (
            "科创板"
            if code_str.startswith(("688", "689"))
            else ("创业板" if code_str.startswith(("300", "301")) else "主板")
        ),
    }

    if not skip_advisor:
        try:
            from stock_ai.advisor_selection import apply_advisor_to_results_row

            apply_advisor_to_results_row(
                row, phase=advisor_phase, account_position_pct=account_position_pct
            )
            if row.get("建议动作") == "禁止":
                return None
            action = str(row["建议动作"])
            _, buy_shares, buy_amount_yuan = _position_suggestion(action, close_today)
            row["建议买入(股)"] = buy_shares
            row["预计金额(元)"] = buy_amount_yuan
        except ImportError:
            pass

    return row
