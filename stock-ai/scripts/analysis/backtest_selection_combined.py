#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合选股逐日回测：历史某日 T 用截至 T 的数据选股，再用 T 之后真实行情验证。

默认科创板 + board-aware 分板块参数。主板回测加 --board main。输出：
  - CSV：每条信号 + 各持有期收益 + 是否符合预期
  - Markdown：按日逐条验证报告 + 按动作/标签汇总
  - 组合回测：资金曲线、年化收益(CAGR)、最大回撤、资金利用率

用法:
  cd stock-ai
  uv run python scripts/analysis/backtest_selection_combined.py
  uv run python scripts/analysis/backtest_selection_combined.py --start 2023-01-01 --buy-only --tags 空中加油
  uv run python scripts/analysis/backtest_selection_combined.py --board main --start 2023-01-03 --buy-only --tags 空中加油 --sample-every 5
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "core_v2"))

from board_filters import (
    detect_board,
    get_board_params,
    max_signals_for_code,
    passes_base_filter,
    passes_crash_filter,
    sql_universe_clause,
)  # noqa: E402
from combined_selection_engine import evaluate_combined_candidate  # noqa: E402
from market_breadth import compute_daily_breadth, regime_for_date  # noqa: E402
from stock_selection_combined import BUY_ACTIONS  # noqa: E402

load_dotenv(_REPO / ".env")

HISTORY_DAYS = 1100
OBSERVE_ACTION = "继续观察"
INDEX_BY_BOARD = {
    "kcb": ("000688", "科创50"),
    "main": ("000300", "沪深300"),
    "all": ("000300", "沪深300"),
}
DEFAULT_HOLD_DAYS = (1, 5, 10, 20)


@dataclass
class RawSignal:
    trade_date: str
    code: str
    close: float
    action: str
    score: float
    tags: str
    filter_mode: str


@dataclass
class PortfolioTrade:
    code: str
    name: str
    signal_date: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    weight: float
    return_pct: float
    pnl_pct_on_equity: float  # 对组合净值的贡献（%）


@dataclass
class PortfolioResult:
    initial_capital: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    trading_days: int
    calendar_days: int
    executed_trades: int
    skipped_trades: int
    avg_utilization_pct: float
    days_in_market_pct: float
    index_total_return_pct: float | None
    index_cagr_pct: float | None
    equity_curve: pd.DataFrame
    trades: list[PortfolioTrade]


@dataclass
class ValidatedSignal:
    trade_date: str
    code: str
    name: str
    action: str
    tags: str
    score: float
    signal_close: float
    filter_mode: str
    primary_hold: int
    primary_return_pct: float | None = None
    index_return_pct: float | None = None
    verdict: str = "无法验证"
    vs_index: str = "-"
    returns: dict[int, float] = field(default_factory=dict)


def _engine():
    url = os.getenv("MYSQL_URL", "").replace("host.docker.internal", "127.0.0.1")
    return create_engine(url)


def _norm_date(d) -> str:
    if isinstance(d, str):
        return d.replace("-", "")[:8]
    return pd.Timestamp(d).strftime("%Y%m%d")


