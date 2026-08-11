#!/usr/bin/env python3
"""No-lookahead backtest that calls the production short-term selector."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Literal, Mapping, Sequence

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6
from stock_ai.relative_strength import (
    ClosePair,
    RelativeStrengthSnapshot,
    build_relative_strength_snapshot,
)
from stock_ai.selection_validation import (
    BacktestMetrics,
    PromotionDecision,
    ValidationArtifact,
    ValidationError,
    choose_validation_profile,
    chronological_splits,
    evaluate_promotion,
    write_validation_artifact,
)
from stock_ai.short_term_selection import (
    BASELINE_POLICY,
    STRICT_A,
    STRICT_B,
    STRICT_C,
    SelectionBar,
    SelectionPolicy,
    SelectionResult,
    select_short_term_candidates,
)
from stock_ai.technical_execution import (
    PortfolioBacktestResult,
    ProxyOpportunity,
    build_proxy_plan,
    simulate_proxy_portfolio,
)
from stock_ai.technical_indicators import (
    IndicatorInputError,
    TechnicalIndicatorSnapshot,
    compute_technical_indicators,
)


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


POLICIES: tuple[SelectionPolicy, ...] = (
    BASELINE_POLICY,
    STRICT_A,
    STRICT_B,
    STRICT_C,
)


@dataclass(frozen=True)
class OpportunityBuild:
    opportunities: Mapping[str, tuple[ProxyOpportunity, ...]]
    rejection_counts: Mapping[str, Mapping[str, int]]
    signal_dates: tuple[date, ...]


@dataclass(frozen=True)
class ResearchOutcome:
    payload: dict[str, object]
    artifact: ValidationArtifact


def _prepare_research_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"trade_date", "open", "high", "low", "close", "amount"}
    missing = required - set(frame.columns)
    if missing:
        raise ValidationError(f"missing price columns: {','.join(sorted(missing))}")
    normalized = frame.copy()
    if "ts_code" not in normalized:
        normalized["ts_code"] = normalized.get("code", "")
    normalized["code"] = normalized["ts_code"].astype(str).map(normalize_code6)
    normalized = normalized[normalized["code"].map(is_sh_sz_main_board_code)].copy()
    normalized["trade_date"] = pd.to_datetime(
        normalized["trade_date"], errors="coerce"
    ).dt.date
    numeric = ["open", "high", "low", "close", "amount"]
    if "pct_chg" not in normalized:
        normalized["pct_chg"] = 0.0
    numeric.append("pct_chg")
    normalized[numeric] = normalized[numeric].apply(pd.to_numeric, errors="coerce")
    normalized = normalized.dropna(subset=["trade_date", *numeric])
    normalized = normalized[
        (normalized["close"] > 0)
        & (normalized["amount"] >= 0)
        & (normalized["high"] >= normalized["low"])
    ].copy()
    normalized["has_suffix"] = normalized["ts_code"].astype(str).str.contains(
        ".", regex=False
    )
    normalized = normalized.sort_values(
        ["code", "trade_date", "has_suffix", "ts_code"]
    ).drop_duplicates(["code", "trade_date"], keep="last")
    if "name" not in normalized:
        normalized["name"] = normalized["code"]
    if "sector" not in normalized:
        normalized["sector"] = normalized["code"]
    return normalized.sort_values(["code", "trade_date"]).reset_index(drop=True)


def build_cross_section_snapshots(
    frame: pd.DataFrame,
) -> dict[date, RelativeStrengthSnapshot]:
    """Build each date's 20-session rank from the entire normalized universe."""

    normalized = _prepare_research_frame(frame)
    market_dates = tuple(sorted(set(normalized["trade_date"])))
    closes_by_date = {
        current_date: {
            row.code: float(row.close)
            for row in group.itertuples(index=False)
        }
        for current_date, group in normalized.groupby("trade_date", sort=True)
    }
    snapshots: dict[date, RelativeStrengthSnapshot] = {}
    for date_index, current_date in enumerate(market_dates):
        if date_index < 20:
            continue
        prior_trade_date = market_dates[date_index - 20]
        current_closes = closes_by_date[current_date]
        prior_closes = closes_by_date[prior_trade_date]
        pairs = tuple(
            ClosePair(code, prior_closes[code], current_close)
            for code, current_close in current_closes.items()
            if code in prior_closes
        )
        snapshots[current_date] = build_relative_strength_snapshot(
            current_trade_date=current_date,
            current_count=len(current_closes),
            prior_trade_date=prior_trade_date,
            pairs=pairs,
        )
    return snapshots


