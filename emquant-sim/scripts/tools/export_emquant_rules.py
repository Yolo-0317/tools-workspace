#!/usr/bin/env python3
"""从持仓执行卡导出掘金仿真 rules.json（与 monitor_holdings_alerts 同源）。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_paths, import_stock_ai_module, stock_ai_root

ensure_paths()
parse_card = import_stock_ai_module("scripts/tools/holdings_card_parser.py").parse_card

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CARD = stock_ai_root() / "investment-agent" / "持仓执行卡.md"
DEFAULT_OUT = ROOT / "output" / "emquant" / "rules.json"

# 与执行卡动作对齐（仿真整手）
TRADE_BY_ID = {
    "meihua_stop_9": {"op": "sell_all"},
    "meihua_reduce_105": {"op": "sell_shares", "shares": 200},
    "nangwang_reduce_16": {"op": "sell_shares", "shares": 200},
    "nangwang_stop_14": {"op": "sell_shares", "shares": 200},
    "guangfa_swap_zone": {"op": "sell_shares", "shares": 200},
    "guangfa_lock_85": {"op": "sell_shares", "shares": 200},
    "baoxin_add_55": {"op": "buy_shares", "shares": 100, "max_position_pct": 75},
    "baoxin_no_chase": {"op": "block_buy"},
    "guanghe_stop_430": {"op": "sell_shares", "shares": 500},
    "hedian_stop_860": {"op": "sell_shares", "shares": 300},
}

# P-买 队列（执行卡「候选买入队列」）
BUY_TRIGGERS = [
    {
        "id": "buy_wanneng",
        "code": "000543",
        "name": "皖能电力",
        "type": "buy_in_range",
        "low": 9.50,
        "high": 9.65,
        "max_daily_pct": 3.0,
        "shares": 200,
        "max_position_pct": 75,
    },
    {
        "id": "buy_youyou",
        "code": "603697",
        "name": "有友食品",
        "type": "buy_in_range",
        "low": 10.70,
        "high": 10.90,
        "max_daily_pct": 3.0,
        "shares": 100,
        "max_position_pct": 75,
    },
    {
        "id": "buy_ccb",
        "code": "601939",
        "name": "建设银行",
        "type": "buy_on_dip",
        "price": 9.90,
        "shares": 100,
        "max_position_pct": 60,
    },
]

BAN_CODES = frozenset(["600873"])


def enrich_trade(rule: dict) -> dict:
    rid = rule.get("id", "")
    if rid in TRADE_BY_ID:
        rule["trade"] = dict(TRADE_BY_ID[rid])
        return rule
    code = rule.get("code", "")
    rtype = rule.get("type", "")
    if rtype == "daily_pct_above":
        rule["trade"] = {"op": "block_buy"}
    elif rtype == "price_below" and code == "600873":
        rule["trade"] = {"op": "sell_all"}
    elif rtype == "price_below" and code == "003816":
        rule["trade"] = {"op": "sell_shares", "shares": 500}
    elif rtype == "price_below" and code == "601985":
        rule["trade"] = {"op": "sell_shares", "shares": 300}
    elif rtype == "price_above":
        rule["trade"] = {"op": "sell_shares", "shares": 200}
    elif rtype == "price_in_range":
        rule["trade"] = {"op": "sell_shares", "shares": 200}
    else:
        rule["trade"] = {"op": "alert_only"}
    return rule


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", type=Path, default=DEFAULT_CARD)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.card.is_file():
        print(f"❌ 未找到 {args.card}", file=sys.stderr)
        return 1

    text = args.card.read_text(encoding="utf-8")
    positions, account, rules = parse_card(text)
    rules = [enrich_trade(r) for r in rules]

    payload = {
        "version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": str(args.card),
        "ban_codes": sorted(BAN_CODES),
        "max_chase_pct": 5.0,
        "high_position_pct": 75.0,
        "holdings_rules": rules,
        "buy_triggers": BUY_TRIGGERS,
        "positions_ref": [
            {"code": p.code, "name": p.name, "shares": p.shares} for p in positions
        ],
    }

    print(f"监控规则 {len(rules)} 条，买入触发 {len(BUY_TRIGGERS)} 条")
    for r in rules:
        print(f"  {r['id']} {r['code']} {r['type']} -> {r.get('trade')}")

    if args.dry_run:
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
