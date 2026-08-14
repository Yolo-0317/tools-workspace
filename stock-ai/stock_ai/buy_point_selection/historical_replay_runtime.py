"""MySQL and BaoStock adapters for point-in-time buy-point replay."""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import os
from typing import Mapping, Sequence

from sqlalchemy import create_engine, text

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6

from .gates import anti_chase_gate, base_gate, classify_market, sector_gate
from .historical_replay import (
    HistoricalPlan,
    ReplayBundle,
    replay_historical_plans,
    second_trading_date_after,
)
from .models import BuyPointBar, MarketSnapshot, SectorSnapshot, SelectionPolicy
from .patterns import detect_setups
from .planning import RiskBudget, build_price_plan
from .reference_baostock import BaoStockReferenceProvider
from .reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SQLReferenceRepository,
    SectorMembership,
    membership_on,
    risk_flags_on,
)
from .reference_sources import IndexBar
from .validation import policy_hash


BENCHMARK_INDEX_CODES = ("sh.000001", "sz.399001", "sh.000688")
STAGE1_RISK_BUDGET = RiskBudget(
    loss_budget=Decimal("500"),
    ticket_limit=Decimal("4000"),
    remaining_exposure=Decimal("40000"),
)


class HistoricalReplayRuntimeError(RuntimeError):
    """Raised when database or provider inputs cannot support a replay."""


@dataclass(frozen=True)
class MarketDailyAggregate:
    trade_date: date
    valid_count: int
    advancing_count: int
    total_amount: Decimal


@dataclass(frozen=True)
class DiscoveryResult:
    plans: tuple[HistoricalPlan, ...]
    rejection_counts: Mapping[str, int]


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _panel_on(
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    dates_by_code: Mapping[str, Sequence[date]],
    analysis_date: date,
) -> dict[str, tuple[BuyPointBar, ...]]:
    panel: dict[str, tuple[BuyPointBar, ...]] = {}
    for code, bars in bars_by_code.items():
        ordered = bars
        dates = dates_by_code[code]
        stop = bisect_right(dates, analysis_date)
        if stop:
            panel[code] = tuple(ordered[max(0, stop - 120) : stop])
    return panel


def _sector_snapshots(
    panel: Mapping[str, Sequence[BuyPointBar]],
    memberships: Mapping[str, SectorMembership],
    policy: SelectionPolicy,
) -> dict[str, SectorSnapshot]:
    grouped: dict[str, list[tuple[str, Sequence[BuyPointBar]]]] = {}
    names: dict[str, str] = {}
    for code, membership in memberships.items():
        bars = panel.get(code, ())
        if len(bars) < 20:
            continue
        grouped.setdefault(membership.sector_code, []).append((code, bars))
        names[membership.sector_code] = membership.sector_name
    returns = {
        sector: _average(
            [bars[-1].close / bars[-6].close - Decimal("1") for _, bars in members]
        )
        for sector, members in grouped.items()
        if members and all(len(bars) >= 10 for _, bars in members)
    }
    ordered_returns = sorted(returns.values())
    snapshots: dict[str, SectorSnapshot] = {}
    for sector, members in grouped.items():
        if sector not in returns:
            continue
        liquid = [
            (code, bars)
            for code, bars in members
            if _average([value.amount_qian for value in bars[-5:]])
            >= policy.min_average_amount5_qian
        ]
        strengthening = sum(
            bars[-1].close >= _average([value.close for value in bars[-20:]])
            and bars[-1].pct_chg > 0
            for _, bars in liquid
        )
        advancing = sum(bars[-1].pct_chg > 0 for _, bars in liquid)
        recent_amount = sum(
            (value.amount_qian for _, bars in liquid for value in bars[-5:]),
            Decimal("0"),
        )
        prior_amount = sum(
            (value.amount_qian for _, bars in liquid for value in bars[-10:-5]),
            Decimal("0"),
        )
        rank = ordered_returns.index(returns[sector]) + 1
        snapshots[sector] = SectorSnapshot(
            sector_code=sector,
            sector_name=names[sector],
            return_percentile=rank / len(ordered_returns),
            liquid_member_count=len(liquid),
            strengthening_member_count=strengthening,
            breadth_ratio=advancing / len(liquid) if liquid else 0.0,
            amount_ratio=float(recent_amount / prior_amount) if prior_amount > 0 else 0.0,
            membership_complete=True,
        )
    return snapshots


