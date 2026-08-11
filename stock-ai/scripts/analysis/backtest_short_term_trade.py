#!/usr/bin/env python3
"""No-lookahead backtest that calls the production short-term selector."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Literal

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_ai.market_codes import is_sh_sz_main_board_code
from stock_ai.short_term_selection import select_short_term_candidates


load_dotenv(ROOT / ".env")
CandidateType = Literal["BREAKOUT", "PULLBACK"]


@dataclass(frozen=True)
class BacktestTrade:
    code: str
    candidate_type: CandidateType
    signal_date: date
    entry_date: date
    exit_date: date
    signal_score: float
    entry_price: float
    exit_price: float
    exit_reason: str
    net_return_pct: float
    max_adverse_pct: float


def _mysql_engine():
    url = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal", "127.0.0.1"
    )
    if not url:
        raise RuntimeError("未配置 MYSQL_URL")
    return create_engine(url, pool_pre_ping=True)


def load_prices(engine, start: str, end: str) -> pd.DataFrame:
    history_start = (pd.Timestamp(start) - timedelta(days=180)).strftime("%Y-%m-%d")
    query = text(
        """
        SELECT ts_code, trade_date, open, high, low, close, pct_chg, amount
        FROM stock_daily
        WHERE trade_date BETWEEN :history_start AND :end
        ORDER BY ts_code, trade_date
        """
    )
    frame = pd.read_sql(
        query, engine, params={"history_start": history_start, "end": end}
    )
    frame["code"] = (
        frame["ts_code"].astype(str).str.split(".").str[0].str.zfill(6)
    )
    frame = frame[frame["code"].map(is_sh_sz_main_board_code)].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    numeric = ["open", "high", "low", "close", "pct_chg", "amount"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close", "amount"])
    frame["name"] = frame["code"]
    frame["sector"] = frame["code"]
    return frame


def _bars(frame: pd.DataFrame) -> list[dict[str, object]]:
    return [
        {
            "trade_date": row.trade_date,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "pct_chg": float(row.pct_chg or 0),
            "amount": float(row.amount),
        }
        for row in frame.itertuples(index=False)
    ]


def run_backtest(
    frame: pd.DataFrame,
    *,
    candidate_type: CandidateType,
    hold_days: int = 5,
    stop_loss: float = 0.05,
    commission_rate: float = 0.001,
    slippage_rate: float = 0.001,
    top_n: int = 5,
    start: date | None = None,
    end: date | None = None,
) -> list[BacktestTrade]:
    """Classify with bars through T only, then enter at T+1 open."""

    if hold_days < 1 or top_n < 1:
        raise ValueError("持有日和每日候选数必须为正数")
    if not 0 <= commission_rate < 0.1 or not 0 <= slippage_rate < 0.1:
        raise ValueError("佣金和滑点参数无效")
    normalized = frame.copy()
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"]).dt.date
    normalized["code"] = normalized["code"].astype(str).str.zfill(6)
    normalized = normalized.sort_values(["code", "trade_date"]).reset_index(drop=True)
    grouped = normalized.groupby("code", sort=True)
    normalized["ma5"] = grouped["close"].transform(lambda values: values.rolling(5).mean())
    normalized["ma10"] = grouped["close"].transform(lambda values: values.rolling(10).mean())
    normalized["ma20"] = grouped["close"].transform(lambda values: values.rolling(20).mean())
    normalized["prior_amount5"] = grouped["amount"].transform(
        lambda values: values.shift(1).rolling(5).mean()
    )
    normalized["prior_high20"] = grouped["high"].transform(
        lambda values: values.shift(1).rolling(20).max()
    )
    normalized["return10"] = grouped["close"].transform(
        lambda values: values / values.shift(10) - 1
    )
    normalized["recent_high10"] = grouped["high"].transform(
        lambda values: values.rolling(10).max()
    )
    trend = (normalized["ma5"] > normalized["ma10"]) & (
        normalized["ma10"] > normalized["ma20"]
    )
    liquid = normalized["prior_amount5"] >= 100_000
    breakout_possible = (
        normalized["close"] > normalized["prior_high20"]
    ) & normalized["pct_chg"].between(0, 7)
    pullback_possible = (
        normalized["return10"].between(0.05, 0.25)
        & (normalized["close"] >= normalized["ma10"])
        & (normalized["close"] <= normalized["ma5"] * 1.02)
        & (normalized["amount"] <= normalized["prior_amount5"] * 1.2)
        & ((normalized["recent_high10"] - normalized["close"]) / normalized["recent_high10"]).between(0.02, 0.10)
    )
    normalized["prefilter"] = trend & liquid & (breakout_possible | pullback_possible)

    panels: dict[str, list[dict[str, object]]] = {}
    locations: dict[str, dict[date, int]] = {}
    for code, group in normalized.groupby("code", sort=True):
        records = group.to_dict("records")
        panels[code] = records
        locations[code] = {row["trade_date"]: index for index, row in enumerate(records)}
    eligible_by_date = {
        signal_date: group["code"].tolist()
        for signal_date, group in normalized[normalized["prefilter"]].groupby("trade_date")
    }
    signal_dates = sorted(set(normalized["trade_date"]))
    if start is not None:
        signal_dates = [value for value in signal_dates if value >= start]
    if end is not None:
        signal_dates = [value for value in signal_dates if value <= end]

    trades: list[BacktestTrade] = []
    for signal_date in signal_dates:
        rows: list[dict[str, object]] = []
        histories: dict[str, list[dict[str, object]]] = {}
        signal_locations: dict[str, int] = {}
        for code in eligible_by_date.get(signal_date, []):
            panel = panels[code]
            index = locations[code][signal_date]
            if index < 59 or index + 1 >= len(panel):
                continue
            history = panel[max(0, index - 119) : index + 1]
            histories[code] = [
                {
                    "trade_date": value["trade_date"],
                    "open": value["open"],
                    "high": value["high"],
                    "low": value["low"],
                    "close": value["close"],
                    "pct_chg": value["pct_chg"],
                    "amount": value["amount"],
                }
                for value in history
            ]
            signal_locations[code] = index
            current = panel[index]
            rows.append(
                {
                    "代码": code,
                    "名称": str(current.get("name", code)),
                    "所属行业": str(current.get("sector", code)),
                    "策略来源": "production-backtest",
                }
            )
        if not rows:
            continue
        selected = select_short_term_candidates(
            analysis_date=signal_date,
            rows=rows,
            bars_by_code=histories,
            holding_codes=set(),
            st_codes=set(),
            limit=top_n,
        )
        for candidate in selected.candidates:
            if candidate.candidate_type != candidate_type:
                continue
            panel = panels[candidate.code]
            signal_index = signal_locations[candidate.code]
            entry_index = signal_index + 1
            entry_row = panel[entry_index]
            entry_price = float(entry_row["open"]) * (1 + slippage_rate)
            final_index = min(entry_index + hold_days - 1, len(panel) - 1)
            window = panel[entry_index : final_index + 1]
            stop_price = entry_price * (1 - stop_loss)
            stop_rows = [row for row in window if float(row["low"]) <= stop_price]
            if not stop_rows:
                exit_row = window[-1]
                raw_exit = float(exit_row["close"])
                exit_reason = "到期"
            else:
                exit_row = stop_rows[0]
                raw_exit = min(float(exit_row["open"]), stop_price)
                exit_reason = "止损"
            exit_price = raw_exit * (1 - slippage_rate)
            net_return = (exit_price / entry_price - 1 - 2 * commission_rate) * 100
            max_adverse = (min(float(row["low"]) for row in window) / entry_price - 1) * 100
            trades.append(
                BacktestTrade(
                    code=candidate.code,
                    candidate_type=candidate.candidate_type,
                    signal_date=signal_date,
                    entry_date=entry_row["trade_date"],
                    exit_date=exit_row["trade_date"],
                    signal_score=candidate.setup_score,
                    entry_price=round(entry_price, 4),
                    exit_price=round(exit_price, 4),
                    exit_reason=exit_reason,
                    net_return_pct=round(net_return, 4),
                    max_adverse_pct=round(max_adverse, 4),
                )
            )
    return sorted(trades, key=lambda item: (item.signal_date, item.code))


def summarize(trades: list[BacktestTrade]) -> dict[str, float | int | None]:
    returns = [trade.net_return_pct for trade in trades]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value <= 0]
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        equity *= 1 + value / 100
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)
    profit_loss_ratio = None
    if wins and losses:
        profit_loss_ratio = (sum(wins) / len(wins)) / abs(sum(losses) / len(losses))
    return {
        "sample_size": len(returns),
        "win_rate": round(len(wins) / len(returns), 6) if returns else None,
        "profit_loss_ratio": round(profit_loss_ratio, 6) if profit_loss_ratio is not None else None,
        "expectancy_pct": round(sum(returns) / len(returns), 6) if returns else None,
        "max_drawdown_pct": round(max_drawdown * 100, 6),
    }


def _json_default(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"unsupported JSON type: {type(value).__name__}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="使用生产规则进行短线无未来函数回测")
    parser.add_argument("--start", default="2025-01-02")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--stop-loss", type=float, default=0.05)
    parser.add_argument("--commission-rate", type=float, default=0.001)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--output", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    prices = load_prices(_mysql_engine(), args.start, args.end)
    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)
    reports: dict[str, dict[str, object]] = {}
    for candidate_type in ("BREAKOUT", "PULLBACK"):
        trades = run_backtest(
            prices,
            candidate_type=candidate_type,
            hold_days=args.hold_days,
            stop_loss=args.stop_loss,
            commission_rate=args.commission_rate,
            slippage_rate=args.slippage_rate,
            top_n=args.top_n,
            start=start_date,
            end=end_date,
        )
        reports[candidate_type] = {
            "metrics": summarize(trades),
        }
    payload = {
        "rule": "stock_ai.short_term_selection production rules",
        "entry": "next_session_open",
        "commission_rate": args.commission_rate,
        "slippage_rate": args.slippage_rate,
        "results": reports,
    }
    if args.output == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))
    else:
        print("短线生产规则回测（T 日收盘信号，T+1 开盘入场）")
        for candidate_type, result in reports.items():
            metrics = result["metrics"]
            print(
                f"{candidate_type}: 样本 {metrics['sample_size']}，胜率 {metrics['win_rate']}，"
                f"盈亏比 {metrics['profit_loss_ratio']}，期望 {metrics['expectancy_pct']}%，"
                f"最大回撤 {metrics['max_drawdown_pct']}%"
            )
        print("回测不代表未来收益，也不会触发自动下单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
