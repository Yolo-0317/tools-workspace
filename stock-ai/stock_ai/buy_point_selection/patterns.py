"""Deterministic detectors for pre-entry buy-point structures."""

from __future__ import annotations

from decimal import Decimal
from statistics import mean
from typing import Sequence

from stock_ai.market_codes import normalize_code6

from .models import BuyPointBar, DetectedSetup, SelectionPolicy, SetupType


ZERO = Decimal("0")
ONE = Decimal("1")


def _ordered(bars: Sequence[BuyPointBar]) -> tuple[BuyPointBar, ...]:
    return tuple(sorted(bars, key=lambda value: value.trade_date))


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, ZERO) / Decimal(len(values))


def _range_width(bars: Sequence[BuyPointBar]) -> Decimal:
    low = min(value.low for value in bars)
    if low <= ZERO:
        return Decimal("Infinity")
    return max(value.high for value in bars) / low - ONE


def _amount_ratio(recent: Sequence[BuyPointBar], prior: Sequence[BuyPointBar]) -> Decimal:
    prior_average = _average([value.amount_qian for value in prior])
    if prior_average <= ZERO:
        return Decimal("Infinity")
    return _average([value.amount_qian for value in recent]) / prior_average


def _moving_average(bars: Sequence[BuyPointBar], period: int, end: int | None = None) -> Decimal:
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
    return current / previous - ONE if previous > ZERO else Decimal("NaN")


def _bounded_quality(*components: Decimal) -> Decimal:
    bounded = [max(ZERO, min(ONE, value)) for value in components]
    return mean(bounded).quantize(Decimal("0.0001"))


def detect_pre_breakout(
    code: str,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy,
) -> DetectedSetup | None:
    ordered = _ordered(bars)
    if len(ordered) < policy.platform_window:
        return None
    window = ordered[-policy.platform_window :]
    platform_high = max(value.high for value in window[:-1])
    platform_low = min(value.low for value in window)
    if platform_low <= ZERO or platform_high <= ZERO:
        return None
    width = platform_high / platform_low - ONE
    distance = (platform_high - window[-1].close) / platform_high
    if width > policy.platform_width_max or not ZERO <= distance <= policy.platform_near_top_max:
        return None

    prior_range = _range_width(window[-20:-10])
    recent_range = _range_width(window[-10:])
    if prior_range <= ZERO:
        return None
    contraction = recent_range / prior_range
    turnover_ratio = _amount_ratio(window[-5:], window[-10:-5])
    ma20_slope = _ma20_slope5(ordered)
    if (
        contraction > policy.platform_contraction_max
        or turnover_ratio > policy.platform_amount_ratio_max
        or not ma20_slope.is_finite()
        or ma20_slope < ZERO
    ):
        return None

    quality = _bounded_quality(
        ONE - width / policy.platform_width_max,
        ONE - distance / policy.platform_near_top_max,
        ONE - contraction / policy.platform_contraction_max,
        ONE - turnover_ratio / policy.platform_amount_ratio_max,
    )
    return DetectedSetup(
        code=normalize_code6(code),
        setup_type=SetupType.PRE_BREAKOUT,
        analysis_date=ordered[-1].trade_date,
        structure_start=window[0].trade_date,
        structure_high=platform_high,
        structure_low=platform_low,
        quality=quality,
        reasons=("CONTRACTING_PLATFORM_NEAR_TOP",),
        metrics={
            "platform_width": width,
            "distance_to_platform_top": distance,
            "range_contraction_ratio": contraction,
            "amount_contraction_ratio": turnover_ratio,
            "ma20_slope5": ma20_slope,
        },
    )