def _fmt_date(s: str) -> str:
    s = _norm_date(s)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def load_panel(
    engine,
    start: str,
    end: str,
    *,
    board: str = "kcb",
) -> tuple[pd.DataFrame, set[str]]:
    start_dt = datetime.strptime(_norm_date(start), "%Y%m%d")
    hist_start = (start_dt - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    end_sql = _fmt_date(end)

    where_extra = sql_universe_clause(board)

    q = f"""
        SELECT ts_code, trade_date, open, high, low, close, pct_chg, vol, amount
        FROM stock_daily
        WHERE trade_date BETWEEN '{hist_start}' AND '{end_sql}'
          AND {where_extra}
        ORDER BY ts_code, trade_date
    """
    df = pd.read_sql(text(q), engine)
    df["code"] = df["ts_code"].astype(str).str.split(".").str[0].str.zfill(6)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    universe = set(df["code"].unique())
    return df, universe


def load_st_universe(engine) -> set[str]:
    try:
        from scripts.tools.portfolio_db import ensure_market_name_cache, load_st_codes

        ensure_market_name_cache()
        return load_st_codes(engine=engine)
    except Exception:
        return set()


def load_index_series(
    engine, start: str, end: str, *, index_code: str = "000688"
) -> pd.Series:
    """指数收盘价序列，index=YYYYMMDD。"""
    hist_start = (
        datetime.strptime(_norm_date(start), "%Y%m%d") - timedelta(days=30)
    ).strftime("%Y-%m-%d")
    end_sql = _fmt_date(end)
    q = f"""
        SELECT trade_date, close FROM stock_daily
        WHERE (ts_code = '{index_code}' OR ts_code LIKE '{index_code}.%')
          AND trade_date BETWEEN '{hist_start}' AND '{end_sql}'
        ORDER BY trade_date
    """
    idx_df = pd.read_sql(text(q), engine)
    if idx_df.empty:
        return pd.Series(dtype=float)
    idx_df["d"] = idx_df["trade_date"].map(_norm_date)
    s = idx_df.set_index("d")["close"].astype(float)
    return s[~s.index.duplicated(keep="last")]


def build_price_index(df: pd.DataFrame) -> dict[tuple[str, str], dict]:
    idx: dict[tuple[str, str], dict] = {}
    for row in df.itertuples(index=False):
        key = (row.code, _norm_date(row.trade_date))
        idx[key] = {
            "open": float(row.open),
            "close": float(row.close),
        }
    return idx


def forward_return(
    price_idx: dict[tuple[str, str], dict],
    code: str,
    signal_date: str,
    calendar: list[str],
    hold_days: int,
) -> float | None:
    """T 日收盘出信号 → T+1 开盘买 → T+hold_days 收盘卖。"""
    if signal_date not in calendar:
        return None
    i0 = calendar.index(signal_date)
    if i0 + hold_days >= len(calendar):
        return None
    entry_date = calendar[i0 + 1]
    exit_date = calendar[i0 + hold_days]
    entry = price_idx.get((code, entry_date))
    exit_row = price_idx.get((code, exit_date))
    if not entry or not exit_row:
        return None
    buy = entry["open"]
    sell = exit_row["close"]
    if buy <= 0:
        return None
    return (sell / buy - 1.0) * 100.0


def index_forward_return(
    index_close: pd.Series,
    calendar: list[str],
    signal_date: str,
    hold_days: int,
) -> float | None:
    if signal_date not in calendar or index_close.empty:
        return None
    i0 = calendar.index(signal_date)
    if i0 + hold_days >= len(calendar):
        return None
    entry_date = calendar[i0 + 1]
    exit_date = calendar[i0 + hold_days]
    if entry_date not in index_close.index or exit_date not in index_close.index:
        return None
    buy = float(index_close[entry_date])
    sell = float(index_close[exit_date])
    if buy <= 0:
        return None
    return (sell / buy - 1.0) * 100.0


def scan_day_signals(
    grouped: dict[str, pd.DataFrame],
    trade_date: str,
    universe: set[str],
    *,
    legacy_filter: bool,
    include_observe: bool,
    breadth_map: dict[str, float] | None = None,
    skip_weak_market_block: bool = False,
) -> list[RawSignal]:
    mode = "legacy" if legacy_filter else "board-aware"
    td_ts = pd.Timestamp(_fmt_date(trade_date))
    signals: list[RawSignal] = []
    allowed = set(BUY_ACTIONS)
    if include_observe:
        allowed.add(OBSERVE_ACTION)

    for code, full in grouped.items():
        if code not in universe:
            continue
        g = full[full["trade_date"] <= td_ts]
        if len(g) < 60:
            continue
        if _norm_date(g.iloc[-1]["trade_date"]) != _norm_date(trade_date):
            continue

        close = float(g.iloc[-1]["close"])
        amount = float(g.iloc[-1]["amount"])
        pct = float(g.iloc[-1]["pct_chg"])
        if not passes_crash_filter(code, pct, legacy_unified=legacy_filter):
            continue
        if not passes_base_filter(code, close, amount, legacy_unified=legacy_filter):
            continue

        board_regime = (
            regime_for_date(breadth_map or {}, trade_date) if breadth_map else "neutral"
        )

        row = evaluate_combined_candidate(
            g,
            code,
            market_score_adj=0,
            hot_sectors=[],
            market_regime=board_regime,
            holdings_codes=set(),
            account_position_pct=0.0,
            industry_map={},
            advisor_phase=0,
            legacy_unified_filter=legacy_filter,
            skip_advisor=True,
            skip_account_caps=True,
            board_market_regime=board_regime,
            skip_weak_market_block=skip_weak_market_block,
        )
        if not row:
            continue
        action = str(row.get("建议动作") or "")
        if action not in allowed:
            continue
        signals.append(
            RawSignal(
                trade_date=_norm_date(trade_date),
                code=code,
                close=float(row["收盘价"]),
                action=action,
                score=float(row["总分"]),
                tags=str(row.get("策略标签") or ""),
                filter_mode=mode,
            )
        )
    signals.sort(key=lambda s: (-s.score, s.code))
    if not legacy_filter:
        from collections import defaultdict

        by_board: dict = defaultdict(list)
        for s in signals:
            by_board[detect_board(s.code)].append(s)
        capped: list[RawSignal] = []
        for _kind, items in by_board.items():
            items.sort(key=lambda s: (-s.score, s.code))
            cap = max_signals_for_code(items[0].code, legacy_unified=False)
            capped.extend(items if cap is None else items[:cap])
        signals = sorted(capped, key=lambda s: (-s.score, s.code))
    return signals


def validate_signals(
    raw: list[RawSignal],
    *,
    price_idx: dict,
    calendar: list[str],
    hold_days: tuple[int, ...],
    primary_hold: int,
    index_close: pd.Series,
    name_map: dict[str, str],
    win_threshold: float,
) -> list[ValidatedSignal]:
    out: list[ValidatedSignal] = []
    for sig in raw:
        rets: dict[int, float] = {}
        for h in hold_days:
            r = forward_return(price_idx, sig.code, sig.trade_date, calendar, h)
            if r is not None:
                rets[h] = r

        primary = rets.get(primary_hold)
        idx_ret = index_forward_return(index_close, calendar, sig.trade_date, primary_hold)

        if primary is None:
            verdict = "无法验证"
            vs_index = "-"
        elif primary > win_threshold:
            verdict = "符合预期"
            vs_index = (
                "跑赢指数"
                if idx_ret is not None and primary > idx_ret
                else ("跑输指数" if idx_ret is not None else "-")
            )
        else:
            verdict = "不符合"
            vs_index = (
                "跑赢指数"
                if idx_ret is not None and primary > idx_ret
                else ("跑输指数" if idx_ret is not None else "-")
            )

        out.append(
            ValidatedSignal(
                trade_date=sig.trade_date,
                code=sig.code,
                name=name_map.get(sig.code, sig.code),
                action=sig.action,
                tags=sig.tags,
                score=sig.score,
                signal_close=sig.close,
                filter_mode=sig.filter_mode,
                primary_hold=primary_hold,
                primary_return_pct=primary,
                index_return_pct=idx_ret,
                verdict=verdict,
                vs_index=vs_index,
                returns=rets,
            )
        )
    return out


def _calendar_days_between(start: str, end: str) -> int:
    d0 = datetime.strptime(_norm_date(start), "%Y%m%d")
    d1 = datetime.strptime(_norm_date(end), "%Y%m%d")
    return max((d1 - d0).days, 1)


def _cagr_pct(initial: float, final: float, calendar_days: int) -> float:
    if calendar_days <= 0 or initial <= 0 or final <= 0:
        return 0.0
    years = calendar_days / 365.25
    return (pow(final / initial, 1.0 / years) - 1.0) * 100.0


def _max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min() * 100.0)


