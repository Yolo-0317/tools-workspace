# coding=utf-8
"""
stock-ai 仿真策略（终端一站式）

1. 综合选股复刻 — stock_selection_combined（日频，09:35）
2. 执行卡盘中规则 — P0～P4 + P-买（60s bar，on_bar 实时触发）

数据与下单：掘金 gm.api。规则文件 rules.json 由 export_emquant_rules.py 生成。
"""
from __future__ import print_function, absolute_import, unicode_literals

import json
import os
import sys
from datetime import datetime, time

from gm.api import *

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import combined_selection_gm as csg
import holdings_rules_gm as hrg

RULES_FILE = os.path.join(_DIR, "rules.json")
UNIVERSE_INDEX = "SHSE.000300"
MAX_POSITIONS = 5
CASH_RESERVE = 0.15
MAX_SINGLE_WEIGHT = 0.25
DRIFT_THRESHOLD = 0.03
HISTORY_BARS = 720
UNIVERSE_TOP_MV = 120
BAR_FREQ = "60s"
BAR_COUNT = 10
SCHEDULE_TIMES = ("09:35:00", "10:30:00", "13:05:00", "14:45:00")


def _normalize_bars(bars):
    """gm on_bar 可能传 list 或单条 bar；勿用 bar.get（会与字段名冲突）。"""
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


def is_main_board(symbol):
    code = symbol.split(".")[-1] if "." in symbol else symbol
    if code.startswith(("688", "689", "8", "4", "92", "300", "301")):
        return False
    return code.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))


def init(context):
    context.universe_index = UNIVERSE_INDEX
    context.max_positions = MAX_POSITIONS
    context.cash_reserve = CASH_RESERVE
    context.max_single = MAX_SINGLE_WEIGHT
    context.drift_threshold = DRIFT_THRESHOLD
    context.target_weights = {}
    context.pool_date = None
    context.market_regime = "neutral"
    context.market_score_adj = 0
    context.fired_ids = set()
    context.fired_day = None
    context.block_buy_today = set()

    cfg = hrg.load_rules(RULES_FILE)
    context.holdings_rules = cfg.get("holdings_rules") or []
    context.buy_triggers = cfg.get("buy_triggers") or []
    context.ban_codes = set(cfg.get("ban_codes") or ["600873"])

    pos_list = get_position() or []
    symbols = set()
    held_rule_syms = 0
    for r in context.holdings_rules:
        gm_sym = hrg.ts_code_to_gm(r["code"])
        if hrg.held_volume(gm_sym, pos_list) >= hrg.MIN_HELD_SHARES:
            symbols.add(gm_sym)
            held_rule_syms += 1
    for bt in context.buy_triggers:
        symbols.add(hrg.ts_code_to_gm(bt["code"]))
    for code in context.ban_codes:
        symbols.add(hrg.ts_code_to_gm(code))

    context.subscribed = list(symbols)
    for sym in context.subscribed:
        subscribe(symbols=sym, frequency=BAR_FREQ, count=BAR_COUNT)

    for t in SCHEDULE_TIMES:
        schedule(schedule_func=on_session, date_rule="1d", time_rule=t)

    print(
        "[stock-ai] init rules=%d buy_triggers=%d subscribe=%d "
        "(holdings_rules active on %d symbols with sim position>=%d)"
        % (
            len(context.holdings_rules),
            len(context.buy_triggers),
            len(context.subscribed),
            held_rule_syms,
            hrg.MIN_HELD_SHARES,
        )
    )
    _log_account("init")


def _reset_daily_state(context):
    day = _now_dt(context).strftime("%Y-%m-%d")
    if context.fired_day == day:
        return
    context.fired_day = day
    context.fired_ids = set()
    context.block_buy_today = set()


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
        "sell_all": _sell_all,
        "sell_shares": _sell_shares,
        "buy_shares": _buy_shares,
    }


def _sell_all(symbol, price):
    order_target_percent(
        symbol=symbol,
        percent=0,
        order_type=OrderType_Limit,
        position_side=PositionSide_Long,
        price=price,
    )


def _sell_shares(symbol, shares, price):
    order_volume(
        symbol=symbol,
        volume=int(shares),
        side=OrderSide_Sell,
        order_type=OrderType_Limit,
        position_effect=PositionEffect_Close,
        price=price,
    )


def _buy_shares(symbol, shares, price):
    order_volume(
        symbol=symbol,
        volume=int(shares),
        side=OrderSide_Buy,
        order_type=OrderType_Limit,
        position_effect=PositionEffect_Open,
        price=price,
    )


