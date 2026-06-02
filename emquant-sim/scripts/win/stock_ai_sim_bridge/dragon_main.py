# coding=utf-8
"""
游资轨龙头战法仿真（读 dragons.json）

数据源：Mac 导出 MySQL emotion_cycle_dragon_watch → deploy dragons.json
纪律：情绪周期日检卡.md（阶段 gate + 龙头观察池 Top3）

终端：仿真 → 关联仿真户 → 运行本策略（filename=dragon_main.py）
"""
from __future__ import print_function, absolute_import, unicode_literals

import os
import sys
from datetime import datetime, time

from gm.api import *

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import dragon_head_gm as dhg
import holdings_rules_gm as hrg

DRAGONS_FILE = os.environ.get("DRAGONS_FILE") or os.path.join(_DIR, "dragons.json")
BAR_FREQ = "60s"
BAR_COUNT = 10
RELOAD_INTERVAL_SEC = 300  # 与 Mac intraday 5min 对齐
SESSION_TIMES = ("09:35:00", "10:30:00", "13:05:00", "14:50:00")


def _build_reload_times():
    """盘中每 5 分钟 schedule reload（不依赖 on_bar 是否有 tick）。"""
    times = []
    for hour in range(9, 12):
        for minute in range(0, 60, 5):
            if hour == 9 and minute < 31:
                continue
            times.append("%02d:%02d:00" % (hour, minute))
    for hour in range(13, 16):
        for minute in range(0, 60, 5):
            times.append("%02d:%02d:00" % (hour, minute))
    return tuple(times)


RELOAD_TIMES = _build_reload_times()


def _normalize_bars(bars):
    if bars is None:
        return []
    if isinstance(bars, (list, tuple)):
        return [b for b in bars if b is not None]
    return [bars]


def _bar_get(bar, key, default=None):
    try:
        return bar[key]
    except (KeyError, TypeError):
        return getattr(bar, key, default)


def _now_dt(context):
    return context.now if hasattr(context, "now") else datetime.now()


def is_trading_session(dt):
    if dt.weekday() >= 5:
        return False
    t = dt.time()
    return (time(9, 30) <= t <= time(11, 30)) or (time(13, 0) <= t <= time(15, 0))


def _nav(cash_dict):
    if isinstance(cash_dict, dict):
        return float(cash_dict.get("nav") or cash_dict.get("total_value") or 0)
    return 0.0


def _position_ratio(cash_dict):
    return hrg.position_ratio_pct(cash_dict)


def _daily_pct(symbol, now_str):
    try:
        bars = history_n(
            symbol=symbol,
            frequency="1d",
            count=2,
            end_time=now_str,
            fields="close",
            skip_suspended=True,
            fill_missing="Last",
            adjust=ADJUST_PREV,
            df=False,
        )
        if not bars or len(bars) < 2:
            return 0.0
        a, b = float(bars[0]["close"]), float(bars[1]["close"])
        return (b / a - 1.0) * 100.0 if a > 0 else 0.0
    except Exception:
        return 0.0


def _order_apis():
    return {
        "sell_all": lambda sym, px: order_target_percent(
            symbol=sym,
            percent=0,
            order_type=OrderType_Limit,
            position_side=PositionSide_Long,
            price=px,
        ),
        "sell_shares": lambda sym, shares, px: order_volume(
            symbol=sym,
            volume=int(shares),
            side=OrderSide_Sell,
            order_type=OrderType_Limit,
            position_effect=PositionEffect_Close,
            price=px,
        ),
        "buy_shares": lambda sym, shares, px: order_volume(
            symbol=sym,
            volume=int(shares),
            side=OrderSide_Buy,
            order_type=OrderType_Limit,
            position_effect=PositionEffect_Open,
            price=px,
        ),
    }


def _dragons_mtime():
    try:
        return os.path.getmtime(DRAGONS_FILE)
    except OSError:
        return 0.0