def _daily_sharpe(daily_returns: pd.Series) -> float | None:
    if len(daily_returns) < 2:
        return None
    std = float(daily_returns.std())
    if std <= 0:
        return None
    return float(daily_returns.mean() / std * (252**0.5))


def simulate_portfolio(
    validated: list[ValidatedSignal],
    *,
    calendar: list[str],
    price_idx: dict[tuple[str, str], dict],
    index_close: pd.Series,
    primary_hold: int,
    position_pct: float,
    max_positions: int,
    initial_capital: float,
    backtest_start: str,
    backtest_end: str,
) -> PortfolioResult | None:
    """
    组合级回测：固定仓位比例、持仓上限、允许重叠；按日盯市。
    入场：T+1 开盘；出场：T+hold 收盘。
    """
    if not calendar:
        return None

    pending: list[tuple[int, ValidatedSignal, str, str]] = []
    for v in validated:
        if v.primary_return_pct is None:
            continue
        if v.trade_date not in calendar:
            continue
        i0 = calendar.index(v.trade_date)
        if i0 + primary_hold >= len(calendar):
            continue
        entry_d = calendar[i0 + 1]
        exit_d = calendar[i0 + primary_hold]
        ep = price_idx.get((v.code, entry_d), {}).get("open")
        xp = price_idx.get((v.code, exit_d), {}).get("close")
        if not ep or not xp or ep <= 0:
            continue
        pending.append((i0, v, entry_d, exit_d))

    pending.sort(key=lambda x: (x[2], -x[1].score, x[1].code))
    entries_by_date: dict[str, list[tuple[ValidatedSignal, str, str]]] = defaultdict(list)
    for _, v, entry_d, exit_d in pending:
        entries_by_date[entry_d].append((v, entry_d, exit_d))

    cash = float(initial_capital)
    open_positions: list[dict] = []
    executed: list[PortfolioTrade] = []
    skipped = 0

    curve_rows: list[dict] = []
    bt_start = _norm_date(backtest_start)
    bt_end = _norm_date(backtest_end)
    sim_calendar = [d for d in calendar if bt_start <= d <= bt_end]

    for d in sim_calendar:
        # 开盘：新仓
        for v, entry_d, exit_d in entries_by_date.get(d, []):
            if len(open_positions) >= max_positions:
                skipped += 1
                continue
            open_px = price_idx.get((v.code, entry_d), {}).get("open")
            if not open_px or open_px <= 0:
                skipped += 1
                continue
            mtm = sum(
                p["shares"] * price_idx.get((p["code"], d), {}).get("close", p["entry_price"])
                for p in open_positions
            )
            equity_now = cash + mtm
            alloc = equity_now * position_pct
            if alloc <= 0 or alloc > cash:
                if cash < equity_now * position_pct * 0.5:
                    skipped += 1
                    continue
                alloc = min(cash, equity_now * position_pct)
            shares = alloc / open_px
            cost = shares * open_px
            cash -= cost
            open_positions.append(
                {
                    "code": v.code,
                    "name": v.name,
                    "signal_date": v.trade_date,
                    "entry_date": entry_d,
                    "exit_date": exit_d,
                    "entry_price": open_px,
                    "shares": shares,
                    "weight": position_pct,
                    "cost": cost,
                }
            )

        # 收盘：盯市 + 平仓
        pos_value = 0.0
        for p in open_positions:
            close_px = price_idx.get((p["code"], d), {}).get("close", p["entry_price"])
            pos_value += p["shares"] * close_px

        equity = cash + pos_value

        still_open = []
        for p in open_positions:
            if p["exit_date"] == d:
                close_px = price_idx.get((p["code"], d), {}).get("close", p["entry_price"])
                proceeds = p["shares"] * close_px
                cash += proceeds
                ret_pct = (close_px / p["entry_price"] - 1.0) * 100.0
                pnl_on_equity = (proceeds - p["cost"]) / initial_capital * 100.0
                executed.append(
                    PortfolioTrade(
                        code=p["code"],
                        name=p["name"],
                        signal_date=p["signal_date"],
                        entry_date=p["entry_date"],
                        exit_date=p["exit_date"],
                        entry_price=p["entry_price"],
                        exit_price=close_px,
                        weight=p["weight"],
                        return_pct=ret_pct,
                        pnl_pct_on_equity=pnl_on_equity,
                    )
                )
            else:
                still_open.append(p)
        open_positions = still_open

        pos_value_end = sum(
            p["shares"] * price_idx.get((p["code"], d), {}).get("close", p["entry_price"])
            for p in open_positions
        )
        equity_end = cash + pos_value_end
        util = pos_value_end / equity_end * 100.0 if equity_end > 0 else 0.0
        curve_rows.append(
            {
                "date": _fmt_date(d),
                "equity": equity_end,
                "cash": cash,
                "position_value": pos_value_end,
                "utilization_pct": util,
                "open_positions": len(open_positions),
            }
        )

    equity_df = pd.DataFrame(curve_rows)
    if equity_df.empty:
        return None

    final_equity = float(equity_df["equity"].iloc[-1])
    cal_days = _calendar_days_between(bt_start, bt_end)
    total_ret = (final_equity / initial_capital - 1.0) * 100.0
    cagr = _cagr_pct(initial_capital, final_equity, cal_days)

    eq_series = equity_df["equity"]
    daily_ret = eq_series.pct_change().dropna()
    mdd = _max_drawdown_pct(eq_series)
    sharpe = _daily_sharpe(daily_ret)

    avg_util = float(equity_df["utilization_pct"].mean())
    days_in_mkt = float((equity_df["open_positions"] > 0).mean() * 100.0)

    idx_total = idx_cagr = None
    idx_days = [d for d in sim_calendar if d in index_close.index]
    if len(idx_days) >= 2:
        i0 = float(index_close[idx_days[0]])
        i1 = float(index_close[idx_days[-1]])
        if i0 > 0:
            idx_total = (i1 / i0 - 1.0) * 100.0
            idx_cagr = _cagr_pct(i0, i1, cal_days)

    return PortfolioResult(
        initial_capital=initial_capital,
        final_equity=final_equity,
        total_return_pct=total_ret,
        cagr_pct=cagr,
        max_drawdown_pct=mdd,
        sharpe_ratio=sharpe,
        trading_days=len(sim_calendar),
        calendar_days=cal_days,
        executed_trades=len(executed),
        skipped_trades=skipped,
        avg_utilization_pct=avg_util,
        days_in_market_pct=days_in_mkt,
        index_total_return_pct=idx_total,
        index_cagr_pct=idx_cagr,
        equity_curve=equity_df,
        trades=executed,
    )


