from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from scripts.analysis.backtest_limit_up_gene_watch import (
    SignalIntent,
    _gene_evaluator,
    catch_metrics,
    run_backtest,
    trade_return,
)


def _panel() -> pd.DataFrame:
    rows = []
    for index in range(14):
        day = date(2026, 7, 1) + timedelta(days=index)
        rows.append(
            {
                "ts_code": "600000.SH",
                "trade_date": day,
                "open": 10.0 + index * 0.1,
                "high": 10.2 + index * 0.1,
                "low": 9.8 + index * 0.1,
                "close": 10.1 + index * 0.1,
                "pct_chg": 1.0,
                "amount": 100_000,
            }
        )
    return pd.DataFrame(rows)


def _qualified_gene_history() -> pd.DataFrame:
    panel = _panel()
    panel.loc[4, ["open", "high", "low", "close", "pct_chg", "amount"]] = [
        10.4,
        11.44,
        10.4,
        11.44,
        10.0,
        400_000,
    ]
    for index in range(5, 14):
        close = 11.45 + (index - 5) * 0.02
        panel.loc[index, ["open", "high", "low", "close", "pct_chg", "amount"]] = [
            close - 0.02,
            close + 0.15,
            close - 0.15,
            close,
            0.2,
            300_000 - (index - 5) * 18_000,
        ]
    return panel


def test_signal_evaluator_receives_only_rows_through_signal_date() -> None:
    seen: list[tuple[date, date]] = []

    def evaluator(code: str, bars: pd.DataFrame, signal_date: date):
        seen.append((bars["trade_date"].max(), signal_date))
        return (code,) if len(bars) >= 5 else ()

    run_backtest(
        _panel(),
        evaluator=evaluator,
        signal_dates=(date(2026, 7, 5), date(2026, 7, 6)),
        hold_days=5,
    )

    assert seen
    assert all(max_seen <= signal_date for max_seen, signal_date in seen)


def test_round_trip_costs_reduce_return() -> None:
    gross = trade_return(10.0, 11.0, commission_rate=0, slippage_rate=0)
    net = trade_return(10.0, 11.0, commission_rate=0.0008, slippage_rate=0.001)

    assert net < gross
    assert gross == pytest.approx(0.1)


def test_entry_is_next_session_open_and_exit_is_fifth_session_close() -> None:
    trades = run_backtest(
        _panel(),
        evaluator=lambda code, bars, signal_date: (code,),
        signal_dates=(date(2026, 7, 3),),
        hold_days=5,
        commission_rate=0,
        slippage_rate=0,
    )

    assert len(trades) == 1
    assert trades[0].entry_date == date(2026, 7, 4)
    assert trades[0].exit_date == date(2026, 7, 8)


def test_observation_signal_does_not_trade_when_next_session_never_reaches_trigger() -> None:
    trades = run_backtest(
        _panel(),
        evaluator=lambda code, bars, signal_date: {
            code: SignalIntent(score=80, trigger_price=20.0, max_gap_pct=5.0)
        },
        signal_dates=(date(2026, 7, 3),),
        hold_days=5,
        commission_rate=0,
        slippage_rate=0,
    )

    assert trades == []


def test_observation_signal_executes_at_trigger_instead_of_lower_open() -> None:
    trades = run_backtest(
        _panel(),
        evaluator=lambda code, bars, signal_date: {
            code: SignalIntent(score=80, trigger_price=10.4, max_gap_pct=5.0)
        },
        signal_dates=(date(2026, 7, 3),),
        hold_days=5,
        commission_rate=0,
        slippage_rate=0,
    )

    assert len(trades) == 1
    assert trades[0].entry_price == pytest.approx(10.4)


def test_observation_signal_rejects_open_more_than_five_percent_above_trigger() -> None:
    panel = _panel()
    panel.loc[panel["trade_date"] == date(2026, 7, 4), ["open", "high"]] = [
        11.0,
        11.2,
    ]

    trades = run_backtest(
        panel,
        evaluator=lambda code, bars, signal_date: {
            code: SignalIntent(score=80, trigger_price=10.4, max_gap_pct=5.0)
        },
        signal_dates=(date(2026, 7, 3),),
        hold_days=5,
        commission_rate=0,
        slippage_rate=0,
    )

    assert trades == []


def test_triggered_trade_exits_when_stored_invalidation_is_breached() -> None:
    panel = _panel()
    panel.loc[panel["trade_date"] == date(2026, 7, 4), "low"] = 10.3
    panel.loc[panel["trade_date"] == date(2026, 7, 5), "low"] = 10.0

    trades = run_backtest(
        panel,
        evaluator=lambda code, bars, signal_date: {
            code: SignalIntent(
                score=80,
                trigger_price=10.4,
                max_gap_pct=5.0,
                invalidation_price=10.2,
            )
        },
        signal_dates=(date(2026, 7, 3),),
        hold_days=5,
        commission_rate=0,
        slippage_rate=0,
    )

    assert len(trades) == 1
    assert trades[0].exit_date == date(2026, 7, 5)
    assert trades[0].exit_price == pytest.approx(10.2)


def test_gene_evaluator_emits_box_breakout_execution_intent() -> None:
    history = _qualified_gene_history()

    evaluated = _gene_evaluator("600000", history, date(2026, 7, 14))

    assert evaluated == {
        "600000": SignalIntent(
            score=62.0,
            trigger_price=11.74,
            max_gap_pct=5.0,
            invalidation_price=10.4,
        )
    }


def test_daily_cap_keeps_highest_scored_signal() -> None:
    first = _panel()
    second = first.copy()
    second["ts_code"] = "600001.SH"
    panel = pd.concat([first, second], ignore_index=True)

    trades = run_backtest(
        panel,
        evaluator=lambda code, bars, signal_date: {code: 80 if code == "600001" else 60},
        signal_dates=(date(2026, 7, 3),),
        hold_days=5,
        commission_rate=0,
        slippage_rate=0,
        max_signals_per_day=1,
    )

    assert [trade.code for trade in trades] == ["600001"]


def test_daily_cap_is_applied_before_later_breakout_outcome_is_known() -> None:
    first = _panel()
    second = first.copy()
    second["ts_code"] = "600001.SH"
    panel = pd.concat([first, second], ignore_index=True)

    def evaluator(code: str, bars: pd.DataFrame, signal_date: date):
        if code == "600001":
            return {code: SignalIntent(score=80, trigger_price=20.0)}
        return {code: SignalIntent(score=60, trigger_price=10.4)}

    trades = run_backtest(
        panel,
        evaluator=evaluator,
        signal_dates=(date(2026, 7, 3),),
        hold_days=5,
        commission_rate=0,
        slippage_rate=0,
        max_signals_per_day=1,
    )

    assert trades == []


def test_catch_metrics_count_next_day_limit_up() -> None:
    panel = _panel()
    panel.loc[panel["trade_date"] == date(2026, 7, 4), "pct_chg"] = 10.0
    trades = run_backtest(
        panel,
        evaluator=lambda code, bars, signal_date: {code: 80},
        signal_dates=(date(2026, 7, 3),),
        hold_days=5,
    )

    metrics = catch_metrics(trades)

    assert metrics["next_day_limit_up_count"] == 1
    assert metrics["next_day_limit_up_rate"] == 1.0
