"""Pure point-in-time replay of frozen historical buy-point plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from .execution import ExecutionCosts, SimulatedTrade, simulate_plan
from .models import BuyPointBar, OutcomeLabel, SetupType
from .planning import PricePlan
from .reference_data import ReferenceCoverage


@dataclass(frozen=True)
class HistoricalPlan:
    signal_date: date
    code: str
    sector_code: str
    market_status: str
    sector_resonating: bool
    plan: PricePlan

    def __post_init__(self) -> None:
        if self.plan.signal_date != self.signal_date:
            raise ValueError("historical plan signal date mismatch")
        if self.plan.code != self.code:
            raise ValueError("historical plan code mismatch")


@dataclass(frozen=True)
class HistoricalOpportunity:
    signal_date: date
    code: str
    sector_code: str
    market_status: str
    sector_resonating: bool
    setup_type: SetupType
    plan: PricePlan
    trade: SimulatedTrade
    resolution_date: date


@dataclass(frozen=True)
class ReplayIntegrity:
    total_plans: int
    emitted_plans: int
    duplicate_structures: int
    pending_plans: int
    missing_sector_dates: tuple[date, ...]
    missing_st_dates: tuple[date, ...]
    missing_announcement_dates: tuple[date, ...]
    missing_market_dates: tuple[date, ...] = ()

    @property
    def complete(self) -> bool:
        return not (
            self.pending_plans
            or self.missing_sector_dates
            or self.missing_st_dates
            or self.missing_announcement_dates
            or self.missing_market_dates
        )


@dataclass(frozen=True)
class HistoricalReplayResult:
    opportunities: tuple[HistoricalOpportunity, ...]
    integrity: ReplayIntegrity


@dataclass(frozen=True)
class ReplayBundle:
    trading_dates: tuple[date, ...]
    replay: HistoricalReplayResult
    rule_version: str
    policy_hash: str
    rejection_counts: Mapping[str, int]


def second_trading_date_after(
    trading_dates: Sequence[date], signal_date: date
) -> date:
    following = tuple(value for value in trading_dates if value > signal_date)
    if len(following) < 2:
        raise ValueError("two future trading dates are required")
    return following[1]


def _resolution_date(
    value: HistoricalPlan,
    trade: SimulatedTrade,
    bars: Sequence[BuyPointBar],
) -> date:
    if trade.exit_legs:
        return trade.exit_legs[-1].exit_date
    later_dates = tuple(bar.trade_date for bar in bars if bar.trade_date > value.signal_date)
    if trade.status == "EXPIRED":
        return value.plan.valid_through_trade_date
    return max(later_dates, default=value.signal_date)


def replay_historical_plans(
    plans: Sequence[HistoricalPlan],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    *,
    costs: ExecutionCosts | None = None,
    signal_dates: Sequence[date] | None = None,
    market_complete_by_date: Mapping[date, bool] | None = None,
) -> HistoricalReplayResult:
    opportunities: list[HistoricalOpportunity] = []
    seen_structures: set[str] = set()
    duplicate_structures = 0
    pending_plans = 0
    missing_sector: set[date] = set()
    missing_st: set[date] = set()
    missing_announcement: set[date] = set()
    missing_market: set[date] = set()

    integrity_dates = tuple(
        sorted(set(signal_dates or (value.signal_date for value in plans)))
    )
    for signal_date in integrity_dates:
        coverage = coverage_by_date.get(signal_date)
        if coverage is None or not coverage.sector_complete:
            missing_sector.add(signal_date)
        if coverage is None or not coverage.st_complete:
            missing_st.add(signal_date)
        if coverage is None or not coverage.announcement_complete:
            missing_announcement.add(signal_date)
        if (
            market_complete_by_date is not None
            and not market_complete_by_date.get(signal_date, False)
        ):
            missing_market.add(signal_date)

    for value in sorted(
        plans,
        key=lambda item: (
            item.signal_date,
            item.code,
            item.plan.structure_id,
        ),
    ):
        coverage = coverage_by_date.get(value.signal_date)
        if coverage is None or not coverage.sector_complete:
            missing_sector.add(value.signal_date)
        if coverage is None or not coverage.st_complete:
            missing_st.add(value.signal_date)
        if coverage is None or not coverage.announcement_complete:
            missing_announcement.add(value.signal_date)
        if coverage is None or not coverage.complete:
            continue
        if value.plan.structure_id in seen_structures:
            duplicate_structures += 1
            continue
        seen_structures.add(value.plan.structure_id)
        bars = tuple(bars_by_code.get(value.code, ()))
        trade = simulate_plan(
            value.plan,
            bars,
            costs,
            sector_code=value.sector_code,
        )
        if trade.outcome is OutcomeLabel.PENDING:
            pending_plans += 1
        opportunities.append(
            HistoricalOpportunity(
                signal_date=value.signal_date,
                code=value.code,
                sector_code=value.sector_code,
                market_status=value.market_status,
                sector_resonating=value.sector_resonating,
                setup_type=value.plan.setup_type,
                plan=value.plan,
                trade=trade,
                resolution_date=_resolution_date(value, trade, bars),
            )
        )

    return HistoricalReplayResult(
        opportunities=tuple(opportunities),
        integrity=ReplayIntegrity(
            total_plans=len(plans),
            emitted_plans=len(opportunities),
            duplicate_structures=duplicate_structures,
            pending_plans=pending_plans,
            missing_sector_dates=tuple(sorted(missing_sector)),
            missing_st_dates=tuple(sorted(missing_st)),
            missing_announcement_dates=tuple(sorted(missing_announcement)),
            missing_market_dates=tuple(sorted(missing_market)),
        ),
    )


def replay_observation_payload(value: HistoricalOpportunity) -> dict[str, object]:
    trade = value.trade
    return {
        "signal_date": value.signal_date.isoformat(),
        "exit_date": value.resolution_date.isoformat(),
        "code": value.code,
        "structure_id": value.plan.structure_id,
        "setup_type": value.setup_type.value,
        "sector_code": value.sector_code,
        "market_status": value.market_status,
        "sector_resonating": value.sector_resonating,
        "trigger_price": str(value.plan.trigger_price),
        "invalidation_price": str(value.plan.invalidation_price),
        "target_2r": str(value.plan.target_2r),
        "risk_fraction": str(value.plan.risk_distance / value.plan.trigger_price),
        "net_return": str(trade.net_return or Decimal("0")),
        "net_pnl": str(trade.net_pnl),
        "outcome": trade.outcome.value,
        "mfe": None if trade.mfe is None else str(trade.mfe),
        "mae": None if trade.mae is None else str(trade.mae),
        "entry_date": None if trade.entry_date is None else trade.entry_date.isoformat(),
        "entry_price": None if trade.entry_price is None else str(trade.entry_price),
        "exit_reason": trade.exit_reason,
        "intraday_order_ambiguous": trade.intraday_order_ambiguous,
    }