def write_portfolio_markdown(
    path: Path, pf: PortfolioResult, *, primary_hold: int, index_label: str = "科创50"
) -> None:
    lines = [
        "# 组合回测报告",
        "",
        f"- 初始资金: {pf.initial_capital:,.0f}",
        f"- 期末净值: {pf.final_equity:,.0f}",
        f"- **累计收益**: {pf.total_return_pct:+.2f}%",
        f"- **年化收益 (CAGR)**: {pf.cagr_pct:+.2f}%",
        f"- 最大回撤: {pf.max_drawdown_pct:.2f}%",
        f"- 夏普比率: {pf.sharpe_ratio:.2f}" if pf.sharpe_ratio is not None else "- 夏普比率: N/A",
        f"- 回测日历天数: {pf.calendar_days}（交易日 {pf.trading_days}）",
        f"- 执行交易: {pf.executed_trades} 笔，跳过（仓位满）: {pf.skipped_trades} 笔",
        f"- 平均资金利用率: {pf.avg_utilization_pct:.1f}%",
        f"- 持仓天数占比: {pf.days_in_market_pct:.1f}%",
        "",
    ]
    if pf.index_total_return_pct is not None:
        lines.extend(
            [
                f"## 基准对比（{index_label} 买入持有）",
                "",
                f"- 累计收益: {pf.index_total_return_pct:+.2f}%",
                f"- 年化 (CAGR): {pf.index_cagr_pct:+.2f}%"
                if pf.index_cagr_pct is not None
                else "",
                f"- 超额年化: {pf.cagr_pct - (pf.index_cagr_pct or 0):+.2f}%",
                "",
            ]
        )
    lines.extend(
        [
            "## 说明",
            "",
            f"- 每笔信号分配净值 {pf.trades[0].weight*100:.0f}% 仓位（首笔），"
            f"持有 {primary_hold} 个交易日（T+1 开 → T+{primary_hold} 收）"
            if pf.trades
            else "- 无成交",
            "- 允许持仓重叠；仓位满时跳过新信号",
            "- 空仓期现金无收益",
            "",
        ]
    )
    if pf.trades:
        lines.append("## 成交明细")
        lines.append("")
        lines.append("| 信号日 | 代码 | 名称 | 入场 | 出场 | 仓位 | 个股收益 | 组合贡献 |")
        lines.append("|--------|------|------|------|------|------|----------|----------|")
        for t in pf.trades:
            lines.append(
                f"| {_fmt_date(t.signal_date)} | {t.code} | {t.name} | "
                f"{_fmt_date(t.entry_date)} | {_fmt_date(t.exit_date)} | "
                f"{t.weight*100:.0f}% | {t.return_pct:+.2f}% | {t.pnl_pct_on_equity:+.2f}% |"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def print_portfolio_summary(pf: PortfolioResult, *, index_label: str = "科创50") -> None:
    print("\n" + "=" * 60)
    print("组合回测（含仓位管理与资金曲线）")
    print("=" * 60)
    print(f"  初始 {pf.initial_capital:,.0f} → 期末 {pf.final_equity:,.0f}")
    print(f"  累计收益 {pf.total_return_pct:+.2f}%  |  **年化 CAGR {pf.cagr_pct:+.2f}%**")
    print(f"  最大回撤 {pf.max_drawdown_pct:.2f}%  |  夏普 {pf.sharpe_ratio or 0:.2f}")
    print(
        f"  成交 {pf.executed_trades} 笔（跳过 {pf.skipped_trades}）| "
        f"资金利用率均值 {pf.avg_utilization_pct:.1f}% | 持仓天占比 {pf.days_in_market_pct:.1f}%"
    )
    if pf.index_cagr_pct is not None:
        alpha = pf.cagr_pct - pf.index_cagr_pct
        print(
            f"  {index_label} 买入持有：累计 {pf.index_total_return_pct:+.2f}% | "
            f"年化 {pf.index_cagr_pct:+.2f}% | 超额年化 {alpha:+.2f}%"
        )


def validated_to_rows(v: ValidatedSignal, *, index_label: str = "科创50") -> dict:
    row = {
        "信号日": _fmt_date(v.trade_date),
        "代码": v.code,
        "名称": v.name,
        "建议动作": v.action,
        "策略标签": v.tags,
        "总分": v.score,
        "信号日收盘": v.signal_close,
        "过滤模式": v.filter_mode,
        f"{v.primary_hold}日收益%": v.primary_return_pct,
        f"{index_label}同期%": v.index_return_pct,
        "验证结论": v.verdict,
        "相对指数": v.vs_index,
    }
    for h, r in sorted(v.returns.items()):
        if h != v.primary_hold:
            row[f"{h}日收益%"] = r
    return row


def write_daily_markdown(
    path: Path,
    by_date: dict[str, list[ValidatedSignal]],
    primary_hold: int,
    *,
    index_label: str = "科创50",
) -> None:
    lines = [
        "# 综合选股逐日验证报告",
        "",
        f"主验证持有期：**T+1 开盘买入 → T+{primary_hold} 收盘卖出**",
        "",
    ]
    for td in sorted(by_date.keys(), reverse=True):
        items = by_date[td]
        lines.append(f"## {_fmt_date(td)}（{len(items)} 只信号）")
        lines.append("")
        if not items:
            lines.append("- 当日无信号")
            lines.append("")
            continue
        for v in items:
            ret_s = (
                f"{v.primary_return_pct:+.2f}%"
                if v.primary_return_pct is not None
                else "N/A"
            )
            idx_s = (
                f"{v.index_return_pct:+.2f}%"
                if v.index_return_pct is not None
                else "N/A"
            )
            lines.append(
                f"- **{v.code} {v.name}** | {v.action} | {v.tags or '无标签'} | 总分 {v.score:.1f}"
            )
            lines.append(
                f"  - {primary_hold}日后 **{ret_s}** | {index_label} {idx_s} | "
                f"**{v.verdict}** | {v.vs_index}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary_markdown(
    path: Path,
    validated: list[ValidatedSignal],
    primary_hold: int,
    *,
    filter_mode: str,
    pool_note: str = "",
) -> None:
    verifiable = [v for v in validated if v.primary_return_pct is not None]
    wins = [v for v in verifiable if v.verdict == "符合预期"]

    lines = [
        "# 综合选股回测汇总",
        "",
        f"- 过滤模式: {filter_mode}",
        f"- 主持有期: {primary_hold} 个交易日",
        f"- 信号总数: {len(validated)}",
        f"- 可验证: {len(verifiable)}",
        f"- 符合预期: {len(wins)}（胜率 {len(wins)/len(verifiable)*100:.1f}%）"
        if verifiable
        else "- 符合预期: 0",
        "",
    ]
    if pool_note:
        lines.append(pool_note)
        lines.append("")

    if verifiable:
        rets = pd.Series([v.primary_return_pct for v in verifiable])
        lines.extend(
            [
                "## 收益分布",
                "",
                f"- 平均收益: {rets.mean():+.2f}%",
                f"- 中位数: {rets.median():+.2f}%",
                f"- 最大: {rets.max():+.2f}%",
                f"- 最小: {rets.min():+.2f}%",
                "",
            ]
        )

    def _group_table(key_fn, title: str) -> None:
        buckets: dict[str, list[float]] = defaultdict(list)
        bucket_n: dict[str, int] = defaultdict(int)
        bucket_win: dict[str, int] = defaultdict(int)
        for v in verifiable:
            k = key_fn(v)
            bucket_n[k] += 1
            if v.primary_return_pct is not None:
                buckets[k].append(v.primary_return_pct)
            if v.verdict == "符合预期":
                bucket_win[k] += 1
        if not bucket_n:
            return
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| 分组 | 信号数 | 胜率 | 均收益 |")
        lines.append("|------|--------|------|--------|")
        for k in sorted(bucket_n.keys(), key=lambda x: (-bucket_n[x], x)):
            n = bucket_n[k]
            wr = bucket_win[k] / n * 100 if n else 0
            avg = sum(buckets[k]) / len(buckets[k]) if buckets[k] else 0
            lines.append(f"| {k} | {n} | {wr:.1f}% | {avg:+.2f}% |")
        lines.append("")

    _group_table(lambda v: v.action, "按建议动作")
    tag_returns: dict[str, list[float]] = defaultdict(list)
    tag_win: dict[str, int] = defaultdict(int)
    tag_n: dict[str, int] = defaultdict(int)
    for v in verifiable:
        tags = [t.strip() for t in v.tags.split(",") if t.strip()]
        if not tags:
            tags = ["无标签"]
        for t in tags:
            tag_n[t] += 1
            if v.primary_return_pct is not None:
                tag_returns[t].append(v.primary_return_pct)
            if v.verdict == "符合预期":
                tag_win[t] += 1
    if tag_n:
        lines.append("## 按策略标签")
        lines.append("")
        lines.append("| 标签 | 信号数 | 胜率 | 均收益 |")
        lines.append("|------|--------|------|--------|")
        for t in sorted(tag_n.keys(), key=lambda x: (-tag_n[x], x)):
            n = tag_n[t]
            wr = tag_win[t] / n * 100
            avg = sum(tag_returns[t]) / len(tag_returns[t]) if tag_returns[t] else 0
            lines.append(f"| {t} | {n} | {wr:.1f}% | {avg:+.2f}% |")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def print_console_sample(
    validated: list[ValidatedSignal],
    primary_hold: int,
    *,
    max_days: int = 5,
) -> None:
    by_date: dict[str, list[ValidatedSignal]] = defaultdict(list)
    for v in validated:
        by_date[v.trade_date].append(v)

    print("\n" + "=" * 60)
    print("逐日验证（最近有信号的交易日，最多展示 {} 天）".format(max_days))
    print("=" * 60)

    shown = 0
    for td in sorted(by_date.keys(), reverse=True):
        if shown >= max_days:
            break
        items = by_date[td]
        if not items:
            continue
        print(f"\n## {_fmt_date(td)}（{len(items)} 只）")
        for v in items[:8]:
            ret_s = (
                f"{v.primary_return_pct:+.2f}%"
                if v.primary_return_pct is not None
                else "N/A"
            )
            print(
                f"  {v.code} {v.name} | {v.action} | {v.tags} | "
                f"{primary_hold}日后 {ret_s} | {v.verdict}"
            )
        if len(items) > 8:
            print(f"  … 另有 {len(items) - 8} 只，见 CSV/Markdown")
        shown += 1

    verifiable = [v for v in validated if v.primary_return_pct is not None]
    if verifiable:
        wins = sum(1 for v in verifiable if v.verdict == "符合预期")
        avg = sum(v.primary_return_pct for v in verifiable) / len(verifiable)
        print(
            f"\n单笔信号: 可验证 {len(verifiable)} 条，胜率 {wins/len(verifiable)*100:.1f}%，"
            f"均收益 {avg:+.2f}%（{primary_hold}日持有，非年化）"
        )
    else:
        print("\n汇总: 区间内无足够未来数据可验证（缩短 end 日期或减小 primary-hold）")


def run_backtest(args) -> None:
    hold_days = tuple(int(x) for x in args.hold_days.split(",") if x.strip())
    primary_hold = args.primary_hold
    if primary_hold not in hold_days:
        hold_days = tuple(sorted(set(hold_days) | {primary_hold}))

    engine = _engine()
    if not args.end:
        with engine.connect() as conn:
            args.end = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).scalar()
    end_norm = _norm_date(args.end)
    start_norm = _norm_date(args.start)

    board = "all" if args.all_market else args.board.lower()
    index_code, index_label = INDEX_BY_BOARD.get(board, INDEX_BY_BOARD["kcb"])
    board_labels = {"kcb": "科创板", "main": "主板", "all": "全市场"}

    print(f"加载数据 [{board_labels.get(board, board)}] {_fmt_date(start_norm)} ~ {_fmt_date(end_norm)} …")
    df, universe = load_panel(engine, start_norm, end_norm, board=board)
    if args.exclude_st:
        st_codes = load_st_universe(engine)
        if st_codes:
            before = len(universe)
            universe = {c for c in universe if c not in st_codes}
            df = df[df["code"].isin(universe)].reset_index(drop=True)
            print(f"  ST 剔除 {before - len(universe)} 只，剩余 {len(universe)} 只")
    grouped = {
        str(c): g.sort_values("trade_date").reset_index(drop=True)
        for c, g in df.groupby("code")
    }

    cal_df = df[
        (df["trade_date"] >= pd.Timestamp(start_norm))
        & (df["trade_date"] <= pd.Timestamp(end_norm))
    ]
    calendar = sorted({_norm_date(d) for d in cal_df["trade_date"].unique()})
    price_idx = build_price_index(df)
    index_close = load_index_series(engine, start_norm, end_norm, index_code=index_code)
    breadth_map = compute_daily_breadth(df, board_kind=board if board in {"kcb", "main"} else None)
    weak_days = sum(1 for r in breadth_map.values() if r < 0.45)
    neutral_days = sum(1 for r in breadth_map.values() if 0.45 <= r <= 0.60)
    strong_days = sum(1 for r in breadth_map.values() if r > 0.60)
    print(
        f"  标的 {len(universe)} 只，交易日 {len(calendar)} 天，"
        f"强势 {strong_days} / 震荡 {neutral_days} / 弱势 {weak_days}"
    )

    if args.allow_neutral or args.no_weak_filter:
        import board_filters as bf
        from dataclasses import replace

        if board in ("kcb", "all"):
            kcb = replace(
                bf.KCB_BOARD,
                block_on_neutral_market=False if args.allow_neutral else bf.KCB_BOARD.block_on_neutral_market,
                block_on_weak_market=False if args.no_weak_filter else bf.KCB_BOARD.block_on_weak_market,
            )
            bf.KCB_BOARD = kcb
            bf._BOARD_MAP[bf.BoardKind.KCB] = kcb
        if board in ("main", "all"):
            main = replace(
                bf.MAIN_BOARD,
                block_on_neutral_market=False if args.allow_neutral else bf.MAIN_BOARD.block_on_neutral_market,
                block_on_weak_market=False if args.no_weak_filter else bf.MAIN_BOARD.block_on_weak_market,
            )
            bf.MAIN_BOARD = main
            bf._BOARD_MAP[bf.BoardKind.MAIN] = main
        if args.allow_neutral:
            print("  已开启震荡市开仓（--allow-neutral）")
        if args.no_weak_filter:
            print("  已关闭弱势过滤（--no-weak-filter）")

    if args.date:
        scan_dates = [_norm_date(args.date)]
    else:
        step = max(1, args.sample_every)
        scan_dates = calendar[::step]

    modes = []
    if args.compare_legacy:
        modes = [("legacy", True), ("board-aware", False)]
    else:
        modes = [("board-aware", False)]

    out_dir = _REPO / "output" / "backtest"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{start_norm}_{end_norm}"
    if args.date:
        tag = _norm_date(args.date)

    for mode_name, legacy in modes:
        print(f"\n扫描 [{mode_name}]，{len(scan_dates)} 个交易日…")
        raw_all: list[RawSignal] = []
        for i, td in enumerate(scan_dates):
            raw_all.extend(
                scan_day_signals(
                    grouped,
                    td,
                    universe,
                    legacy_filter=legacy,
                    include_observe=args.include_observe,
                    breadth_map=breadth_map,
                    skip_weak_market_block=args.no_weak_filter,
                )
            )
            if (i + 1) % 25 == 0:
                print(f"  已处理 {i + 1}/{len(scan_dates)} 天，累计信号 {len(raw_all)}")

        codes_needed = sorted({s.code for s in raw_all})
        name_map: dict[str, str] = {c: c for c in codes_needed}
        if codes_needed and os.getenv("SKIP_BACKTEST_NAME_LOOKUP", "").lower() not in {
            "1",
            "true",
            "yes",
        }:
            try:
                from scripts.tools.portfolio_db import load_stock_names_by_codes

                name_map = load_stock_names_by_codes(codes_needed) or name_map
            except Exception:
                pass

        validated = validate_signals(
            raw_all,
            price_idx=price_idx,
            calendar=calendar,
            hold_days=hold_days,
            primary_hold=primary_hold,
            index_close=index_close,
            name_map=name_map,
            win_threshold=args.win_threshold,
        )
        if args.tags:
            tag_set = {t.strip() for t in args.tags.split(",") if t.strip()}
            validated = [
                v
                for v in validated
                if any(t in v.tags for t in tag_set)
            ]
        if args.min_score is not None:
            validated = [v for v in validated if v.score >= args.min_score]
        if args.max_score is not None:
            validated = [v for v in validated if v.score <= args.max_score]
        if args.buy_only:
            validated = [v for v in validated if v.action in BUY_ACTIONS]

        by_date: dict[str, list[ValidatedSignal]] = defaultdict(list)
        for v in validated:
            by_date[v.trade_date].append(v)

        mode_tag = f"{tag}_{board}_{mode_name.replace('-', '_')}"
        csv_path = out_dir / f"selection_backtest_{mode_tag}.csv"
        daily_md = out_dir / f"selection_backtest_daily_{mode_tag}.md"
        summary_md = out_dir / f"selection_backtest_summary_{mode_tag}.md"

        if validated:
            rows = [validated_to_rows(v, index_label=index_label) for v in validated]
            pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
        write_daily_markdown(daily_md, by_date, primary_hold, index_label=index_label)
        write_summary_markdown(
            summary_md,
            validated,
            primary_hold,
            filter_mode=mode_name,
            pool_note=f"标的池：{board_labels.get(board, board)}",
        )

        pf: PortfolioResult | None = None
        if not args.no_portfolio and validated:
            pf = simulate_portfolio(
                validated,
                calendar=calendar,
                price_idx=price_idx,
                index_close=index_close,
                primary_hold=primary_hold,
                position_pct=args.position_pct,
                max_positions=args.max_positions,
                initial_capital=args.initial_capital,
                backtest_start=start_norm,
                backtest_end=end_norm,
            )
            if pf:
                pf_csv = out_dir / f"selection_equity_curve_{mode_tag}.csv"
                pf_md = out_dir / f"selection_portfolio_{mode_tag}.md"
                pf.equity_curve.to_csv(pf_csv, index=False, encoding="utf-8-sig")
                write_portfolio_markdown(
                    pf_md, pf, primary_hold=primary_hold, index_label=index_label
                )
                if pf.trades:
                    pd.DataFrame([asdict(t) for t in pf.trades]).to_csv(
                        out_dir / f"selection_portfolio_trades_{mode_tag}.csv",
                        index=False,
                        encoding="utf-8-sig",
                    )
                print_portfolio_summary(pf, index_label=index_label)

        print_console_sample(validated, primary_hold, max_days=args.show_days)
        print(f"\n输出:")
        print(f"  CSV: {csv_path}")
        print(f"  逐日报告: {daily_md}")
        print(f"  汇总: {summary_md}")
        if pf:
            print(f"  资金曲线: {pf_csv}")
            print(f"  组合报告: {pf_md}")


