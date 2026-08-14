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


@dataclass(frozen=True)
class SetupTemplateDiagnostic:
    code: str
    signal_date: date
    template: str
    window_sessions: int | None
    failures: tuple[str, ...]
    boundary_deviation: Decimal
    metrics: Mapping[str, Decimal]
    executable_shares: int = 0


MARKET_FREEZE_REASONS = frozenset(
    {"INDEX_AND_BREADTH_WEAK", "AMOUNT_AND_BREADTH_WEAK"}
)


def _range_width(bars: Sequence[BuyPointBar]) -> Decimal:
    low = min(value.low for value in bars)
    if low <= 0:
        return Decimal("Infinity")
    return max(value.high for value in bars) / low - Decimal("1")


def _amount_ratio(
    recent: Sequence[BuyPointBar],
    prior: Sequence[BuyPointBar],
) -> Decimal:
    prior_average = _average([value.amount_qian for value in prior])
    if prior_average <= 0:
        return Decimal("Infinity")
    return _average([value.amount_qian for value in recent]) / prior_average


def _moving_average(
    bars: Sequence[BuyPointBar],
    period: int,
    end: int | None = None,
) -> Decimal:
    resolved_end = len(bars) if end is None else end
    start = resolved_end - period
    if start < 0:
        return Decimal("NaN")
    return _average([value.close for value in bars[start:resolved_end]])


def _ma20_slope5(bars: Sequence[BuyPointBar]) -> Decimal:
    if len(bars) < 25:
        return Decimal("NaN")
    current = _moving_average(bars, 20)
    previous = _moving_average(bars, 20, len(bars) - 5)
    return current / previous - Decimal("1") if previous > 0 else Decimal("NaN")


def _above_deviation(value: Decimal, maximum: Decimal) -> Decimal:
    if not value.is_finite() or maximum <= 0:
        return Decimal("Infinity")
    return max(Decimal("0"), value - maximum) / maximum


def _below_deviation(value: Decimal, minimum: Decimal) -> Decimal:
    if not value.is_finite() or minimum <= 0:
        return Decimal("Infinity")
    return max(Decimal("0"), minimum - value) / minimum


def _platform_diagnostic(
    code: str,
    signal_date: date,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy,
) -> SetupTemplateDiagnostic:
    if len(bars) < policy.platform_window:
        return SetupTemplateDiagnostic(
            code,
            signal_date,
            "PRE_BREAKOUT",
            policy.platform_window,
            ("PLATFORM_HISTORY_SHORT",),
            Decimal("Infinity"),
            {},
        )
    window = bars[-policy.platform_window :]
    platform_high = max(value.high for value in window[:-1])
    platform_low = min(value.low for value in window)
    if platform_low <= 0 or platform_high <= 0:
        return SetupTemplateDiagnostic(
            code,
            signal_date,
            "PRE_BREAKOUT",
            policy.platform_window,
            ("PLATFORM_INVALID_PRICE",),
            Decimal("Infinity"),
            {},
        )
    width = platform_high / platform_low - Decimal("1")
    distance = (platform_high - window[-1].close) / platform_high
    prior_range = _range_width(window[-20:-10])
    recent_range = _range_width(window[-10:])
    contraction = (
        recent_range / prior_range
        if prior_range.is_finite() and prior_range > 0
        else Decimal("Infinity")
    )
    turnover_ratio = _amount_ratio(window[-5:], window[-10:-5])
    ma20_slope = _ma20_slope5(bars)
    failures = []
    deviation = Decimal("0")
    if width > policy.platform_width_max:
        failures.append("PLATFORM_WIDTH_WIDE")
        deviation += _above_deviation(width, policy.platform_width_max)
    if not Decimal("0") <= distance <= policy.platform_near_top_max:
        failures.append("PLATFORM_NOT_NEAR_TOP")
        deviation += (
            abs(distance) / policy.platform_near_top_max
            if distance < 0
            else _above_deviation(distance, policy.platform_near_top_max)
        )
    if contraction > policy.platform_contraction_max:
        failures.append("PLATFORM_RANGE_NOT_CONTRACTED")
        deviation += _above_deviation(contraction, policy.platform_contraction_max)
    if turnover_ratio > policy.platform_amount_ratio_max:
        failures.append("PLATFORM_AMOUNT_NOT_CONTRACTED")
        deviation += _above_deviation(
            turnover_ratio,
            policy.platform_amount_ratio_max,
        )
    if not ma20_slope.is_finite() or ma20_slope < 0:
        failures.append("PLATFORM_MA20_NOT_RISING")
        deviation += Decimal("1") if ma20_slope.is_finite() else Decimal("Infinity")
    return SetupTemplateDiagnostic(
        code,
        signal_date,
        "PRE_BREAKOUT",
        policy.platform_window,
        tuple(failures),
        deviation,
        {
            "platform_width": width,
            "distance_to_platform_top": distance,
            "range_contraction_ratio": contraction,
            "amount_contraction_ratio": turnover_ratio,
            "ma20_slope5": ma20_slope,
        },
    )