def _run_holdings_rules(context, sym, price, daily_pct, cash):
    """仅对仿真户持仓>=整手的标的执行执行卡减仓/止损（与 stock-ai 监控逻辑隔离）。"""
    for rule in context.holdings_rules:
        if hrg.ts_code_to_gm(rule.get("code", "")) != sym:
            continue
        rid = rule.get("id", "")
        if rid in context.fired_ids:
            continue
        if not hrg.rule_triggered(rule, price, daily_pct):
            continue
        trade = rule.get("trade") or {}
        if trade.get("op") == "block_buy":
            context.block_buy_today.add(sym)
            context.fired_ids.add(rid)
            print("[stock-ai] rule block_buy", rid, sym, daily_pct)
            continue
        print("[stock-ai] RULE", rid, sym, price, daily_pct, trade)
        if not hrg.execute_trade(trade, sym, price, cash, get_position, _order_apis()):
            print("[stock-ai] RULE not executed", rid, sym, trade.get("op"))
        context.fired_ids.add(rid)


def _ensure_subscribed(context, sym):
    if sym in context.subscribed:
        return
    subscribe(symbols=sym, frequency=BAR_FREQ, count=BAR_COUNT)
    context.subscribed.append(sym)


def _on_bar_one(context, bar, dt):
    sym = _bar_get(bar, "symbol")
    if not sym:
        return
    price = float(_bar_get(bar, "close") or 0)
    if price <= 0:
        return

    now_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    daily_pct = _daily_pct(sym, now_str)
    code = hrg.gm_to_code(sym)
    cash = get_cash()

    if sym in context.block_buy_today and daily_pct > hrg.MAX_CHASE_PCT:
        return

    pos_list = get_position() or []
    if hrg.held_volume(sym, pos_list) >= hrg.MIN_HELD_SHARES:
        _run_holdings_rules(context, sym, price, daily_pct, cash)

    for bt in context.buy_triggers:
        if hrg.ts_code_to_gm(bt.get("code", "")) != sym:
            continue
        bid = bt.get("id", "")
        if bid in context.fired_ids:
            continue
        if sym in context.block_buy_today:
            continue
        if code in context.ban_codes:
            continue
        if daily_pct >= hrg.MAX_CHASE_PCT:
            continue
        if not hrg.buy_triggered(bt, price, daily_pct):
            continue
        pos_pct = hrg.position_ratio_pct(cash)
        if pos_pct > float(bt.get("max_position_pct", hrg.HIGH_POSITION_PCT)):
            continue
        trade = {"op": "buy_shares", "shares": bt.get("shares", 100), "max_position_pct": bt.get("max_position_pct", 75)}
        print("[stock-ai] BUY_TRIGGER", bid, sym, price, daily_pct)
        if not hrg.execute_trade(trade, sym, price, cash, get_position, _order_apis()):
            print("[stock-ai] BUY not executed", bid, sym)
        context.fired_ids.add(bid)


def on_bar(context, bars):
    bar_list = _normalize_bars(bars)
    if not bar_list:
        return
    dt = _now_dt(context)
    if not is_trading_session(dt):
        return

    _reset_daily_state(context)
    for bar in bar_list:
        try:
            _on_bar_one(context, bar, dt)
        except Exception as exc:
            print("[stock-ai] on_bar error", _bar_get(bar, "symbol"), exc)


def _log_account(tag):
    try:
        print("[%s] cash=%s" % (tag, get_cash()))
        for p in get_position() or []:
            print("  pos", p.get("symbol"), p.get("volume"))
    except Exception as exc:
        print("[%s] err" % tag, exc)


def _last_trade_date(now_str):
    days = get_previous_n_trading_dates(exchange="SHSE", date=now_str, n=1)
    return days[0] if days else now_str