def _reload_dragons(context):
    prev_phase = (getattr(context, "emotion_header", None) or {}).get("phase")
    prev_codes = {str(x.get("ts_code", "")).zfill(6) for x in (getattr(context, "dragon_items", None) or [])}
    file_mtime = _dragons_mtime()
    cfg = dhg.load_dragons(DRAGONS_FILE)
    context.emotion_header = cfg.get("header") or {}
    context.dragon_items = cfg.get("dragon_items") or []
    context.pool_trade_date = cfg.get("trade_date")
    context.pool_slot = cfg.get("checklist_slot")
    context.dragons_file_mtime = file_mtime

    syms = dhg.dragon_symbols(context.dragon_items)
    new_codes = {str(x.get("ts_code", "")).zfill(6) for x in context.dragon_items}
    for sym in syms:
        if sym not in context.subscribed:
            subscribe(symbols=sym, frequency=BAR_FREQ, count=BAR_COUNT)
            context.subscribed.append(sym)

    phase = context.emotion_header.get("phase")
    cap = dhg.position_cap_pct(context.emotion_header)
    ok, why = dhg.phase_allows_new_open(context.emotion_header)
    changed = prev_phase != phase or prev_codes != new_codes
    tag = " (updated)" if changed else ""
    mtime_str = datetime.fromtimestamp(file_mtime).strftime("%H:%M:%S") if file_mtime else "missing"
    print(
        "[dragon] reload%s date=%s slot=%s phase=%s cap=%.0f%% open=%s dragons=%d (%s) file=%s mtime=%s"
        % (
            tag,
            context.pool_trade_date,
            context.pool_slot,
            phase,
            cap,
            ok,
            len(context.dragon_items),
            why,
            DRAGONS_FILE,
            mtime_str,
        )
    )
    if changed:
        for item in context.dragon_items:
            print(
                "  #%s %s %s %s板 pass=%s"
                % (
                    item.get("rank_no"),
                    item.get("ts_code"),
                    item.get("name"),
                    item.get("board_height"),
                    item.get("checklist_pass"),
                )
            )


def _maybe_reload_dragons(context, dt):
    if not is_trading_session(dt):
        return
    last = float(getattr(context, "last_dragon_reload_ts", 0.0) or 0.0)
    last_mtime = float(getattr(context, "dragons_file_mtime", 0.0) or 0.0)
    ts = dt.timestamp()
    file_mtime = _dragons_mtime()
    if file_mtime > last_mtime or ts - last >= RELOAD_INTERVAL_SEC:
        _reload_dragons(context)
        context.last_dragon_reload_ts = ts


def init(context):
    context.subscribed = []
    context.fired_ids = set()
    context.fired_day = None
    context.entry_day = {}
    context.intraday_state = {}
    context.half_profit_taken = set()
    context.last_dragon_reload_ts = 0.0
    context.dragons_file_mtime = 0.0

    _reload_dragons(context)
    if not context.dragon_items:
        print("[dragon] warn: dragons.json 为空，请先 Mac 导出并 deploy")

    print("[dragon] mode=v2 enhanced-probe (re-seal / rank-weight / take-profit)")

    for t in RELOAD_TIMES:
        schedule(schedule_func=on_reload, date_rule="1d", time_rule=t)
    for t in SESSION_TIMES:
        schedule(schedule_func=on_session, date_rule="1d", time_rule=t)

    _log_account("init")


def _reset_daily_state(context):
    day = _now_dt(context).strftime("%Y-%m-%d")
    if context.fired_day == day:
        return
    context.fired_day = day
    context.fired_ids = set()
    context.intraday_state = {}
    context.half_profit_taken = set()


def _intraday_state(context, sym, day_key):
    if not hasattr(context, "intraday_state") or context.intraday_state is None:
        context.intraday_state = {}
    st = context.intraday_state.get(sym)
    if not st or st.get("day") != day_key:
        st = dhg.new_intraday_state(day_key)
        context.intraday_state[sym] = st
    return st


def on_reload(context):
    dt = _now_dt(context)
    _reload_dragons(context)
    context.last_dragon_reload_ts = dt.timestamp()


def on_session(context):
    dt = _now_dt(context)
    if not is_trading_session(dt):
        return
    _reload_dragons(context)
    context.last_dragon_reload_ts = dt.timestamp()
    header = context.emotion_header or {}
    phase = str(header.get("phase") or "")
    if phase not in dhg.PHASE_NO_OPEN:
        return

    pos_list = get_position() or []
    apis = _order_apis()
    for sym in dhg.dragon_symbols(context.dragon_items):
        if hrg.held_volume(sym, pos_list) < hrg.MIN_HELD_SHARES:
            continue
        try:
            px = current(symbols=sym)[0]["price"]
        except Exception:
            continue
        if not px or px <= 0:
            continue
        print("[dragon] SESSION_EXIT phase=%s sell_all %s" % (phase, sym))
        apis["sell_all"](sym, px)