def _trend_window_diagnostic(
    code: str,
    signal_date: date,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy,
    session_count: int,
) -> SetupTemplateDiagnostic:
    pullback_start = len(bars) - session_count
    trend_end = pullback_start - 1
    trend_start = trend_end - 10
    if trend_start < 0:
        return SetupTemplateDiagnostic(
            code,
            signal_date,
            "TREND_PULLBACK",
            session_count,
            ("TREND_HISTORY_SHORT",),
            Decimal("Infinity"),
            {},
        )
    pullback = bars[pullback_start:]
    base_close = bars[trend_start].close
    peak_bar = bars[trend_end]
    trend_return = (
        peak_bar.close / base_close - Decimal("1")
        if base_close > 0
        else Decimal("NaN")
    )
    drawdown = (
        (peak_bar.high - bars[-1].close) / peak_bar.high
        if peak_bar.high > 0
        else Decimal("NaN")
    )
    turnover_ratio = _amount_ratio(
        pullback,
        bars[trend_start + 1 : trend_end + 1],
    )
    ma10 = _moving_average(bars, 10)
    ma20 = _moving_average(bars, 20)
    failures = []
    deviation = Decimal("0")
    if not any(value.pct_chg < 0 for value in pullback):
        failures.append("TREND_NO_NEGATIVE_PULLBACK")
        deviation += Decimal("1")
    if any(value.pct_chg > Decimal("0.5") or abs(value.pct_chg) > Decimal("2") for value in pullback):
        failures.append("TREND_PULLBACK_BAR_DISORDERLY")
        deviation += Decimal("1")
    if not policy.trend_return10_min <= trend_return <= policy.trend_return10_max:
        failures.append("TREND_RETURN_OUT_OF_RANGE")
        deviation += (
            _below_deviation(trend_return, policy.trend_return10_min)
            if trend_return < policy.trend_return10_min
            else _above_deviation(trend_return, policy.trend_return10_max)
        )
    if not policy.trend_drawdown_min <= drawdown <= policy.trend_drawdown_max:
        failures.append("TREND_DRAWDOWN_OUT_OF_RANGE")
        deviation += (
            _below_deviation(drawdown, policy.trend_drawdown_min)
            if drawdown < policy.trend_drawdown_min
            else _above_deviation(drawdown, policy.trend_drawdown_max)
        )
    if turnover_ratio > policy.pullback_amount_ratio_max:
        failures.append("TREND_AMOUNT_NOT_CONTRACTED")
        deviation += _above_deviation(
            turnover_ratio,
            policy.pullback_amount_ratio_max,
        )
    if bars[-1].close < ma10:
        failures.append("TREND_CLOSE_BELOW_MA10")
        deviation += _below_deviation(bars[-1].close, ma10)
    if bars[-1].close < ma20:
        failures.append("TREND_CLOSE_BELOW_MA20")
        deviation += _below_deviation(bars[-1].close, ma20)
    return SetupTemplateDiagnostic(
        code,
        signal_date,
        "TREND_PULLBACK",
        session_count,
        tuple(failures),
        deviation,
        {
            "trend_return10": trend_return,
            "pullback_sessions": Decimal(session_count),
            "pullback_drawdown": drawdown,
            "pullback_amount_ratio": turnover_ratio,
            "ma10": ma10,
            "ma20": ma20,
        },
    )