def build_historical_market_snapshots(
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    index_bars_by_code: Mapping[str, Sequence[IndexBar]],
    *,
    market_aggregates_by_date: Mapping[date, MarketDailyAggregate] | None = None,
) -> dict[date, MarketSnapshot]:
    ordered_dates = tuple(trading_dates)
    requested_dates = frozenset(ordered_dates)
    index_by_date = {
        code: {bar.trade_date: bar for bar in bars}
        for code, bars in index_bars_by_code.items()
    }
    equity_by_date: dict[date, list[BuyPointBar]] = {}
    for bars in bars_by_code.values():
        for bar in bars:
            if bar.trade_date in requested_dates:
                equity_by_date.setdefault(bar.trade_date, []).append(bar)
    snapshots: dict[date, MarketSnapshot] = {}
    for index, current_date in enumerate(ordered_dates):
        previous_date = ordered_dates[index - 1] if index else None
        current_equities = equity_by_date.get(current_date, ())
        previous_equities = equity_by_date.get(previous_date, ()) if previous_date else ()
        current_aggregate = (
            market_aggregates_by_date.get(current_date)
            if market_aggregates_by_date is not None
            else None
        )
        previous_aggregate = (
            market_aggregates_by_date.get(previous_date)
            if market_aggregates_by_date is not None and previous_date is not None
            else None
        )
        current_amount = (
            current_aggregate.total_amount
            if current_aggregate is not None
            else sum((bar.amount_qian for bar in current_equities), Decimal("0"))
        )
        previous_amount = (
            previous_aggregate.total_amount
            if previous_aggregate is not None
            else sum((bar.amount_qian for bar in previous_equities), Decimal("0"))
        )
        valid_indexes = True
        above = 0
        for code in BENCHMARK_INDEX_CODES:
            dated = index_by_date.get(code, {})
            history = [dated[day].close for day in ordered_dates[: index + 1] if day in dated]
            if current_date not in dated or len(history) < 20:
                valid_indexes = False
                continue
            above += history[-1] > _average(history[-20:])
        complete = bool(
            valid_indexes
            and (
                current_aggregate is not None
                and current_aggregate.valid_count > 0
                if market_aggregates_by_date is not None
                else current_equities
            )
            and (
                previous_aggregate is not None
                and previous_aggregate.valid_count > 0
                if market_aggregates_by_date is not None
                else previous_equities
            )
            and current_amount > 0
            and previous_amount > 0
        )
        breadth_pct = (
            100.0
            * current_aggregate.advancing_count
            / current_aggregate.valid_count
            if current_aggregate is not None and current_aggregate.valid_count > 0
            else (
                100.0
                * sum(bar.pct_chg > 0 for bar in current_equities)
                / len(current_equities)
                if current_equities
                else 0.0
            )
        )
        snapshots[current_date] = MarketSnapshot(
            indexes_above_ma20=above,
            breadth_pct=breadth_pct,
            amount_ratio=(
                float(current_amount / previous_amount)
                if previous_amount > 0
                else 0.0
            ),
            complete=complete,
        )
    return snapshots


def _cumulative_return_pct(bars: Sequence[BuyPointBar], sessions: int) -> Decimal:
    return (bars[-1].close / bars[-sessions - 1].close - Decimal("1")) * Decimal("100")