def detect_trend_pullback(
    code: str,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy,
) -> DetectedSetup | None:
    ordered = _ordered(bars)
    if len(ordered) < 30:
        return None
    for session_count in range(2, 5):
        pullback_start = len(ordered) - session_count
        trend_end = pullback_start - 1
        trend_start = trend_end - 10
        if trend_start < 0:
            continue
        pullback = ordered[pullback_start:]
        if not any(value.pct_chg < ZERO for value in pullback):
            continue
        if any(value.pct_chg > Decimal("0.5") or abs(value.pct_chg) > Decimal("2") for value in pullback):
            continue

        base_close = ordered[trend_start].close
        peak_bar = ordered[trend_end]
        if base_close <= ZERO:
            continue
        trend_return = peak_bar.close / base_close - ONE
        drawdown = (peak_bar.high - ordered[-1].close) / peak_bar.high
        turnover_ratio = _amount_ratio(pullback, ordered[trend_start + 1 : trend_end + 1])
        ma10 = _moving_average(ordered, 10)
        ma20 = _moving_average(ordered, 20)
        if not policy.trend_return10_min <= trend_return <= policy.trend_return10_max:
            continue
        if not policy.trend_drawdown_min <= drawdown <= policy.trend_drawdown_max:
            continue
        if turnover_ratio > policy.pullback_amount_ratio_max:
            continue
        if ordered[-1].close < ma10 or ordered[-1].close < ma20:
            continue

        quality = _bounded_quality(
            ONE - abs(trend_return - Decimal("0.10")) / Decimal("0.08"),
            ONE - abs(drawdown - Decimal("0.04")) / Decimal("0.04"),
            ONE - turnover_ratio / policy.pullback_amount_ratio_max,
        )
        return DetectedSetup(
            code=normalize_code6(code),
            setup_type=SetupType.TREND_PULLBACK,
            analysis_date=ordered[-1].trade_date,
            structure_start=pullback[0].trade_date,
            structure_high=max(value.high for value in pullback),
            structure_low=min(value.low for value in pullback),
            quality=quality,
            reasons=("ORDERLY_LOW_VOLUME_PULLBACK",),
            metrics={
                "trend_return10": trend_return,
                "pullback_sessions": Decimal(session_count),
                "pullback_drawdown": drawdown,
                "pullback_amount_ratio": turnover_ratio,
                "ma10": ma10,
                "ma20": ma20,
            },
        )
    return None


def detect_first_launch_pullback(
    code: str,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy,
) -> DetectedSetup | None:
    ordered = _ordered(bars)
    if len(ordered) < 10:
        return None
    for quiet_sessions in (1, 2):
        launch_index = len(ordered) - quiet_sessions - 1
        launch = ordered[launch_index]
        preceding = ordered[launch_index - 5 : launch_index]
        quiet = ordered[launch_index + 1 :]
        if len(preceding) != 5:
            continue
        launch_gain = launch.pct_chg / Decimal("100")
        launch_amount_ratio = launch.amount_qian / _average([value.amount_qian for value in preceding])
        launch_range = launch.high - launch.low
        if launch_range <= ZERO:
            continue
        close_location = (launch.close - launch.low) / launch_range
        preceding_return = preceding[-1].close / preceding[0].close - ONE
        preceding_three_up = all(value.pct_chg > ZERO for value in preceding[-3:])
        if not policy.launch_gain_min <= launch_gain <= policy.launch_gain_max:
            continue
        if not policy.launch_amount_ratio_min <= launch_amount_ratio <= policy.launch_amount_ratio_max:
            continue
        if close_location < policy.launch_close_location_min or preceding_return > Decimal("0.05"):
            continue
        if preceding_three_up:
            continue
        if any(
            abs(value.pct_chg / Decimal("100")) > policy.consolidation_gain_abs_max
            or value.amount_qian / launch.amount_qian > policy.consolidation_amount_ratio_max
            for value in quiet
        ):
            continue

        quiet_amount_ratio = max(value.amount_qian / launch.amount_qian for value in quiet)
        quality = _bounded_quality(
            ONE - abs(launch_gain - Decimal("0.035")) / Decimal("0.015"),
            close_location,
            ONE - quiet_amount_ratio / policy.consolidation_amount_ratio_max,
        )
        structure = (launch, *quiet)
        return DetectedSetup(
            code=normalize_code6(code),
            setup_type=SetupType.FIRST_LAUNCH_PULLBACK,
            analysis_date=ordered[-1].trade_date,
            structure_start=launch.trade_date,
            structure_high=max(value.high for value in quiet),
            structure_low=min(value.low for value in structure),
            quality=quality,
            reasons=("FIRST_LAUNCH_WITH_QUIET_PULLBACK",),
            metrics={
                "launch_gain_pct": launch_gain,
                "launch_amount_ratio": launch_amount_ratio,
                "launch_close_location": close_location,
                "preceding_return5": preceding_return,
                "quiet_sessions": Decimal(quiet_sessions),
                "quiet_amount_ratio": quiet_amount_ratio,
            },
        )
    return None


def detect_setups(
    code: str,
    bars: Sequence[BuyPointBar],
    policy: SelectionPolicy | None = None,
) -> tuple[DetectedSetup, ...]:
    resolved = policy or SelectionPolicy()
    detectors = (
        detect_pre_breakout,
        detect_trend_pullback,
        detect_first_launch_pullback,
    )
    return tuple(
        setup
        for detector in detectors
        if (setup := detector(code, bars, resolved)) is not None
    )