def _gm_market_regime(now_str):
    try:
        bars = history_n(
            symbol="SHSE.000300",
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
            return "neutral", 0
        prev_c, last_c = float(bars[0]["close"]), float(bars[1]["close"])
        pct = (last_c / prev_c - 1.0) * 100.0 if prev_c > 0 else 0.0
        up_ratio = 0.55 if pct > 0.5 else (0.40 if pct < -0.5 else 0.50)
        regime = csg.classify_market_regime(up_ratio)
        adj = 5 if regime == "strong" else (-5 if regime == "weak" else 0)
        return regime, adj
    except Exception as exc:
        print("[stock-ai] regime fallback:", exc)
        return "neutral", 0


def _filter_symbols(symbols, trade_date, now_dt, ban_codes):
    info = get_symbols(
        sec_type1=1010,
        symbols=symbols,
        trade_date=trade_date,
        skip_suspended=True,
        skip_st=True,
    )
    out = []
    for item in info:
        sym = item["symbol"]
        if not is_main_board(sym):
            continue
        if hrg.gm_to_code(sym) in ban_codes:
            continue
        listed = item.get("listed_date")
        delisted = item.get("delisted_date")
        if listed and listed > now_dt:
            continue
        if delisted and delisted <= now_dt:
            continue
        out.append(sym)
    return out


def _bars_to_df(bars):
    import pandas as pd

    df = pd.DataFrame(bars) if not hasattr(bars, "columns") else bars.copy()
    for col in ("open", "high", "low", "close", "amount", "volume", "pct_chg"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "pct_chg" not in df.columns and "close" in df.columns:
        df["pct_chg"] = df["close"].pct_change() * 100.0
    if "amount" not in df.columns and "volume" in df.columns and "close" in df.columns:
        df["amount"] = df["volume"] * df["close"] / 1000.0
    return df


def select_pool_combined(context):
    now = _now_dt(context)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    last_day = _last_trade_date(now_str)
    regime, madj = _gm_market_regime(now_str)
    context.market_regime = regime
    context.market_score_adj = madj

    try:
        idx = stk_get_index_constituents(index=context.universe_index, trade_date=last_day)
        raw = list(idx["symbol"]) if hasattr(idx, "get") else [r["symbol"] for r in idx]
    except Exception as exc:
        print("[stock-ai] constituents error:", exc)
        return {}

    symbols = _filter_symbols(raw, last_day, now, context.ban_codes)
    try:
        import pandas as pd

        mv = stk_get_daily_mktvalue_pt(symbols=symbols, fields="tot_mv", trade_date=last_day, df=True)
        if mv is not None and len(mv) > 0:
            symbols = mv.sort_values("tot_mv", ascending=False).head(UNIVERSE_TOP_MV)["symbol"].tolist()
    except Exception:
        symbols = symbols[:UNIVERSE_TOP_MV]

    candidates = []
    for sym in symbols:
        if sym == hrg.ts_code_to_gm("600873"):
            continue
        try:
            bars = history_n(
                symbol=sym,
                frequency="1d",
                count=HISTORY_BARS,
                end_time=last_day,
                fields="open,high,low,close,amount,volume",
                skip_suspended=True,
                fill_missing="Last",
                adjust=ADJUST_PREV,
                df=True,
            )
        except Exception:
            continue
        if bars is None or len(bars) < 60:
            continue
        hit = csg.evaluate_symbol(_bars_to_df(bars), regime, madj)
        if hit:
            hit["symbol"] = sym
            candidates.append(hit)

    top = csg.pick_top(candidates, context.max_positions)
    weights = csg.normalize_weights(top, context.cash_reserve)
    for sym in list(weights.keys()):
        weights[sym] = min(weights[sym], context.max_single)
    print("[stock-ai] pool", list(weights.keys()))
    return weights


def _nav():
    cash = get_cash()
    if isinstance(cash, dict):
        return float(cash.get("nav") or cash.get("total_value") or 0)
    return 0.0


def rebalance(context):
    desired = context.target_weights or {}
    current = {}
    nav = _nav()
    if nav > 0:
        for p in get_position() or []:
            sym = p.get("symbol")
            mv = float(p.get("market_value") or 0)
            if sym and mv > 0:
                current[sym] = mv / nav
    for sym in sorted(set(desired) | set(current)):
        tgt, cur = desired.get(sym, 0.0), current.get(sym, 0.0)
        if sym == hrg.ts_code_to_gm("600873") and tgt > cur:
            tgt = 0.0
        if abs(tgt - cur) < context.drift_threshold:
            continue
        try:
            px = current(symbols=sym)[0]["price"]
        except Exception:
            px = None
        if not px or px <= 0:
            continue
        print("[stock-ai] rebalance", sym, cur, tgt)
        order_target_percent(
            symbol=sym,
            percent=tgt,
            order_type=OrderType_Limit,
            position_side=PositionSide_Long,
            price=px,
        )


def on_session(context):
    dt = _now_dt(context)
    if not is_trading_session(dt):
        return
    day_key = dt.strftime("%Y-%m-%d")
    if context.pool_date != day_key:
        context.target_weights = select_pool_combined(context)
        context.pool_date = day_key
        for sym in context.target_weights:
            if sym not in context.subscribed:
                subscribe(symbols=sym, frequency=BAR_FREQ, count=BAR_COUNT)
                context.subscribed.append(sym)
    if context.target_weights:
        rebalance(context)


def on_order_status(context, order):
    status = _bar_get(order, "status") if order is not None else None
    if status == 3:
        sym = _bar_get(order, "symbol")
        print("[stock-ai] filled", sym, _bar_get(order, "volume"))
        if sym and hrg.held_volume(sym, get_position() or [], get_position) >= hrg.MIN_HELD_SHARES:
            _ensure_subscribed(context, sym)


if __name__ == "__main__":
    run(
        strategy_id="REPLACE_STRATEGY_ID",
        filename="main_combined.py",
        mode=MODE_LIVE,
        token="REPLACE_TOKEN",
    )