def main():
    parser = argparse.ArgumentParser(
        description="综合选股逐日回测：历史某日选股，用后续真实行情验证"
    )
    parser.add_argument("--start", default="2023-01-03", help="回测起始（含）")
    parser.add_argument("--end", default=None, help="回测结束（含），默认 MySQL 最新日")
    parser.add_argument("--date", default=None, help="仅验证单个交易日（YYYY-MM-DD）")
    parser.add_argument("--sample-every", type=int, default=1, help="每 N 个交易日扫描一次（默认每日）")
    parser.add_argument(
        "--hold-days",
        default="1,5,10,20",
        help="附加持有期（逗号分隔），均写入 CSV",
    )
    parser.add_argument(
        "--primary-hold",
        type=int,
        default=5,
        help="主验证持有期（用于「符合预期」判定与报告标题）",
    )
    parser.add_argument(
        "--win-threshold",
        type=float,
        default=0.0,
        help="primary-hold 收益 > 此值（%%）视为符合预期",
    )
    parser.add_argument(
        "--include-observe",
        action="store_true",
        default=True,
        help="纳入「继续观察」信号（默认开启）",
    )
    parser.add_argument(
        "--no-include-observe",
        action="store_false",
        dest="include_observe",
        help="仅统计买入类动作",
    )
    parser.add_argument(
        "--compare-legacy",
        action="store_true",
        help="同时跑 legacy（5-20 元）与 board-aware 对照",
    )
    parser.add_argument(
        "--board",
        choices=["kcb", "main", "all"],
        default="kcb",
        help="标的池：kcb 科创板 / main 沪深主板 / all 全市场",
    )
    parser.add_argument(
        "--all-market",
        action="store_true",
        help="同 --board all",
    )
    parser.add_argument(
        "--exclude-st",
        action="store_true",
        default=True,
        help="剔除 ST（默认开启，主板推荐）",
    )
    parser.add_argument(
        "--no-exclude-st",
        action="store_false",
        dest="exclude_st",
        help="不剔除 ST",
    )
    parser.add_argument(
        "--no-weak-filter",
        action="store_true",
        help="关闭弱势过滤（涨跌比<45%）；不关闭震荡市过滤",
    )
    parser.add_argument(
        "--allow-neutral",
        action="store_true",
        help="允许震荡市开仓（默认仅强势市：涨跌比>60%）",
    )
    parser.add_argument(
        "--buy-only",
        action="store_true",
        help="仅统计买入类动作（强势关注/观察买入/小仓埋伏）",
    )
    parser.add_argument("--min-score", type=float, default=None, help="信号总分下限（回测后过滤）")
    parser.add_argument("--max-score", type=float, default=None, help="信号总分上限（回测后过滤）")
    parser.add_argument(
        "--tags",
        default=None,
        help="仅保留含指定标签的信号，逗号分隔，如：空中加油",
    )
    parser.add_argument("--show-days", type=int, default=5, help="控制台展示最近 N 个有信号日")
    parser.add_argument(
        "--position-pct",
        type=float,
        default=0.20,
        help="每笔信号占用净值比例（默认 20%%）",
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=5,
        help="最大同时持仓数",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100_000.0,
        help="初始资金（元）",
    )
    parser.add_argument(
        "--no-portfolio",
        action="store_true",
        help="跳过组合级资金曲线/年化回测",
    )
    args = parser.parse_args()
    run_backtest(args)


if __name__ == "__main__":
    main()