def discover_historical_plans(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_snapshots: Mapping[date, MarketSnapshot],
    policy: SelectionPolicy | None = None,
    risk_budget: RiskBudget = STAGE1_RISK_BUDGET,
) -> DiscoveryResult:
    resolved = policy or SelectionPolicy()
    plans: list[HistoricalPlan] = []
    rejections: Counter[str] = Counter()
    dates_by_code = {
        code: tuple(value.trade_date for value in bars)
        for code, bars in bars_by_code.items()
    }
    for analysis_date in signal_dates:
        coverage = coverage_by_date.get(analysis_date)
        if coverage is None or not coverage.complete:
            rejections["POINT_IN_TIME_COVERAGE_INCOMPLETE"] += 1
            continue
        market_snapshot = market_snapshots.get(
            analysis_date, MarketSnapshot(0, 0.0, 0.0, False)
        )
        market = classify_market(market_snapshot)
        if market.status == "FREEZE":
            rejections.update(market.reasons)
            continue
        try:
            valid_through = second_trading_date_after(trading_dates, analysis_date)
        except ValueError:
            rejections["FUTURE_TRADING_DATES_MISSING"] += 1
            continue
        panel = _panel_on(bars_by_code, dates_by_code, analysis_date)
        memberships_on_date = membership_on(memberships, analysis_date)
        flags_on_date = risk_flags_on(risk_flags, analysis_date)
        sectors = _sector_snapshots(panel, memberships_on_date, resolved)
        for code, bars in sorted(panel.items()):
            if not bars or bars[-1].trade_date != analysis_date:
                rejections["LATEST_BAR_MISSING"] += 1
                continue
            base = base_gate(code, bars, set(), flags_on_date, resolved)
            if not base.passed:
                rejections.update(base.reasons)
                continue
            setups = detect_setups(code, bars, resolved)
            if not setups:
                rejections["NO_BUY_POINT_SETUP"] += 1
                continue
            setup = max(setups, key=lambda value: (value.quality, value.setup_type.value))
            ma5 = _average([value.close for value in bars[-5:]])
            ma20 = _average([value.close for value in bars[-20:]])
            anti = anti_chase_gate(
                bars[-1].pct_chg,
                _cumulative_return_pct(bars, 3),
                _cumulative_return_pct(bars, 5),
                (bars[-1].close / ma5 - Decimal("1")) * Decimal("100"),
                (bars[-1].close / ma20 - Decimal("1")) * Decimal("100"),
                resolved,
            )
            if not anti.passed:
                rejections.update(anti.reasons)
                continue
            membership = memberships_on_date.get(code)
            if membership is None:
                rejections["SECTOR_MISSING"] += 1
                continue
            sector = sectors.get(membership.sector_code)
            if sector is None:
                rejections["SECTOR_MISSING"] += 1
                continue
            sector_decision = sector_gate(sector, resolved)
            if not sector_decision.passed:
                rejections.update(sector_decision.reasons)
                continue
            decision = build_price_plan(
                setup,
                bars,
                risk_budget,
                market.status,
                resolved,
                valid_through_trade_date=valid_through,
            )
            if decision.plan is None:
                rejections.update(decision.reasons)
                continue
            plans.append(
                HistoricalPlan(
                    signal_date=analysis_date,
                    code=code,
                    sector_code=membership.sector_code,
                    market_status=market.status,
                    sector_resonating=True,
                    plan=decision.plan,
                )
            )
    return DiscoveryResult(tuple(plans), dict(sorted(rejections.items())))


def _load_daily_bars(engine, start: date, end: date) -> dict[str, tuple[BuyPointBar, ...]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT ts_code, trade_date, open, high, low, close, pct_chg, amount "
                "FROM stock_daily WHERE trade_date BETWEEN :start AND :end "
                "ORDER BY ts_code, trade_date"
            ),
            {"start": start, "end": end},
        ).mappings()
        loaded = list(rows)
    grouped: dict[str, dict[date, BuyPointBar]] = {}
    for row in loaded:
        code = normalize_code6(str(row["ts_code"]))
        if not is_sh_sz_main_board_code(code):
            continue
        trade_date = row["trade_date"]
        if not isinstance(trade_date, date):
            trade_date = date.fromisoformat(str(trade_date)[:10])
        required = (row["open"], row["high"], row["low"], row["close"], row["amount"])
        if any(value is None for value in required):
            continue
        grouped.setdefault(code, {})[trade_date] = BuyPointBar(
            trade_date=trade_date,
            open=Decimal(str(row["open"])),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
            close=Decimal(str(row["close"])),
            pct_chg=Decimal(str(row["pct_chg"] or 0)),
            amount_qian=Decimal(str(row["amount"])),
        )
    return {
        code: tuple(value for _, value in sorted(rows.items()))
        for code, rows in grouped.items()
    }


