# coding=utf-8
"""执行卡盘中规则：判定 + 仿真下单（对齐 monitor_holdings_alerts）。"""
from __future__ import annotations

import json
import os

BAN_GM = frozenset(["SHSE.600873"])
MAX_CHASE_PCT = 5.0
HIGH_POSITION_PCT = 75.0
MIN_HELD_SHARES = 100


def ts_code_to_gm(code):
    c = str(code).zfill(6)
    if c.startswith(("5", "6", "9")):
        return "SHSE.%s" % c
    return "SZSE.%s" % c


def gm_to_code(symbol):
    return symbol.split(".")[-1] if "." in symbol else symbol


def load_rules(path):
    if not path or not os.path.isfile(path):
        return {"holdings_rules": [], "buy_triggers": [], "ban_codes": ["600873"]}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def rule_triggered(rule, price, daily_pct):
    rtype = rule.get("type")
    if rtype == "price_below":
        return price < float(rule["price"])
    if rtype == "price_above":
        return price >= float(rule["price"])
    if rtype == "price_in_range":
        return float(rule["low"]) <= price <= float(rule["high"])
    if rtype == "daily_pct_above":
        return daily_pct > float(rule.get("pct", 5))
    return False


def buy_triggered(bt, price, daily_pct):
    t = bt.get("type")
    if t == "buy_in_range":
        return (
            float(bt["low"]) <= price <= float(bt["high"])
            and daily_pct < float(bt.get("max_daily_pct", 3))
        )
    if t == "buy_on_dip":
        return price <= float(bt["price"])
    return False


def _cash_field(cash_dict, key, default=0):
    if not cash_dict:
        return default
    if isinstance(cash_dict, dict):
        return cash_dict.get(key, default)
    return getattr(cash_dict, key, default)


def position_ratio_pct(cash_dict):
    if not cash_dict:
        return 0.0
    nav = float(_cash_field(cash_dict, "nav") or _cash_field(cash_dict, "total_value") or 0)
    if nav <= 0:
        return 0.0
    market = float(_cash_field(cash_dict, "market_value") or _cash_field(cash_dict, "fpnl") or 0)
    if not _cash_field(cash_dict, "market_value") and _cash_field(cash_dict, "available") is not None:
        market = nav - float(_cash_field(cash_dict, "available") or 0)
    return market / nav * 100.0


def _round_lot(shares):
    s = int(shares) // 100 * 100
    return max(s, 100)


def held_volume(symbol, pos_list, get_position_fn=None):
    """仿真户该标的持仓股数（整手策略用 MIN_HELD_SHARES 门槛）。"""
    if pos_list is None and get_position_fn is not None:
        pos_list = get_position_fn() or []
    if not pos_list:
        return 0
    for p in pos_list:
        psym = p.get("symbol") if isinstance(p, dict) else getattr(p, "symbol", None)
        if psym != symbol:
            continue
        vol = p.get("volume") if isinstance(p, dict) else getattr(p, "volume", 0)
        avail = p.get("available") if isinstance(p, dict) else getattr(p, "available", 0)
        return int(vol or avail or 0)
    return 0


def execute_trade(trade, symbol, price, cash_dict, get_position_fn, order_apis):
    """order_apis: dict sell_all, sell_shares, buy_shares"""
    op = (trade or {}).get("op", "alert_only")
    if op == "alert_only" or op == "block_buy":
        return False

    pos_list = get_position_fn() or []
    pos_vol = held_volume(symbol, pos_list)

    if op == "sell_all":
        if pos_vol <= 0:
            return False
        order_apis["sell_all"](symbol, price)
        return True

    if op == "sell_shares":
        shares = _round_lot(trade.get("shares", 100))
        shares = min(shares, pos_vol)
        if shares < 100:
            return False
        order_apis["sell_shares"](symbol, shares, price)
        return True

    if op == "buy_shares":
        if symbol in BAN_GM:
            return False
        pos_pct = position_ratio_pct(cash_dict)
        max_pct = float(trade.get("max_position_pct", HIGH_POSITION_PCT))
        if pos_pct > max_pct:
            print("[stock-ai] skip buy high position", pos_pct)
            return False
        shares = _round_lot(trade.get("shares", 100))
        order_apis["buy_shares"](symbol, shares, price)
        return True

    return False
