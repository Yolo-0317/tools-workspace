#!/usr/bin/env python3
"""Chronological T+1-open to T+5-close validation for the gene-watch lane."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Callable, Iterable, Mapping

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from core_v2.board_filters import passes_base_filter, passes_crash_filter
from stock_ai.limit_up_gene_watch import PRECISION_POLICY, evaluate_limit_up_gene_candidate
from stock_ai.limit_up_logic import LimitUpContext, analyze_limit_up_logic
from stock_ai.selection_validation import (
    BacktestMetrics,
    GENE_WATCH_CRITERIA,
    chronological_splits,
    evaluate_promotion,
)


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "core_v2") not in sys.path:
    sys.path.insert(0, str(ROOT / "core_v2"))
SCHEMA_VERSION = "limit-up-gene-watch-validation-v1"
RULE_VERSION = "limit-up-gene-watch-1.0.0"
Evaluator = Callable[[str, pd.DataFrame, date], Iterable[str] | Mapping[str, float]]


@dataclass(frozen=True)
class BacktestTrade:
    code: str
    signal_date: date
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    net_return: float
    score: float = 0.0
    entry_day_pct_chg: float = 0.0
    next_day_limit_up: bool = False


def trade_return(
    entry_open: float,
    exit_close: float,
    *,
    commission_rate: float,
    slippage_rate: float,
) -> float:
    if entry_open <= 0 or exit_close <= 0:
        raise ValueError("prices must be positive")
    if min(commission_rate, slippage_rate) < 0:
        raise ValueError("cost rates must be non-negative")
    buy = float(entry_open) * (1.0 + slippage_rate) * (1.0 + commission_rate)
    sell = float(exit_close) * (1.0 - slippage_rate) * (1.0 - commission_rate)
    return sell / buy - 1.0


def run_backtest(
    panel: pd.DataFrame,
    *,
    evaluator: Evaluator,
    signal_dates: Iterable[date] | None = None,
    hold_days: int = 5,
    commission_rate: float = 0.0008,
    slippage_rate: float = 0.001,
    max_signals_per_day: int | None = None,
) -> list[BacktestTrade]:
    """Pass only bars through T to the evaluator and execute on later bars."""
    if hold_days < 1:
        raise ValueError("hold_days must be positive")
    frame = panel.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    frame["ts_code"] = frame["ts_code"].astype(str)
    frame = frame.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    dates = tuple(sorted(set(signal_dates or frame["trade_date"].unique())))
    trades: list[BacktestTrade] = []

    for ts_code, bars in frame.groupby("ts_code", sort=True):
        bars = bars.sort_values("trade_date").reset_index(drop=True)
        positions = {value: index for index, value in enumerate(bars["trade_date"])}
        code = str(ts_code).split(".")[0].zfill(6)
        for signal_date in dates:
            position = positions.get(signal_date)
            if position is None or position + hold_days >= len(bars):
                continue
            history = bars.iloc[: position + 1].copy()
            evaluated = evaluator(code, history, signal_date)
            if isinstance(evaluated, Mapping):
                selected = set(evaluated)
                score = float(evaluated.get(code, 0.0))
            else:
                selected = set(evaluated)
                score = 0.0
            if code not in selected:
                continue
            entry = bars.iloc[position + 1]
            exit_row = bars.iloc[position + hold_days]
            entry_price = float(entry["open"])
            exit_price = float(exit_row["close"])
            if entry_price <= 0 or exit_price <= 0:
                continue
            trades.append(
                BacktestTrade(
                    code=code,
                    signal_date=signal_date,
                    entry_date=entry["trade_date"],
                    exit_date=exit_row["trade_date"],
                    entry_price=entry_price,
                    exit_price=exit_price,
                    net_return=trade_return(
                        entry_price,
                        exit_price,
                        commission_rate=commission_rate,
                        slippage_rate=slippage_rate,
                    ),
                    score=score,
                    entry_day_pct_chg=float(entry.get("pct_chg") or 0.0),
                    next_day_limit_up=(
                        float(entry.get("pct_chg") or 0.0)
                        >= (19.5 if code.startswith(("30", "68")) else 9.5)
                    ),
                )
            )
    ordered = sorted(trades, key=lambda item: (item.signal_date, -item.score, item.code))
    if max_signals_per_day is None:
        return ordered
    if max_signals_per_day < 1:
        raise ValueError("max_signals_per_day must be positive")
    capped: list[BacktestTrade] = []
    counts: dict[date, int] = {}
    for trade in ordered:
        count = counts.get(trade.signal_date, 0)
        if count >= max_signals_per_day:
            continue
        capped.append(trade)
        counts[trade.signal_date] = count + 1
    return capped


def catch_metrics(trades: Iterable[BacktestTrade]) -> dict[str, float | int]:
    resolved = list(trades)
    hits = sum(1 for trade in resolved if trade.next_day_limit_up)
    return {
        "signal_count": len(resolved),
        "next_day_limit_up_count": hits,
        "next_day_limit_up_rate": hits / len(resolved) if resolved else 0.0,
    }


def _metrics(trades: Iterable[BacktestTrade], *, shape: str) -> BacktestMetrics:
    resolved = list(trades)
    returns = [item.net_return * 100.0 for item in resolved]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value <= 0]
    daily_returns: dict[date, list[float]] = {}
    for trade in resolved:
        daily_returns.setdefault(trade.signal_date, []).append(trade.net_return * 100.0)
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for values in daily_returns.values():
        value = sum(values) / len(values)
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak * 100.0)
    average_win = sum(wins) / len(wins) if wins else 0.0
    average_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    ratio = average_win / average_loss if average_loss > 0 else (999.0 if wins else 0.0)
    return BacktestMetrics(
        trade_count=len(returns),
        wins=len(wins),
        expectancy=sum(returns) / len(returns) if returns else 0.0,
        shape_counts={shape: len(returns)},
        max_drawdown_pct=max_drawdown,
        profit_loss_ratio=ratio,
    )


def _gene_evaluator(code: str, bars: pd.DataFrame, signal_date: date) -> tuple[str, ...]:
    latest = bars.iloc[-1]
    amount = float(latest["amount"] or 0.0)
    if not passes_base_filter(code, float(latest["close"]), amount):
        return ()
    result = analyze_limit_up_logic(
        code,
        code,
        bars.tail(60).to_dict(orient="records"),
        LimitUpContext(observed_at=datetime.combine(signal_date, datetime.min.time()).astimezone()),
    )
    candidate = evaluate_limit_up_gene_candidate(
        result,
        amount_wan=amount / 10.0,
        base_filter_passed=True,
        policy=PRECISION_POLICY,
    )
    return {code: float(candidate.score)} if candidate is not None else {}


def _combined_evaluator(code: str, bars: pd.DataFrame, signal_date: date) -> tuple[str, ...]:
    if len(bars) < 60:
        return ()
    latest = bars.iloc[-1]
    amount = float(latest["amount"] or 0.0)
    if not passes_crash_filter(code, float(latest["pct_chg"])):
        return ()
    if not passes_base_filter(code, float(latest["close"]), amount):
        return ()
    from core_v2.combined_selection_engine import evaluate_combined_candidate

    row = evaluate_combined_candidate(
        bars,
        code,
        market_score_adj=0,
        hot_sectors=[],
        market_regime="neutral",
        holdings_codes=set(),
        account_position_pct=0.0,
        industry_map={},
        advisor_phase=0,
        skip_advisor=True,
        skip_account_caps=True,
        board_market_regime="neutral",
        skip_weak_market_block=False,
    )
    if not row:
        return ()
    return (
        {code: float(row.get("总分") or 0.0)}
        if str(row.get("建议动作") or "") in {"强势关注", "观察买入", "小仓埋伏"}
        else {}
    )


def _load_panel(engine, *, start: date, end: date, hold_days: int) -> pd.DataFrame:
    return pd.read_sql(
        text(
            """
            SELECT ts_code, trade_date, open, high, low, close, pct_chg, amount
            FROM stock_daily
            WHERE trade_date BETWEEN :warmup AND :forward
            ORDER BY ts_code, trade_date
            """
        ),
        engine,
        params={
            "warmup": start - timedelta(days=120),
            "forward": end + timedelta(days=max(14, hold_days * 3)),
        },
    )


def _bounds(values: tuple[date, ...]) -> dict[str, str]:
    return {"start": values[0].isoformat(), "end": values[-1].isoformat()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="涨停基因观察池时序回测")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--commission-rate", type=float, default=0.0008)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--artifact", default="output/validation/limit_up_gene_watch.json")
    args = parser.parse_args(argv)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    load_dotenv(ROOT / ".env")
    mysql_url = os.getenv("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    if not mysql_url:
        raise RuntimeError("未配置 MYSQL_URL")
    engine = create_engine(mysql_url, pool_pre_ping=True)
    panel = _load_panel(engine, start=start, end=end, hold_days=args.hold_days)
    print(f"loaded {len(panel)} daily bars", flush=True)
    research_dates = tuple(
        value for value in sorted(set(pd.to_datetime(panel["trade_date"]).dt.date))
        if start <= value <= end
    )
    split = chronological_splits(research_dates)
    test_dates = split.test
    print(f"replaying baseline on {len(test_dates)} test sessions", flush=True)
    baseline_trades = run_backtest(
        panel,
        evaluator=_combined_evaluator,
        signal_dates=test_dates,
        hold_days=args.hold_days,
        commission_rate=args.commission_rate,
        slippage_rate=args.slippage_rate,
        max_signals_per_day=5,
    )
    print(f"baseline trades: {len(baseline_trades)}; replaying gene watch", flush=True)
    candidate_trades = run_backtest(
        panel,
        evaluator=_gene_evaluator,
        signal_dates=test_dates,
        hold_days=args.hold_days,
        commission_rate=args.commission_rate,
        slippage_rate=args.slippage_rate,
        max_signals_per_day=5,
    )
    baseline = _metrics(baseline_trades, shape="COMBINED")
    candidate = _metrics(candidate_trades, shape="LIMIT_UP_GENE")
    decision = evaluate_promotion(
        baseline=baseline,
        candidate=candidate,
        criteria=GENE_WATCH_CRITERIA,
    )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_bounds": {"start": start.isoformat(), "end": end.isoformat()},
        "split_bounds": {
            "train": _bounds(split.train),
            "validation": _bounds(split.validation),
            "test": _bounds(split.test),
        },
        "costs": {
            "commission_rate": args.commission_rate,
            "slippage_rate": args.slippage_rate,
        },
        "hold_days": args.hold_days,
        "selected_profile": "limit_up_gene_watch" if decision.promoted else None,
        "metrics": {
            "baseline_test": baseline.to_dict(),
            "candidate_test": candidate.to_dict(),
        },
        "catch_metrics": {
            "baseline_test": catch_metrics(baseline_trades),
            "candidate_test": catch_metrics(candidate_trades),
        },
        "promoted": decision.promoted,
        "reasons": list(decision.reasons),
        "limitations": [
            "historical news veto coverage is not reconstructed; production still applies the live veto",
            "combined baseline uses neutral market regime and no historical hot-sector enrichment",
        ],
    }
    destination = ROOT / args.artifact if not Path(args.artifact).is_absolute() else Path(args.artifact)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(destination), "promoted": decision.promoted, "reasons": decision.reasons}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