def _selection_bars(records: Sequence[Mapping[str, object]]) -> tuple[SelectionBar, ...]:
    return tuple(
        SelectionBar(
            trade_date=value["trade_date"],
            open=float(value["open"]),
            high=float(value["high"]),
            low=float(value["low"]),
            close=float(value["close"]),
            pct_chg=float(value["pct_chg"]),
            amount_qian=float(value["amount"]),
        )
        for value in records
    )


def build_policy_opportunities(
    frame: pd.DataFrame,
    *,
    start: date,
    end: date,
    top_n: int = 5,
) -> OpportunityBuild:
    """Classify all policies with one indicator calculation per code and date."""

    normalized = _prepare_research_frame(frame)
    grouped = normalized.groupby("code", sort=False)
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
        lambda values: values / values.shift(10) - 1.0
    )
    normalized["recent_high10"] = grouped["high"].transform(
        lambda values: values.rolling(10).max()
    )
    trend = (normalized["ma5"] > normalized["ma10"]) & (
        normalized["ma10"] > normalized["ma20"]
    )
    liquid = normalized["prior_amount5"] >= 100_000
    breakout_possible = (
        (normalized["close"] > normalized["prior_high20"])
        & normalized["pct_chg"].between(0, 7)
    )
    pullback_possible = (
        normalized["return10"].between(0.05, 0.25)
        & (normalized["close"] >= normalized["ma10"])
        & (normalized["close"] <= normalized["ma5"] * 1.02)
        & (normalized["amount"] <= normalized["prior_amount5"] * 1.2)
        & (
            (normalized["recent_high10"] - normalized["close"])
            / normalized["recent_high10"]
        ).between(0.02, 0.10)
    )
    normalized["prefilter"] = trend & liquid & (breakout_possible | pullback_possible)

    panel_records: dict[str, list[dict[str, object]]] = {}
    panel_bars: dict[str, tuple[SelectionBar, ...]] = {}
    locations: dict[str, dict[date, int]] = {}
    for code, group in normalized.groupby("code", sort=True):
        records = group.to_dict("records")
        panel_records[code] = records
        panel_bars[code] = _selection_bars(records)
        locations[code] = {
            value.trade_date: index for index, value in enumerate(panel_bars[code])
        }
    eligible_by_date = {
        current_date: tuple(group["code"])
        for current_date, group in normalized[normalized["prefilter"]].groupby("trade_date")
    }
    signal_dates = tuple(
        value
        for value in sorted(set(normalized["trade_date"]))
        if start <= value <= end
    )
    cross_sections = build_cross_section_snapshots(normalized)
    opportunities: dict[str, list[ProxyOpportunity]] = {
        policy.name: [] for policy in POLICIES
    }
    rejection_counts: dict[str, Counter[str]] = {
        policy.name: Counter() for policy in POLICIES
    }

    for signal_date in signal_dates:
        rows: list[dict[str, object]] = []
        histories: dict[str, tuple[SelectionBar, ...]] = {}
        signal_locations: dict[str, int] = {}
        indicators: dict[str, TechnicalIndicatorSnapshot] = {}
        for code in eligible_by_date.get(signal_date, ()):
            index = locations[code][signal_date]
            if index < 59:
                continue
            history = panel_bars[code][max(0, index - 119) : index + 1]
            histories[code] = history
            signal_locations[code] = index
            current = panel_records[code][index]
            rows.append(
                {
                    "代码": code,
                    "名称": str(current.get("name", code)),
                    "所属行业": str(current.get("sector", code)),
                    "策略来源": "production-backtest",
                }
            )
            try:
                indicators[code] = compute_technical_indicators(history)
            except IndicatorInputError:
                rejection_counts["BASELINE"]["INDICATOR_INVALID"] += 1
        if not rows:
            continue
        snapshot = cross_sections.get(signal_date)
        for policy in POLICIES:
            if policy.strict and (snapshot is None or not snapshot.is_usable):
                rejection_counts[policy.name]["CROSS_SECTION_INCOMPLETE"] += 1
                continue
            selected = select_short_term_candidates(
                analysis_date=signal_date,
                rows=rows,
                bars_by_code=histories,
                holding_codes=set(),
                st_codes=set(),
                relative_strength_by_code=(snapshot.percentiles if snapshot else None),
                technical_indicators_by_code=indicators,
                policy=policy,
                limit=top_n,
            )
            rejection_counts[policy.name].update(
                item.reason for item in selected.rejected
            )
            for candidate in selected.candidates:
                indicator = indicators.get(candidate.code)
                if indicator is None:
                    rejection_counts[policy.name]["INDICATOR_INVALID"] += 1
                    continue
                enriched = replace(
                    candidate,
                    metrics={**candidate.metrics, **asdict(indicator)},
                )
                plan = build_proxy_plan(enriched, histories[candidate.code])
                index = signal_locations[candidate.code]
                subsequent = panel_bars[candidate.code][index + 1 : index + 6]
                opportunities[policy.name].append(
                    ProxyOpportunity(plan=plan, bars=subsequent)
                )
    return OpportunityBuild(
        opportunities={
            name: tuple(values) for name, values in opportunities.items()
        },
        rejection_counts={
            name: dict(values) for name, values in rejection_counts.items()
        },
        signal_dates=signal_dates,
    )


