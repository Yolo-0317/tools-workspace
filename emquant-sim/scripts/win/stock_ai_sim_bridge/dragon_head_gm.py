# coding=utf-8
"""游资轨龙头战法 v2：增强试探版（准回封 + 分档仓位 + 止盈破板）。"""
from __future__ import print_function, absolute_import, unicode_literals

import json
import os
from datetime import time

# 与执行卡 / 日检卡一致
MAX_CHASE_PCT = 5.0
MIN_PREMIUM_PCT = 1.0
MAX_EXPLODE_PCT = 40.0
STOP_LOSS_PCT = -5.0
MIN_CHECKLIST_PASS = 5
MAX_DRAGON_POSITIONS = 3
MIN_BOARD_HEIGHT = 2
MIN_SHARES = 100

# v2：准回封 / 结构买点
NEAR_LIMIT_PCT = 9.0
PULLBACK_FROM_HIGH_PCT = 2.0
RESEAL_TOLERANCE_PCT = 1.5
PULLBACK_ENTRY_MIN_PCT = 1.5
HIGH_ACCEL_BOARD = 3
HIGH_ACCEL_DAILY_PCT = 7.0
ONE_WORD_LIMIT_PCT = 9.8

# v2：止盈
TAKE_PROFIT_HALF_PCT = 7.0
TAKE_PROFIT_FULL_PCT = 10.0
BROKEN_BOARD_EXIT_PCT = 5.0

# v2：按龙位分配游资轨预算（占 position_cap_pct 的比例）
RANK_WEIGHTS = {1: 0.40, 2: 0.25, 3: 0.15}
PHASE_MAX_RANK = {"启动": 1, "发酵": 2, "高潮": 3}
PHASE_MAX_POSITIONS = {"启动": 1, "发酵": 2, "高潮": 3}

PHASE_NO_OPEN = frozenset(["冰点", "退潮"])
PHASE_CAN_OPEN = frozenset(["启动", "发酵", "高潮"])
PHASE_REDUCE = frozenset(["分歧"])

# 09:30–09:45 不盲目接力
OPEN_CHAOS_END = time(9, 45)


def ts_code_to_gm(code):
    c = str(code).zfill(6)
    if c.startswith(("5", "6", "9")):
        return "SHSE.%s" % c
    return "SZSE.%s" % c


def gm_to_code(symbol):
    return symbol.split(".")[-1] if "." in symbol else symbol


def load_dragons(path):
    if not path or not os.path.isfile(path):
        return {
            "trade_date": None,
            "checklist_slot": None,
            "header": {},
            "dragon_items": [],
        }
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "trade_date": data.get("trade_date"),
        "checklist_slot": data.get("checklist_slot"),
        "header": data.get("header") or {},
        "dragon_items": data.get("dragon_items") or [],
    }