def _trade_dates(engine, start: date, end: date) -> tuple[date, ...]:
    with engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    "SELECT DISTINCT trade_date FROM stock_daily "
                    "WHERE trade_date BETWEEN :start AND :end ORDER BY trade_date"
                ),
                {"start": start, "end": end},
            ).scalars()
        )


def _future_dates(engine, end: date, count: int = 7) -> tuple[date, ...]:
    with engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    "SELECT DISTINCT trade_date FROM stock_daily WHERE trade_date > :end "
                    "ORDER BY trade_date LIMIT :count"
                ),
                {"end": end, "count": count},
            ).scalars()
        )


def _load_market_aggregates(
    engine, start: date, end: date
) -> dict[date, MarketDailyAggregate]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT trade_date, COUNT(pct_chg) AS valid_count, "
                "SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) AS advancing_count, "
                "SUM(amount) AS total_amount FROM stock_daily "
                "WHERE trade_date BETWEEN :start AND :end GROUP BY trade_date "
                "ORDER BY trade_date"
            ),
            {"start": start, "end": end},
        ).mappings()
        return {
            row["trade_date"]: MarketDailyAggregate(
                trade_date=row["trade_date"],
                valid_count=int(row["valid_count"] or 0),
                advancing_count=int(row["advancing_count"] or 0),
                total_amount=Decimal(str(row["total_amount"] or 0)),
            )
            for row in rows
        }


def generate_mysql_replay_bundle(start: date, end: date) -> ReplayBundle:
    from dotenv import load_dotenv

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    load_dotenv(os.path.join(root, ".env"), override=False)
    mysql_url = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal", "127.0.0.1"
    )
    if not mysql_url:
        raise HistoricalReplayRuntimeError("MYSQL_URL is not configured")
    engine = create_engine(mysql_url, pool_pre_ping=True)
    signal_dates = _trade_dates(engine, start, end)
    if len(signal_dates) < 630:
        raise HistoricalReplayRuntimeError("at least 630 signal trading dates are required")
    future_dates = _future_dates(engine, end)
    if len(future_dates) < 7:
        raise HistoricalReplayRuntimeError("seven future trading dates are required")
    all_dates = signal_dates + future_dates
    history_start = start - timedelta(days=180)
    bars_by_code = _load_daily_bars(engine, history_start, future_dates[-1])
    repository = SQLReferenceRepository(engine)
    coverage = repository.coverage_between(signal_dates)
    memberships = repository.memberships_between(history_start, end)
    risk_flags = repository.risk_flags_between(start, end)

    index_provider = BaoStockReferenceProvider()
    with index_provider.session():
        index_bars = {
            code: index_provider.fetch_index_bars(code, history_start, end)
            for code in BENCHMARK_INDEX_CODES
        }
    market_dates = _trade_dates(engine, history_start, end)
    market_aggregates = _load_market_aggregates(engine, history_start, end)
    market_snapshots = build_historical_market_snapshots(
        market_dates,
        bars_by_code,
        index_bars,
        market_aggregates_by_date=market_aggregates,
    )
    discovery = discover_historical_plans(
        signal_dates=signal_dates,
        trading_dates=all_dates,
        bars_by_code=bars_by_code,
        memberships=memberships,
        risk_flags=risk_flags,
        coverage_by_date=coverage,
        market_snapshots=market_snapshots,
    )
    replay = replay_historical_plans(
        discovery.plans,
        bars_by_code,
        coverage,
        signal_dates=signal_dates,
        market_complete_by_date={
            day: market_snapshots.get(day, MarketSnapshot(0, 0.0, 0.0, False)).complete
            for day in signal_dates
        },
    )
    policy = SelectionPolicy()
    return ReplayBundle(
        trading_dates=signal_dates,
        replay=replay,
        rule_version=policy.rule_version,
        policy_hash=policy_hash(policy),
        rejection_counts=discovery.rejection_counts,
    )
