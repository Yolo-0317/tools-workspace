#!/usr/bin/env python3
"""持仓行情查询：MySQL portfolio_positions + OpenCLI 东财现价。"""

from __future__ import annotations

import sys
from pathlib import Path

STOCK_AI_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STOCK_AI_ROOT))

from scripts.tools.fetch_eastmoney_quotes import EastmoneyQuote, fetch_quotes
from scripts.tools.portfolio_db import DbPosition, load_positions


def _format_line(position: DbPosition, quote: EastmoneyQuote | None) -> str:
    name = position.name or position.code
    code = position.code
    if quote is None:
        return f"{name}({code}): 获取失败"

    line = f"{name}({code}): {quote.price}元 {quote.change_amt:+.2f}({quote.change_pct:+.2f}%)"
    if position.shares and position.cost:
        pnl_amt = (quote.price - position.cost) * position.shares
        pnl_pct = (quote.price / position.cost - 1) * 100
        line += f" | 持仓{position.shares} 成本{position.cost:.3f} 盈亏{pnl_amt:+.0f}({pnl_pct:+.1f}%)"
    return line


def load_holdings() -> list[DbPosition]:
    return load_positions()


def print_holdings_quotes(positions: list[DbPosition] | None = None) -> None:
    positions = positions if positions is not None else load_holdings()
    if not positions:
        print("错误: MySQL 无持仓数据")
        print("请先运行: uv run python -m scripts.tools.sync_portfolio_from_card")
        return

    try:
        quotes = fetch_quotes([p.code for p in positions])
    except Exception as exc:
        print(f"行情查询失败: {exc}")
        return

    for position in positions:
        print(_format_line(position, quotes.get(position.code)))


if __name__ == "__main__":
    holdings = load_holdings()
    print(f"持仓股票 {len(holdings)} 只:")
    print_holdings_quotes(holdings)
