"""Pure, zero-share diagnostics for exact-date short-term recall."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from stock_ai.market_codes import is_sh_sz_main_board_code, normalize_code6

from .case_review import CaseSignalReplay
from .gates import base_gate
from .models import BuyPointBar, SelectionPolicy
from .patterns import detect_setups
from .reference_data import RiskFlag, risk_flags_on


@dataclass(frozen=True)
class DailyRecallWinner:
    code: str
    signal_date: date
    horizon_end_date: date
    entry_date: date
    entry_price: Decimal
    forward_maximum_gain: Decimal
    maximum_gain_date: date
    captured_tiers: tuple[str, ...] = ()
    first_rejection: str | None = None
    executable_shares: int = 0


@dataclass(frozen=True)
class DailyRecallCohort:
    signal_date: date
    outcome_dates: tuple[date, ...]
    complete: bool
    winners: tuple[DailyRecallWinner, ...]


@dataclass(frozen=True)
class MarketFreezeDiagnostic:
    code: str
    signal_date: date
    market_reason: str
    base_passed: bool
    base_reasons: tuple[str, ...]
    setup_types: tuple[str, ...]
    setup_qualities: tuple[Decimal, ...]
    executable_shares: int = 0


MARKET_FREEZE_REASONS = frozenset(
    {"INDEX_AND_BREADTH_WEAK", "AMOUNT_AND_BREADTH_WEAK"}
)


def attribute_daily_recall_winners(
    winners: Sequence[DailyRecallWinner],
    replay: CaseSignalReplay,
) -> tuple[DailyRecallWinner, ...]:
    candidates = (*replay.strict_shadow, *replay.near_misses)
    tiers_by_identity: dict[tuple[date, str], set[str]] = {}
    for candidate in candidates:
        identity = (
            candidate.signal_date,
            normalize_code6(candidate.code),
        )
        tiers_by_identity.setdefault(identity, set()).add(candidate.tier)
    attributed = []
    for winner in winners:
        identity = (winner.signal_date, normalize_code6(winner.code))
        tiers = tuple(sorted(tiers_by_identity.get(identity, set())))
        trace = replay.traces.get(identity)
        attributed.append(
            replace(
                winner,
                captured_tiers=tiers,
                first_rejection=(
                    None if tiers or trace is None else trace.first_rejection
                ),
            )
        )
    return tuple(
        sorted(attributed, key=lambda value: (value.signal_date, value.code))
    )


def diagnose_market_freeze_winners(
    winners: Sequence[DailyRecallWinner],
    *,
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    risk_flags: Sequence[RiskFlag],
    holding_codes_by_date: Mapping[date, frozenset[str]],
    policy: SelectionPolicy | None = None,
) -> tuple[MarketFreezeDiagnostic, ...]:
    resolved = policy or SelectionPolicy()
    normalized_bars = {
        normalize_code6(code): tuple(values)
        for code, values in bars_by_code.items()
    }
    rows = []
    for winner in winners:
        if (
            winner.captured_tiers
            or winner.first_rejection not in MARKET_FREEZE_REASONS
        ):
            continue
        bars = tuple(
            sorted(
                (
                    value
                    for value in normalized_bars.get(winner.code, ())
                    if value.trade_date <= winner.signal_date
                ),
                key=lambda value: value.trade_date,
            )[-120:]
        )
        base = base_gate(
            winner.code,
            bars,
            set(holding_codes_by_date.get(winner.signal_date, frozenset())),
            risk_flags_on(risk_flags, winner.signal_date),
            resolved,
        )
        setups = detect_setups(winner.code, bars, resolved) if base.passed else ()
        rows.append(
            MarketFreezeDiagnostic(
                winner.code,
                winner.signal_date,
                winner.first_rejection,
                base.passed,
                base.reasons,
                tuple(value.setup_type.value for value in setups),
                tuple(value.quality for value in setups),
            )
        )
    return tuple(sorted(rows, key=lambda value: (value.signal_date, value.code)))


def next_five_trading_dates(
    signal_date: date,
    trading_dates: Sequence[date],
    cutoff: date,
) -> tuple[date, ...]:
    return tuple(
        value
        for value in sorted(set(trading_dates))
        if signal_date < value <= cutoff
    )[:5]


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def find_daily_actionable_winners(
    *,
    signal_date: date,
    outcome_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    risk_flags: Sequence[RiskFlag],
    holding_codes: frozenset[str],
    policy: SelectionPolicy | None = None,
) -> DailyRecallCohort:
    resolved = policy or SelectionPolicy()
    horizon = tuple(sorted(set(outcome_dates)))
    if len(horizon) != 5:
        return DailyRecallCohort(signal_date, horizon, False, ())
    dated_flags = risk_flags_on(risk_flags, signal_date)
    vetoed = {
        code
        for code, flags in dated_flags.items()
        if any(value.severity == "VETO" for value in flags)
    }
    held = {normalize_code6(value) for value in holding_codes}
    horizon_set = frozenset(horizon)
    winners = []
    for raw_code, values in sorted(bars_by_code.items()):
        code = normalize_code6(raw_code)
        if not is_sh_sz_main_board_code(code) or code in vetoed or code in held:
            continue
        ordered = tuple(sorted(values, key=lambda value: value.trade_date))
        history = tuple(value for value in ordered if value.trade_date <= signal_date)
        if len(history) < 5 or history[-1].trade_date != signal_date:
            continue
        if _average([value.amount_qian for value in history[-5:]]) < resolved.min_average_amount5_qian:
            continue
        outcome = tuple(value for value in ordered if value.trade_date in horizon_set)
        if tuple(value.trade_date for value in outcome) != horizon:
            continue
        previous_close = history[-1].close
        selected: DailyRecallWinner | None = None
        for index, entry in enumerate(outcome):
            if (
                not entry.open.is_finite()
                or entry.open <= 0
                or not previous_close.is_finite()
                or previous_close <= 0
            ):
                previous_close = entry.close
                continue
            locked_limit_up = (
                entry.open == entry.high == entry.low == entry.close
                and entry.pct_chg >= Decimal("9.5")
            )
            gap = entry.open / previous_close - Decimal("1")
            if not locked_limit_up and gap <= Decimal("0.03"):
                forward = outcome[index:]
                maximum_high = max(value.high for value in forward)
                maximum_gain = maximum_high / entry.open - Decimal("1")
                if maximum_gain >= Decimal("0.05"):
                    maximum_date = next(
                        value.trade_date
                        for value in forward
                        if value.high == maximum_high
                    )
                    selected = DailyRecallWinner(
                        code,
                        signal_date,
                        horizon[-1],
                        entry.trade_date,
                        entry.open,
                        maximum_gain,
                        maximum_date,
                    )
                    break
            previous_close = entry.close
        if selected is not None:
            winners.append(selected)
    return DailyRecallCohort(
        signal_date,
        horizon,
        True,
        tuple(sorted(winners, key=lambda value: value.code)),
    )