def _metrics_from_portfolio(
    portfolio: PortfolioBacktestResult,
    opportunities: Sequence[ProxyOpportunity],
) -> tuple[BacktestMetrics, dict[str, object]]:
    shapes = {
        (item.plan.code, item.plan.signal_date): item.plan.candidate_type
        for item in opportunities
    }
    returns = [float(item.net_return or 0.0) * 100.0 for item in portfolio.trades]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value <= 0]
    shape_counts = Counter(
        shapes[(item.code, item.signal_date)] for item in portfolio.trades
    )
    metrics = BacktestMetrics(
        trade_count=len(returns),
        wins=len(wins),
        expectancy=sum(returns) / len(returns) if returns else 0.0,
        shape_counts={
            "BREAKOUT": shape_counts.get("BREAKOUT", 0),
            "PULLBACK": shape_counts.get("PULLBACK", 0),
        },
    )
    average_win = sum(wins) / len(wins) if wins else None
    average_loss = sum(losses) / len(losses) if losses else None
    profit_loss_ratio = (
        average_win / abs(average_loss)
        if average_win is not None and average_loss not in (None, 0)
        else None
    )
    details = {
        **metrics.to_dict(),
        "average_win_pct": average_win,
        "average_loss_pct": average_loss,
        "profit_loss_ratio": profit_loss_ratio,
        "max_drawdown_pct": portfolio.max_drawdown * 100.0,
        "execution_rejections": dict(
            Counter(item.status for item in portfolio.rejections)
        ),
    }
    return metrics, details


