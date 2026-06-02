#!/usr/bin/env python3
"""从 MySQL portfolio_positions 导出掘金仿真 targets.json。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_paths, import_stock_ai_module

ensure_paths()
_portfolio_db = import_stock_ai_module("scripts/tools/portfolio_db.py")
DbPosition = _portfolio_db.DbPosition
load_positions = _portfolio_db.load_positions

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "output" / "emquant" / "targets.json"

# 与持仓执行卡 / investment-agent 红线对齐的关键词
_NO_BUY_HINTS = ("不追高", "禁止补仓", "严禁补仓", "暂不", "观望", "不接", "勿补")
_ZERO_HINTS = ("清仓", "全卖")
_REDUCE_HINTS = ("减仓", "减持")


def _action_flags(action: str) -> dict:
    a = (action or "").strip()
    flags = {"trade_allowed": True, "no_buy": False, "note": a[:80]}
    if any(h in a for h in _ZERO_HINTS):
        return {"trade_allowed": False, "no_buy": True, "note": a[:80]}
    # 「持有…跌破 x 止损」仍保留目标权重，由盘中监控/人工处理
    if "止损" in a and not a.startswith("持有"):
        return {"trade_allowed": False, "no_buy": True, "note": a[:80]}
    if any(h in a for h in _NO_BUY_HINTS):
        flags["no_buy"] = True
    if any(h in a for h in _REDUCE_HINTS) or re.search(r"减\s*\d+\s*股", a):
        flags["no_buy"] = True
    return flags


def _ts_code(code: str) -> str:
    c = str(code).zfill(6)
    if c.startswith(("5", "6", "9")):
        return f"{c}.SH"
    return f"{c}.SZ"


def build_targets(
    positions: list[DbPosition],
    *,
    cash_reserve: float,
    max_single: float,
    observe_only: bool,
) -> dict:
    tradable = [p for p in positions if re.fullmatch(r"\d{6}", str(p.code).zfill(6))]
    eligible = []
    for p in tradable:
        flags = _action_flags(p.action)
        if flags.get("trade_allowed") is False:
            continue
        eligible.append((p, flags))

    n = len(eligible)
    investable = max(0.0, 1.0 - cash_reserve)
    per = (investable / n) if n else 0.0
    per = min(per, max_single)

    targets = []
    for p, flags in eligible:
        targets.append(
            {
                "ts_code": _ts_code(p.code),
                "name": p.name,
                "weight": round(per, 4),
                "shares_ref": p.shares,
                "cost_ref": p.cost,
                "status": p.status,
                "action": p.action,
                **flags,
            }
        )

    return {
        "version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": "stock-ai portfolio_positions",
        "observe_only": observe_only,
        "cash_reserve": cash_reserve,
        "max_single_weight": max_single,
        "drift_threshold": 0.03,
        "targets": targets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="导出掘金仿真 targets.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cash-reserve", type=float, default=0.15, help="保留现金比例")
    parser.add_argument("--max-single", type=float, default=0.20)
    parser.add_argument("--observe-only", action="store_true", help="只观察不下单")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    positions = load_positions()
    if not positions:
        print("❌ MySQL 无活跃持仓，请先 sync_portfolio_from_card", file=sys.stderr)
        return 1

    payload = build_targets(
        positions,
        cash_reserve=args.cash_reserve,
        max_single=args.max_single,
        observe_only=args.observe_only,
    )

    print(f"持仓 {len(positions)} → 目标 {len(payload['targets'])} 只")
    for t in payload["targets"]:
        flags = []
        if t.get("no_buy"):
            flags.append("no_buy")
        if not t.get("trade_allowed", True):
            flags.append("blocked")
        extra = (" [" + ",".join(flags) + "]") if flags else ""
        print(f"  {t['name']} {t['ts_code']} w={t['weight']:.2%}{extra}")

    if args.dry_run:
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
