#!/usr/bin/env python3
"""生成短线交易候选池并写入 ``short_term_trade`` 策略桶。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
from dotenv import load_dotenv

from scripts.tools.holdings_context import load_full_decision_context
from scripts.tools.portfolio_db import save_selection_daily_results
from scripts.tools.selection_results import merge_selection_strategies_df
from stock_ai.short_term_trade import build_trade_candidates


def main() -> int:
    load_dotenv(ROOT / ".env")
    try:
        trade_date, rows, _ = merge_selection_strategies_df(strategies=("combined", "ma5", "watch", "five_factor"))
    except FileNotFoundError as exc:
        print(f"短线候选池未生成：{exc}。请先同步日线并运行基础选股策略。")
        return 0
    holding_codes, _ = load_full_decision_context()
    candidates = build_trade_candidates(rows, holding_codes=holding_codes, limit=5)
    payload = candidates.to_dict("records") if not candidates.empty else []
    save_selection_daily_results(trade_date, payload, strategy="short_term_trade")
    if candidates.empty:
        print("短线候选池为空：未发现通过追高、流动性和持仓过滤的标的。")
        return 0
    columns = [column for column in ("代码", "名称", "候选类型", "交易候选分", "收盘价", "涨幅%", "建议动作") if column in candidates]
    print(candidates[columns].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