def _float_val(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool_val(value):
    if value in (1, True, "1", "true", "True"):
        return True
    if value in (0, False, "0", "false", "False"):
        return False
    return None


def phase_allows_new_open(header):
    """是否允许游资轨新开（阶段 + 溢价 + 炸板率 + allow_new_open）。"""
    phase = str(header.get("phase") or "").strip()
    if phase in PHASE_NO_OPEN:
        return False, "phase=%s" % phase

    premium = _float_val(header.get("limit_up_premium_pct"))
    if premium is not None and premium < MIN_PREMIUM_PCT:
        return False, "premium=%.2f" % premium

    explode = _float_val(header.get("explode_rate_pct"))
    if explode is not None and explode >= MAX_EXPLODE_PCT:
        return False, "explode=%.2f" % explode

    allow = _bool_val(header.get("allow_new_open"))
    if allow is False:
        return False, "allow_new_open=0"

    if phase in PHASE_CAN_OPEN:
        return True, "phase=%s" % phase

    if phase in PHASE_REDUCE:
        return False, "phase=分歧(仅留核心龙)"

    return False, "phase=%s" % (phase or "unknown")


def position_cap_pct(header):
    cap = _float_val(header.get("position_cap_pct"))
    if cap is None:
        phase = str(header.get("phase") or "")
        defaults = {
            "冰点": 2.0,
            "启动": 40.0,
            "发酵": 60.0,
            "高潮": 75.0,
            "分歧": 40.0,
            "退潮": 0.0,
        }
        return defaults.get(phase, 0.0)
    return cap


def max_rank_for_phase(header):
    phase = str(header.get("phase") or "")
    return PHASE_MAX_RANK.get(phase, 0)


def max_positions_for_phase(header):
    phase = str(header.get("phase") or "")
    return PHASE_MAX_POSITIONS.get(phase, 0)


def rank_allowed(dragon, header):
    rank = int(dragon.get("rank_no") or 99)
    cap_rank = max_rank_for_phase(header)
    if cap_rank <= 0:
        return False, "phase_no_rank"
    if rank > cap_rank:
        return False, "rank>%d" % cap_rank
    return True, "rank_ok"


def in_buy_time_window(dt):
    """09:30–09:45 禁止新开（开盘盲目接力）。"""
    if dt is None:
        return True, "time_ok"
    t = dt.time() if hasattr(dt, "time") else dt
    if time(9, 30) <= t < OPEN_CHAOS_END:
        return False, "open_chaos"
    return True, "time_ok"


def ban_high_acceleration(dragon, daily_pct):
    board = int(dragon.get("board_height") or 0)
    if board >= HIGH_ACCEL_BOARD and daily_pct >= HIGH_ACCEL_DAILY_PCT:
        return True, "high_accel>=%d板+%.0f%%" % (HIGH_ACCEL_BOARD, HIGH_ACCEL_DAILY_PCT)
    return False, ""


def new_intraday_state(day_key):
    return {
        "day": day_key,
        "high_pct": -100.0,
        "morning_low_pct": 100.0,
        "touched_limit": False,
        "pullback_seen": False,
    }


def update_intraday_state(state, daily_pct, dt):
    """用 60s bar 近似更新日内结构（触板 / 回落 / 早盘低点）。"""
    if daily_pct > state.get("high_pct", -100.0):
        state["high_pct"] = daily_pct

    if dt is not None:
        t = dt.time() if hasattr(dt, "time") else None
        if t and t <= time(10, 0) and daily_pct < state.get("morning_low_pct", 100.0):
            state["morning_low_pct"] = daily_pct

    if state["high_pct"] >= NEAR_LIMIT_PCT:
        state["touched_limit"] = True

    if state["touched_limit"] and state["high_pct"] - daily_pct >= PULLBACK_FROM_HIGH_PCT:
        state["pullback_seen"] = True

    return state


def _base_entry_gates(dragon, price, daily_pct, header, dt):
    if price <= 0:
        return False, "bad_price"

    board = int(dragon.get("board_height") or 0)
    if board < MIN_BOARD_HEIGHT:
        return False, "board<%d" % MIN_BOARD_HEIGHT

    passed = int(dragon.get("checklist_pass") or 0)
    if passed < MIN_CHECKLIST_PASS:
        return False, "pass<%d" % MIN_CHECKLIST_PASS

    if daily_pct < -3.0:
        return False, "drop>3"

    ok, reason = phase_allows_new_open(header)
    if not ok:
        return False, reason

    ok, reason = rank_allowed(dragon, header)
    if not ok:
        return False, reason

    ok, reason = in_buy_time_window(dt)
    if not ok:
        return False, reason

    return True, "gates_ok"


def _entry_reseal(daily_pct, state):
    if not state.get("touched_limit") or not state.get("pullback_seen"):
        return False
    if daily_pct >= state["high_pct"] - RESEAL_TOLERANCE_PCT:
        return True
    return False


def _entry_pullback(daily_pct, state):
    if state.get("touched_limit"):
        return False
    high = state.get("high_pct", daily_pct)
    if high - daily_pct < PULLBACK_ENTRY_MIN_PCT:
        return False
    if not (2.0 <= daily_pct <= 7.0):
        return False
    if daily_pct >= high - 0.8:
        return True
    return False


def _entry_weak2strong(daily_pct, state, dt):
    if dt is None:
        return False
    t = dt.time() if hasattr(dt, "time") else None
    if not t or t < time(10, 0):
        return False
    morning_low = state.get("morning_low_pct", 0.0)
    if morning_low >= 0:
        return False
    if daily_pct >= 1.0:
        return True
    return False


def entry_signal(dragon, price, daily_pct, header, dt=None, intraday_state=None):
    """v2 结构买点：准回封 > 分时回踩 > 弱转强（均须过 gate）。"""
    ok, reason = _base_entry_gates(dragon, price, daily_pct, header, dt)
    if not ok:
        return False, reason

    state = intraday_state or {}
    if state.get("touched_limit") and daily_pct >= ONE_WORD_LIMIT_PCT and not state.get("pullback_seen"):
        return False, "one_word"

    if _entry_reseal(daily_pct, state):
        return True, "re-seal"

    banned, reason = ban_high_acceleration(dragon, daily_pct)
    if banned:
        return False, reason

    if _entry_pullback(daily_pct, state):
        return True, "pullback"

    if _entry_weak2strong(daily_pct, state, dt):
        return True, "weak2strong"

    return False, "no_structure"


def exit_signal(header, daily_pct, held_days=0, intraday_state=None, half_taken=False):
    """v2 出场：阶段清仓 / 止损 / 破板 / 止盈 / 时间止损。"""
    phase = str(header.get("phase") or "")
    if phase in PHASE_NO_OPEN:
        return "sell_all", "phase=%s清仓" % phase

    state = intraday_state or {}
    if state.get("touched_limit") and daily_pct < BROKEN_BOARD_EXIT_PCT:
        return "sell_all", "broken_board"

    if daily_pct <= STOP_LOSS_PCT:
        return "sell_all", "stop_loss"

    if daily_pct >= TAKE_PROFIT_FULL_PCT:
        return "sell_all", "take_profit_full"

    if daily_pct >= TAKE_PROFIT_HALF_PCT and not half_taken:
        return "sell_half", "take_profit_half"

    if held_days >= 5:
        return "sell_all", "time_stop_5d"

    return None, ""


def max_shares_for_dragon(header, cash_dict, nav_fn, dragon, price):
    """按龙位权重 × NAV × cap 计算整手股数。"""
    cap_pct = position_cap_pct(header)
    if cap_pct <= 0 or price <= 0:
        return 0

    nav = nav_fn(cash_dict)
    if nav <= 0:
        return MIN_SHARES

    rank = int(dragon.get("rank_no") or 99)
    weight = RANK_WEIGHTS.get(rank, 0.10)
    budget = nav * (cap_pct / 100.0) * weight
    shares = int(budget / price) // 100 * 100
    if shares < MIN_SHARES:
        return 0
    return shares


def count_dragon_positions(pos_list, dragon_items):
    codes = {str(d.get("ts_code") or "").zfill(6) for d in dragon_items}
    n = 0
    for p in pos_list or []:
        sym = p.get("symbol") if isinstance(p, dict) else getattr(p, "symbol", None)
        if gm_to_code(sym) in codes:
            vol = p.get("volume") if isinstance(p, dict) else getattr(p, "volume", 0)
            if int(vol or 0) >= MIN_SHARES:
                n += 1
    return n


def dragon_symbols(dragon_items):
    out = []
    seen = set()
    for item in dragon_items:
        code = str(item.get("ts_code") or "").zfill(6)
        if len(code) != 6 or code in seen:
            continue
        seen.add(code)
        out.append(ts_code_to_gm(code))
    return out


def find_dragon(dragon_items, symbol):
    code = gm_to_code(symbol)
    for item in dragon_items:
        if str(item.get("ts_code") or "").zfill(6) == code:
            return item
    return None