def run_policy_research(
    frame: pd.DataFrame,
    *,
    start: date,
    end: date,
    commission_rate: float = 0.001,
    slippage_rate: float = 0.001,
    max_positions: int = 2,
    cooldown_sessions: int = 5,
    top_n: int = 5,
) -> ResearchOutcome:
    normalized = _prepare_research_frame(frame)
    research_dates = tuple(
        value
        for value in sorted(set(normalized["trade_date"]))
        if start <= value <= end
    )
    split = chronological_splits(research_dates)
    build = build_policy_opportunities(
        normalized,
        start=start,
        end=end,
        top_n=top_n,
    )
    segments = {
        "train": split.train,
        "validation": split.validation,
        "test": split.test,
    }
    common_configuration = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "commission_rate": commission_rate,
        "slippage_rate": slippage_rate,
        "max_positions": max_positions,
        "cooldown_sessions": cooldown_sessions,
    }
    reports: dict[str, dict[str, object]] = {}
    validation_metrics: dict[str, BacktestMetrics] = {}
    test_metrics: dict[str, BacktestMetrics] = {}
    for policy in POLICIES:
        segment_reports: dict[str, object] = {}
        for segment_name, segment_dates in segments.items():
            date_set = set(segment_dates)
            segment_opportunities = tuple(
                item
                for item in build.opportunities[policy.name]
                if item.plan.signal_date in date_set
            )
            portfolio = simulate_proxy_portfolio(
                segment_opportunities,
                market_dates=segment_dates,
                commission_rate=commission_rate,
                slippage_rate=slippage_rate,
                max_positions=max_positions,
                cooldown_sessions=cooldown_sessions,
            )
            metrics, detail = _metrics_from_portfolio(
                portfolio, segment_opportunities
            )
            segment_reports[segment_name] = detail
            if segment_name == "validation" and policy.strict:
                validation_metrics[policy.name] = metrics
            if segment_name == "test":
                test_metrics[policy.name] = metrics
        reports[policy.name] = {
            "rule_version": policy.rule_version,
            "configuration": dict(common_configuration),
            "segments": segment_reports,
            "selection_rejections": dict(build.rejection_counts[policy.name]),
        }

    selected_profile = choose_validation_profile(validation=validation_metrics)
    baseline_test = test_metrics["BASELINE"]
    candidate_test = (
        test_metrics[selected_profile]
        if selected_profile is not None
        else BacktestMetrics(
            trade_count=0,
            wins=0,
            expectancy=0.0,
            shape_counts={"BREAKOUT": 0, "PULLBACK": 0},
        )
    )
    decision = (
        evaluate_promotion(baseline=baseline_test, candidate=candidate_test)
        if selected_profile is not None
        else PromotionDecision(False, ("NO_VALIDATION_PROFILE",))
    )
    split_bounds = {
        name: {"start": values[0].isoformat(), "end": values[-1].isoformat()}
        for name, values in segments.items()
    }
    artifact = ValidationArtifact(
        schema_version="short-term-selection-validation-v1",
        rule_version="short-term-selection-2.1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_bounds={"start": start.isoformat(), "end": end.isoformat()},
        split_bounds=split_bounds,
        costs={
            "commission_rate": commission_rate,
            "slippage_rate": slippage_rate,
        },
        selected_profile=selected_profile,
        metrics={
            "baseline_test": baseline_test.to_dict(),
            "candidate_test": candidate_test.to_dict(),
        },
        promoted=decision.promoted,
        reasons=decision.reasons,
    )
    payload: dict[str, object] = {
        "report_type": "technical_execution_proxy",
        "data_bounds": artifact.data_bounds,
        "split_bounds": split_bounds,
        "selected_profile": selected_profile,
        "promotion": {
            "promoted": decision.promoted,
            "reasons": list(decision.reasons),
        },
        "policies": reports,
        "limitations": [
            "historical chips, order books, flows, and sectors are not reconstructed",
            "results do not represent future returns and do not place orders",
        ],
    }
    return ResearchOutcome(payload=payload, artifact=artifact)


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
    parser = argparse.ArgumentParser(description="高精度短线技术执行代理回测")
    parser.add_argument("--start", default="2024-01-02")
    parser.add_argument("--end")
    parser.add_argument("--commission-rate", type=float, default=0.001)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--max-positions", type=int, default=2)
    parser.add_argument("--cooldown-sessions", type=int, default=5)
    parser.add_argument("--output", choices=("text", "json"), default="text")
    parser.add_argument("--write-validation")
    args = parser.parse_args(argv)
    try:
        engine = _mysql_engine()
        end_value = args.end
        if end_value is None:
            with engine.connect() as connection:
                latest = connection.execute(
                    text("SELECT MAX(trade_date) FROM stock_daily")
                ).scalar_one()
            if latest is None:
                raise ValidationError("stock_daily has no completed dates")
            end_value = str(latest)[:10]
        prices = load_prices(engine, args.start, end_value)
        outcome = run_policy_research(
            prices,
            start=date.fromisoformat(args.start),
            end=date.fromisoformat(end_value),
            commission_rate=args.commission_rate,
            slippage_rate=args.slippage_rate,
            max_positions=args.max_positions,
            cooldown_sessions=args.cooldown_sessions,
            top_n=args.top_n,
        )
        if args.write_validation:
            write_validation_artifact(args.write_validation, outcome.artifact)
    except (ValidationError, ValueError):
        print("validation_error")
        return 2
    except Exception:
        print("research_failed")
        return 2

    if args.output == "json":
        print(
            json.dumps(
                outcome.payload,
                ensure_ascii=False,
                indent=2,
                default=_json_default,
                sort_keys=True,
            )
        )
    else:
        promotion = outcome.payload["promotion"]
        print("高精度短线技术执行代理回测")
        print(f"验证集选择: {outcome.payload['selected_profile'] or '无'}")
        print(f"晋级: {promotion['promoted']}")
        print(f"原因: {','.join(promotion['reasons']) or '全部门禁通过'}")
        print("该结果不代表未来收益，也不会触发自动下单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