def _launch_window_diagnostic(
    code: str,
    signal_date: date,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy,
    quiet_sessions: int,
) -> SetupTemplateDiagnostic:
    launch_index = len(bars) - quiet_sessions - 1
    preceding = bars[launch_index - 5 : launch_index]
    if launch_index < 0 or len(preceding) != 5:
        return SetupTemplateDiagnostic(
            code,
            signal_date,
            "FIRST_LAUNCH_PULLBACK",
            quiet_sessions,
            ("LAUNCH_HISTORY_SHORT",),
            Decimal("Infinity"),
            {},
        )
    launch = bars[launch_index]
    quiet = bars[launch_index + 1 :]
    launch_gain = launch.pct_chg / Decimal("100")
    prior_amount = _average([value.amount_qian for value in preceding])
    launch_amount_ratio = (
        launch.amount_qian / prior_amount
        if prior_amount > 0
        else Decimal("Infinity")
    )
    launch_range = launch.high - launch.low
    close_location = (
        (launch.close - launch.low) / launch_range
        if launch_range > 0
        else Decimal("NaN")
    )
    preceding_return = (
        preceding[-1].close / preceding[0].close - Decimal("1")
        if preceding[0].close > 0
        else Decimal("NaN")
    )
    preceding_three_up = all(value.pct_chg > 0 for value in preceding[-3:])
    quiet_amount_ratio = max(
        (value.amount_qian / launch.amount_qian for value in quiet),
        default=Decimal("Infinity"),
    ) if launch.amount_qian > 0 else Decimal("Infinity")
    quiet_max_abs_gain = max(
        (abs(value.pct_chg / Decimal("100")) for value in quiet),
        default=Decimal("Infinity"),
    )
    failures = []
    deviation = Decimal("0")
    if not policy.launch_gain_min <= launch_gain <= policy.launch_gain_max:
        failures.append("LAUNCH_GAIN_OUT_OF_RANGE")
        deviation += (
            _below_deviation(launch_gain, policy.launch_gain_min)
            if launch_gain < policy.launch_gain_min
            else _above_deviation(launch_gain, policy.launch_gain_max)
        )
    if not policy.launch_amount_ratio_min <= launch_amount_ratio <= policy.launch_amount_ratio_max:
        failures.append("LAUNCH_AMOUNT_OUT_OF_RANGE")
        deviation += (
            _below_deviation(launch_amount_ratio, policy.launch_amount_ratio_min)
            if launch_amount_ratio < policy.launch_amount_ratio_min
            else _above_deviation(launch_amount_ratio, policy.launch_amount_ratio_max)
        )
    if not close_location.is_finite() or close_location < policy.launch_close_location_min:
        failures.append("LAUNCH_CLOSE_LOCATION_LOW")
        deviation += _below_deviation(close_location, policy.launch_close_location_min)
    if not preceding_return.is_finite() or preceding_return > Decimal("0.05"):
        failures.append("LAUNCH_PRECEDING_RETURN_HIGH")
        deviation += _above_deviation(preceding_return, Decimal("0.05"))
    if preceding_three_up:
        failures.append("LAUNCH_PRECEDING_THREE_UP")
        deviation += Decimal("1")
    if quiet_max_abs_gain > policy.consolidation_gain_abs_max:
        failures.append("LAUNCH_QUIET_PRICE_LOUD")
        deviation += _above_deviation(
            quiet_max_abs_gain,
            policy.consolidation_gain_abs_max,
        )
    if quiet_amount_ratio > policy.consolidation_amount_ratio_max:
        failures.append("LAUNCH_QUIET_AMOUNT_LOUD")
        deviation += _above_deviation(
            quiet_amount_ratio,
            policy.consolidation_amount_ratio_max,
        )
    return SetupTemplateDiagnostic(
        code,
        signal_date,
        "FIRST_LAUNCH_PULLBACK",
        quiet_sessions,
        tuple(failures),
        deviation,
        {
            "launch_gain_pct": launch_gain,
            "launch_amount_ratio": launch_amount_ratio,
            "launch_close_location": close_location,
            "preceding_return5": preceding_return,
            "quiet_sessions": Decimal(quiet_sessions),
            "quiet_max_abs_gain": quiet_max_abs_gain,
            "quiet_amount_ratio": quiet_amount_ratio,
        },
    )


def diagnose_setup_windows(
    code: str,
    signal_date: date,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy | None = None,
) -> tuple[SetupTemplateDiagnostic, ...]:
    resolved = policy or SelectionPolicy()
    normalized = normalize_code6(code)
    bounded = tuple(
        sorted(
            (value for value in bars if value.trade_date <= signal_date),
            key=lambda value: value.trade_date,
        )[-120:]
    )
    return (
        _platform_diagnostic(normalized, signal_date, bounded, resolved),
        *(
            _trend_window_diagnostic(
                normalized,
                signal_date,
                bounded,
                resolved,
                sessions,
            )
            for sessions in range(2, 5)
        ),
        *(
            _launch_window_diagnostic(
                normalized,
                signal_date,
                bounded,
                resolved,
                sessions,
            )
            for sessions in (1, 2)
        ),
    )


def diagnose_no_setup(
    code: str,
    signal_date: date,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy | None = None,
) -> tuple[SetupTemplateDiagnostic, ...]:
    windows = diagnose_setup_windows(code, signal_date, bars, policy)
    trend = min(
        windows[1:4],
        key=lambda value: (
            len(value.failures),
            value.boundary_deviation,
            value.window_sessions or 0,
        ),
    )
    launch = min(
        windows[4:6],
        key=lambda value: (
            len(value.failures),
            value.boundary_deviation,
            value.window_sessions or 0,
        ),
    )
    return windows[0], trend, launch


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
