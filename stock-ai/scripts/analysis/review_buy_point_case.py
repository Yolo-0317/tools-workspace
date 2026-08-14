#!/usr/bin/env python3
"""Generate a read-only short-window buy-point case review."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
import sys
from typing import Callable, Mapping, Protocol, Sequence

from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_ai.buy_point_selection.case_report import write_case_revision
from stock_ai.buy_point_selection.case_review import (
    CaseReview,
    attribute_buyable_winners,
    evaluate_case_plan,
    find_buyable_winners,
    replay_case_signals,
)
from stock_ai.buy_point_selection.models import BuyPointBar, MarketSnapshot, SelectionPolicy
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
)
from stock_ai.buy_point_selection.validation import policy_hash
from stock_ai.market_codes import normalize_code6


class CaseReviewRuntime(Protocol):
    def build_review(self, start: date, end: date, cutoff: date) -> CaseReview: ...


@dataclass(frozen=True)
class CaseReviewInputs:
    trading_dates: tuple[date, ...]
    bars_by_code: Mapping[str, Sequence[BuyPointBar]]
    memberships: tuple[SectorMembership, ...]
    risk_flags: tuple[RiskFlag, ...]
    coverage_by_date: Mapping[date, ReferenceCoverage]
    market_snapshots: Mapping[date, MarketSnapshot]
    holding_codes_by_date: Mapping[date, frozenset[str]]
    holdings_complete_by_date: Mapping[date, bool] = field(default_factory=dict)


class DefaultRuntime:
    def __init__(
        self,
        *,
        input_loader: Callable[[date, date, date], CaseReviewInputs] | None = None,
    ) -> None:
        self._input_loader = input_loader or load_mysql_case_inputs

    def build_review(self, start: date, end: date, cutoff: date) -> CaseReview:
        inputs = self._input_loader(start, end, cutoff)
        signal_dates = tuple(
            value for value in inputs.trading_dates if start <= value <= end
        )
        if not signal_dates:
            raise ValueError("信号窗口没有交易日")
        complete_dates = tuple(
            value for value in inputs.trading_dates if value <= cutoff
        )
        if not complete_dates:
            raise ValueError("结果截止日前没有完整市场数据")
        effective_cutoff = complete_dates[-1]
        replay = replay_case_signals(
            signal_dates=signal_dates,
            trading_dates=inputs.trading_dates,
            bars_by_code=inputs.bars_by_code,
            memberships=inputs.memberships,
            risk_flags=inputs.risk_flags,
            coverage_by_date=inputs.coverage_by_date,
            market_snapshots=inputs.market_snapshots,
            holding_codes_by_date=inputs.holding_codes_by_date,
        )
        incomplete_holdings = {
            value
            for value in signal_dates
            if inputs.holdings_complete_by_date
            and not inputs.holdings_complete_by_date.get(value, False)
        }
        if incomplete_holdings:
            replay = replace(
                replay,
                incomplete_dates=tuple(
                    sorted(set(replay.incomplete_dates) | incomplete_holdings)
                ),
            )
        candidates = (*replay.strict_shadow, *replay.near_misses)
        outcomes = tuple(
            evaluate_case_plan(
                candidate,
                inputs.bars_by_code.get(candidate.code, ()),
                outcome_cutoff=effective_cutoff,
            )
            for candidate in candidates
        )
        final_signal_date = signal_dates[-1]
        outcome_dates = tuple(
            value
            for value in inputs.trading_dates
            if final_signal_date < value <= effective_cutoff
        )
        winners = find_buyable_winners(
            signal_date=final_signal_date,
            outcome_dates=outcome_dates,
            bars_by_code=inputs.bars_by_code,
            risk_flags=inputs.risk_flags,
            holding_codes=inputs.holding_codes_by_date.get(
                final_signal_date, frozenset()
            ),
        )
        attributed = attribute_buyable_winners(winners, replay)
        risk_coverage_complete = all(
            inputs.coverage_by_date.get(value) is not None
            and inputs.coverage_by_date[value].announcement_complete
            for value in signal_dates
        )
        selection_policy = SelectionPolicy()
        return CaseReview(
            signal_dates=signal_dates,
            outcome_cutoff=effective_cutoff,
            rule_version=selection_policy.rule_version,
            policy_hash=policy_hash(selection_policy),
            replay=replay,
            outcomes=outcomes,
            winners=attributed,
            risk_coverage_complete=risk_coverage_complete,
        )


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _load_holdings_by_date(
    engine: object,
    signal_dates: Sequence[date],
) -> tuple[dict[date, frozenset[str]], dict[date, bool]]:
    """Read point-in-time holdings without falling back to current positions."""
    ordered_dates = tuple(sorted(set(signal_dates)))
    if not ordered_dates:
        return {}, {}
    parameters = {"start": ordered_dates[0], "end": ordered_dates[-1]}
    with engine.connect() as connection:
        account_rows = list(
            connection.execute(
                text(
                    "SELECT snapshot_date FROM portfolio_account_daily "
                    "WHERE snapshot_slot = 'eod' "
                    "AND snapshot_date BETWEEN :start AND :end"
                ),
                parameters,
            ).mappings()
        )
        position_rows = list(
            connection.execute(
                text(
                    "SELECT snapshot_date, ts_code, shares "
                    "FROM portfolio_positions_daily "
                    "WHERE snapshot_slot = 'eod' "
                    "AND snapshot_date BETWEEN :start AND :end"
                ),
                parameters,
            ).mappings()
        )
        event_rows = list(
            connection.execute(
                text(
                    "SELECT ts_code, shares_after, broker_captured_at "
                    "FROM portfolio_position_events "
                    "WHERE broker_captured_at < :cutoff "
                    "ORDER BY broker_captured_at, ts_code"
                ),
                {
                    "cutoff": datetime.combine(
                        ordered_dates[-1] + timedelta(days=1), time.min
                    )
                },
            ).mappings()
        )
    snapshot_dates = {_as_date(row["snapshot_date"]) for row in account_rows}
    snapshot_holdings: dict[date, set[str]] = {
        value: set() for value in snapshot_dates
    }
    for row in position_rows:
        snapshot_date = _as_date(row["snapshot_date"])
        if int(row["shares"] or 0) > 0:
            snapshot_holdings.setdefault(snapshot_date, set()).add(
                normalize_code6(str(row["ts_code"]))
            )
    events = tuple(
        (
            _as_datetime(row["broker_captured_at"]),
            normalize_code6(str(row["ts_code"])),
            int(row["shares_after"] or 0),
        )
        for row in event_rows
    )
    holdings: dict[date, frozenset[str]] = {}
    complete: dict[date, bool] = {}
    for signal_date in ordered_dates:
        if signal_date in snapshot_dates:
            holdings[signal_date] = frozenset(
                snapshot_holdings.get(signal_date, set())
            )
            complete[signal_date] = True
            continue
        cutoff = datetime.combine(signal_date + timedelta(days=1), time.min)
        applicable = tuple(value for value in events if value[0] < cutoff)
        latest_by_code: dict[str, int] = {}
        for _, code, shares_after in applicable:
            latest_by_code[code] = shares_after
        holdings[signal_date] = frozenset(
            code for code, shares in latest_by_code.items() if shares > 0
        )
        complete[signal_date] = bool(applicable)
    return holdings, complete


def load_mysql_case_inputs(
    start: date,
    end: date,
    cutoff: date,
) -> CaseReviewInputs:
    """Load a bounded, read-only point-in-time bundle from existing stores."""
    import os

    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    from stock_ai.buy_point_selection.historical_replay_runtime import (
        BENCHMARK_INDEX_CODES,
        _load_daily_bars,
        _load_market_aggregates,
        _trade_dates,
        build_historical_market_snapshots,
    )
    from stock_ai.buy_point_selection.reference_baostock import (
        BaoStockReferenceProvider,
    )
    from stock_ai.buy_point_selection.reference_data import SQLReferenceRepository

    load_dotenv(ROOT / ".env", override=False)
    mysql_url = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal", "127.0.0.1"
    )
    if not mysql_url:
        raise RuntimeError("未配置 MYSQL_URL")
    engine = create_engine(mysql_url, pool_pre_ping=True)
    history_start = start - timedelta(days=180)
    trading_dates = _trade_dates(engine, history_start, cutoff)
    signal_dates = tuple(value for value in trading_dates if start <= value <= end)
    if not signal_dates:
        raise RuntimeError("信号窗口没有完整日线")
    if len(tuple(value for value in trading_dates if value > signal_dates[-1])) < 2:
        raise RuntimeError("缺少至少两个信号后交易日")
    bars_by_code = _load_daily_bars(engine, history_start, cutoff)
    repository = SQLReferenceRepository(engine)
    coverage = repository.coverage_between(signal_dates)
    memberships = repository.memberships_between(history_start, end)
    risk_flags = repository.risk_flags_between(start, end)
    market_dates = tuple(value for value in trading_dates if value <= end)
    market_aggregates = _load_market_aggregates(engine, history_start, end)
    index_provider = BaoStockReferenceProvider()
    with index_provider.session():
        index_bars = {
            code: index_provider.fetch_index_bars(code, history_start, end)
            for code in BENCHMARK_INDEX_CODES
        }
    market_snapshots = build_historical_market_snapshots(
        market_dates,
        bars_by_code,
        index_bars,
        market_aggregates_by_date=market_aggregates,
    )
    holdings, holdings_complete = _load_holdings_by_date(engine, signal_dates)
    return CaseReviewInputs(
        trading_dates=trading_dates,
        bars_by_code=bars_by_code,
        memberships=memberships,
        risk_flags=risk_flags,
        coverage_by_date=coverage,
        market_snapshots=market_snapshots,
        holding_codes_by_date=holdings,
        holdings_complete_by_date=holdings_complete,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成短窗口买点案例复盘（只读）")
    parser.add_argument("--signal-start", type=date.fromisoformat, required=True)
    parser.add_argument("--signal-end", type=date.fromisoformat, required=True)
    parser.add_argument("--outcome-cutoff", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--output-dir",
        default="output/research/buy_point_cases",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime_factory: Callable[[], CaseReviewRuntime] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    if args.signal_start > args.signal_end:
        print("信号开始日不能晚于信号结束日", file=sys.stderr)
        return 2
    if args.outcome_cutoff <= args.signal_end:
        print("结果截止日必须晚于信号结束日", file=sys.stderr)
        return 2
    factory = runtime_factory or DefaultRuntime
    try:
        review = factory().build_review(
            args.signal_start,
            args.signal_end,
            args.outcome_cutoff,
        )
        json_path, markdown_path = write_case_revision(review, args.output_dir)
    except Exception as exc:
        print(f"案例复盘失败：{exc}", file=sys.stderr)
        return 2
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
