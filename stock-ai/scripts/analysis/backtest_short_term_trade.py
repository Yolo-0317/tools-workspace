#!/usr/bin/env python3
"""短线交易候选的无未来数据日线回测。

信号只使用 T 日收盘及更早日线；成交假设为 T+1 开盘，持有最多 5 个交易日。
这是“量价趋势候选层”的机械验证：题材、资金流、筹码和盘口五项确认不在
stock_daily 中，不能被伪造成历史可验证数据，仍须在实盘盘中补齐。
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, asdict
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core_v2"))
from board_filters import sql_universe_clause  # noqa: E402

load_dotenv(REPO / ".env")


@dataclass
class Trade:
    code: str
    signal_date: str
    entry_date: str
    exit_date: str
    signal_type: str
    signal_score: float
    entry_price: float
    exit_price: float
    exit_reason: str
    gross_return_pct: float
    net_return_pct: float
    max_adverse_pct: float


def _mysql_engine():
    url = os.environ.get("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    if not url:
        raise RuntimeError("未配置 MYSQL_URL")
    return create_engine(url, pool_pre_ping=True)


def load_prices(engine, start: str, end: str, board: str) -> pd.DataFrame:
    history_start = (pd.Timestamp(start) - timedelta(days=80)).strftime("%Y-%m-%d")
    query = text(
        f"""
        SELECT ts_code, trade_date, open, high, low, close, pct_chg, amount
        FROM stock_daily
        WHERE trade_date BETWEEN :history_start AND :end
          AND {sql_universe_clause(board)}
        ORDER BY ts_code, trade_date
        """
    )
    frame = pd.read_sql(query, engine, params={"history_start": history_start, "end": end})
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame["code"] = frame["ts_code"].astype(str).str.split(".").str[0].str.zfill(6)
    numeric = ["open", "high", "low", "close", "pct_chg", "amount"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    return frame.dropna(subset=["open", "high", "low", "close", "amount"])


def add_signals(
    frame: pd.DataFrame,
    start: str,
    end: str,
    *,
    signal_types: set[str],
    breakout_volume_multiple: float,
) -> pd.DataFrame:
    """构建仅可在当日收盘后得到的趋势回踩 / 突破信号。"""
    frame = frame.copy()
    calculated = [
        "ma5", "ma10", "ma20", "amount5", "prior_high20", "return10",
        "future_open", "future_dates", "signal_type", "signal_score",
    ]
    frame[["ma5", "ma10", "ma20", "amount5", "prior_high20", "return10", "future_open"]] = np.nan
    frame["future_dates"] = pd.NaT
    frame["signal_type"] = ""
    frame["signal_score"] = np.nan
    for _, group in frame.groupby("code", sort=False):
        daily = group.copy()
        daily["ma5"] = daily["close"].rolling(5).mean()
        daily["ma10"] = daily["close"].rolling(10).mean()
        daily["ma20"] = daily["close"].rolling(20).mean()
        daily["amount5"] = daily["amount"].rolling(5).mean()
        daily["prior_high20"] = daily["high"].shift(1).rolling(20).max()
        daily["return10"] = daily["close"] / daily["close"].shift(10) - 1
        daily["future_open"] = daily["open"].shift(-1)
        daily["future_dates"] = daily["trade_date"].shift(-1)

        trend = (daily["ma5"] > daily["ma10"]) & (daily["ma10"] > daily["ma20"])
        liquid = daily["amount"] >= 50_000  # Tushare amount 单位：千元，至少 5000 万
        sane_move = daily["pct_chg"].between(-2, 5)
        pullback = (
            trend
            & daily["return10"].ge(0.08)
            & daily["close"].between(daily["ma5"] * 0.98, daily["ma5"] * 1.02)
            & daily["amount"].le(daily["amount5"] * 1.2)
            & sane_move
        )
        breakout = (
            trend
            & daily["close"].gt(daily["prior_high20"])
            & daily["close"].ge(daily["high"] * 0.985)
            & daily["amount"].ge(daily["amount5"] * breakout_volume_multiple)
            & daily["pct_chg"].between(0, 5)
        )
        daily["signal_type"] = np.select(
            [pullback, breakout], ["强趋势回踩", "突破启动"], default=""
        )
        daily["signal_score"] = (
            50
            + (daily["ma5"] / daily["ma20"] - 1).clip(lower=0) * 500
            + (daily["amount"] / daily["amount5"] - 1).clip(lower=0, upper=2) * 10
            + daily["pct_chg"].clip(lower=0, upper=5)
        )
        frame.loc[daily.index, calculated] = daily[calculated]

    signals = frame
    signals = signals[
        (signals["trade_date"] >= pd.Timestamp(start))
        & (signals["trade_date"] <= pd.Timestamp(end))
        & signals["signal_type"].ne("")
        & signals["signal_type"].isin(signal_types)
        & signals["future_open"].gt(0)
    ].copy()
    return signals.sort_values(["trade_date", "signal_score"], ascending=[True, False])


def simulate(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    hold_days: int,
    stop_loss: float,
    cost_pct: float,
    top_n: int,
    max_entry_gap: float | None,
) -> list[Trade]:
    panels = {code: group.reset_index(drop=True) for code, group in prices.groupby("code", sort=False)}
    trades: list[Trade] = []
    for _, signal in signals.groupby("trade_date", sort=True):
        for row in signal.head(top_n).itertuples(index=False):
            panel = panels[row.code]
            entry_idx = panel.index[panel["trade_date"].eq(row.future_dates)]
            if len(entry_idx) != 1:
                continue
            entry_idx = int(entry_idx[0])
            exit_idx = entry_idx + hold_days - 1
            if exit_idx >= len(panel):
                continue
            entry = float(row.future_open)
            if max_entry_gap is not None and entry > float(row.close) * (1 + max_entry_gap):
                continue
            stop_price = entry * (1 - stop_loss)
            window = panel.iloc[entry_idx : exit_idx + 1]
            stop_rows = window[window["low"] <= stop_price]
            if not stop_rows.empty:
                stopped = stop_rows.iloc[0]
                exit_price = min(float(stopped["open"]), stop_price)
                exit_date = stopped["trade_date"]
                reason = "止损"
            else:
                final_day = window.iloc[-1]
                exit_price = float(final_day["close"])
                exit_date = final_day["trade_date"]
                reason = "到期"
            gross = (exit_price / entry - 1) * 100
            max_adverse = (window["low"].min() / entry - 1) * 100
            trades.append(
                Trade(
                    code=row.code,
                    signal_date=row.trade_date.strftime("%Y-%m-%d"),
                    entry_date=row.future_dates.strftime("%Y-%m-%d"),
                    exit_date=exit_date.strftime("%Y-%m-%d"),
                    signal_type=row.signal_type,
                    signal_score=round(float(row.signal_score), 2),
                    entry_price=round(entry, 3),
                    exit_price=round(exit_price, 3),
                    exit_reason=reason,
                    gross_return_pct=round(gross, 3),
                    net_return_pct=round(gross - cost_pct, 3),
                    max_adverse_pct=round(max_adverse, 3),
                )
            )
    return trades


def report(trades: list[Trade], args: argparse.Namespace) -> tuple[pd.DataFrame, str]:
    results = pd.DataFrame([asdict(item) for item in trades])
    if results.empty:
        return results, "# 短线交易候选回测\n\n无可验证交易。"
    net = results["net_return_pct"]
    wins = net.gt(0)
    by_type = results.groupby("signal_type")["net_return_pct"].agg(["count", "mean", lambda x: (x > 0).mean()])
    by_type.columns = ["交易数", "平均净收益%", "胜率"]
    lines = [
        "# 短线交易候选回测（机械日线层）",
        "",
        f"- 样本：{args.start} 至 {args.end}，{args.board}；T 日收盘生成信号，T+1 开盘成交。",
        f"- 规则：每个信号日最多前 {args.top_n} 名；最多持有 {args.hold_days} 日；盘中低点触发 {args.stop_loss:.1%} 止损；单边成本 {args.cost_pct / 2:.2f}%。",
        f"- 候选：{'、'.join(sorted(args.signal_types))}；突破量能至少为 5 日均量的 {args.breakout_volume_multiple:.1f} 倍；"
        + (f"次日开盘高开超过 {args.max_entry_gap:.1%} 放弃。" if args.max_entry_gap is not None else "不限制次日高开。"),
        "- 未回测项：题材强度、板块联动、资金流、筹码分布、买五卖五；这些是实盘次日确认门槛，不能由日线替代。",
        "",
        "## 汇总",
        "",
        f"- 交易数：{len(results)}；胜率：{wins.mean():.1%}；平均单笔净收益：{net.mean():.2f}%。",
        f"- 中位数净收益：{net.median():.2f}%；平均盈利：{net[wins].mean():.2f}%；平均亏损：{net[~wins].mean():.2f}%。",
        f"- 止损占比：{results['exit_reason'].eq('止损').mean():.1%}；平均最大不利波动：{results['max_adverse_pct'].mean():.2f}%。",
        "",
        "## 分类型",
        "",
        by_type.assign(胜率=by_type["胜率"].map(lambda value: f"{value:.1%}"), **{"平均净收益%": by_type["平均净收益%"].map(lambda value: f"{value:.2f}")}).to_markdown(),
        "",
        "## 使用边界",
        "",
        "该结果仅用于决定是否保留候选层，不能推导为自动买入或未来收益承诺。实盘仍执行 2%–4% 试错仓、单笔计划最大亏损 500 元、五项盘中确认后才可下单。",
    ]
    return results, "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="短线交易候选的无未来数据回测")
    parser.add_argument("--start", default="2025-01-02")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--board", choices=("main", "kcb", "all"), default="main")
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--stop-loss", type=float, default=0.06)
    parser.add_argument("--cost-pct", type=float, default=0.20, help="往返成本百分比，例如 0.20 表示 0.20%%")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument(
        "--signal-types",
        default="强趋势回踩,突破启动",
        help="逗号分隔，例如 突破启动",
    )
    parser.add_argument("--breakout-volume-multiple", type=float, default=1.0)
    parser.add_argument("--max-entry-gap", type=float, default=None, help="次日允许的最高开盘溢价，例如 0.03")
    args = parser.parse_args()
    if args.hold_days < 1 or args.top_n < 1 or not 0 < args.stop_loss < 0.2:
        raise SystemExit("持有日、候选数和止损参数不合法")

    args.signal_types = {item.strip() for item in args.signal_types.split(",") if item.strip()}
    if not args.signal_types or args.breakout_volume_multiple < 1 or (args.max_entry_gap is not None and args.max_entry_gap < 0):
        raise SystemExit("候选类型、量能或开盘溢价参数不合法")
    prices = load_prices(_mysql_engine(), args.start, args.end, args.board)
    signals = add_signals(
        prices, args.start, args.end,
        signal_types=args.signal_types,
        breakout_volume_multiple=args.breakout_volume_multiple,
    )
    trades = simulate(
        signals, prices, hold_days=args.hold_days, stop_loss=args.stop_loss,
        cost_pct=args.cost_pct, top_n=args.top_n, max_entry_gap=args.max_entry_gap,
    )
    results, markdown = report(trades, args)
    output = REPO / "output"
    output.mkdir(exist_ok=True)
    type_suffix = "-".join(sorted(args.signal_types)).replace("强趋势回踩", "pullback").replace("突破启动", "breakout")
    gap_suffix = "nogap" if args.max_entry_gap is None else f"gap{args.max_entry_gap:.0%}"
    suffix = f"short_term_trade_{args.board}_{args.start.replace('-', '')}_{args.end.replace('-', '')}_{type_suffix}_vol{args.breakout_volume_multiple:g}_{gap_suffix}"
    results.to_csv(output / f"{suffix}.csv", index=False, encoding="utf-8-sig")
    (output / f"{suffix}.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"明细：{output / f'{suffix}.csv'}")


if __name__ == "__main__":
    main()