def _on_bar_one(context, bar, dt):
    sym = _bar_get(bar, "symbol")
    if not sym:
        return
    price = float(_bar_get(bar, "close") or 0)
    if price <= 0:
        return

    dragon = dhg.find_dragon(context.dragon_items, sym)
    if not dragon:
        return

    now_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    daily_pct = _daily_pct(sym, now_str)
    header = context.emotion_header or {}
    cash = get_cash()
    pos_list = get_position() or []
    held = hrg.held_volume(sym, pos_list)
    code = hrg.gm_to_code(sym)
    day_key = dt.strftime("%Y-%m-%d")
    intraday = _intraday_state(context, sym, day_key)
    dhg.update_intraday_state(intraday, daily_pct, dt)

    if held >= hrg.MIN_HELD_SHARES:
        entry_day = context.entry_day.get(sym, day_key)
        held_days = 0
        try:
            held_days = (
                datetime.strptime(day_key, "%Y-%m-%d")
                - datetime.strptime(entry_day, "%Y-%m-%d")
            ).days
        except Exception:
            held_days = 0

        half_taken = sym in getattr(context, "half_profit_taken", set())
        exit_action, reason = dhg.exit_signal(
            header,
            daily_pct,
            held_days=held_days,
            intraday_state=intraday,
            half_taken=half_taken,
        )
        if exit_action:
            if exit_action == "sell_half":
                eid = "half_%s_%s" % (code, day_key)
                if eid not in context.fired_ids:
                    half_shares = max(hrg.MIN_HELD_SHARES, (held // 200) * 100)
                    print("[dragon] EXIT_HALF", sym, reason, daily_pct, "shares=%d" % half_shares)
                    trade = {"op": "sell_shares", "shares": half_shares}
                    if hrg.execute_trade(trade, sym, price, cash, get_position, _order_apis()):
                        context.fired_ids.add(eid)
                        context.half_profit_taken.add(sym)
            else:
                eid = "exit_%s_%s" % (code, day_key)
                if eid not in context.fired_ids:
                    print("[dragon] EXIT", sym, reason, daily_pct)
                    trade = {"op": "sell_all"}
                    hrg.execute_trade(trade, sym, price, cash, get_position, _order_apis())
                    context.fired_ids.add(eid)
                    context.half_profit_taken.discard(sym)
        return

    bid = "buy_%s_%s" % (code, day_key)
    if bid in context.fired_ids:
        return

    max_pos = dhg.max_positions_for_phase(header)
    n_dragon = dhg.count_dragon_positions(pos_list, context.dragon_items)
    if max_pos <= 0 or n_dragon >= max_pos:
        return

    pos_pct = _position_ratio(cash)
    cap = dhg.position_cap_pct(header)
    if pos_pct >= cap:
        return

    ok, reason = dhg.entry_signal(
        dragon, price, daily_pct, header, dt=dt, intraday_state=intraday
    )
    if not ok:
        return

    shares = dhg.max_shares_for_dragon(header, cash, _nav, dragon, price)
    if shares < hrg.MIN_HELD_SHARES:
        return

    trade = {"op": "buy_shares", "shares": shares, "max_position_pct": cap}
    print(
        "[dragon] BUY/%s" % reason,
        sym,
        dragon.get("name"),
        "rank=%s" % dragon.get("rank_no"),
        "%.2f%%" % daily_pct,
        "shares=%d" % shares,
    )
    if hrg.execute_trade(trade, sym, price, cash, get_position, _order_apis()):
        context.fired_ids.add(bid)
        context.entry_day[sym] = day_key


def on_bar(context, bars):
    bar_list = _normalize_bars(bars)
    if not bar_list:
        return
    dt = _now_dt(context)
    if not is_trading_session(dt):
        return

    _reset_daily_state(context)
    _maybe_reload_dragons(context, dt)
    for bar in bar_list:
        try:
            _on_bar_one(context, bar, dt)
        except Exception as exc:
            print("[dragon] on_bar error", _bar_get(bar, "symbol"), exc)


def _log_account(tag):
    try:
        print("[%s] cash=%s" % (tag, get_cash()))
        for p in get_position() or []:
            print("  pos", p.get("symbol"), p.get("volume"))
    except Exception as exc:
        print("[%s] err" % tag, exc)


if __name__ == "__main__":
    run(
        strategy_id="REPLACE_STRATEGY_ID",
        filename="dragon_main.py",
        mode=MODE_LIVE,
        token="REPLACE_TOKEN",
    )
