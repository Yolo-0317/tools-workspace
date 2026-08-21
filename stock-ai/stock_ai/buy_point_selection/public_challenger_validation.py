"""Frozen validation mathematics for the public strategy challenger."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
import hashlib
import math
import random
from typing import Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .five_day_ranking_v3_attribution import wilson_interval
from .public_challenger_execution import ChallengerTrade
from .public_challenger_signals import ChallengerSignal
from .validation import ChronologicalSplit


_RESOLVED_STATUSES = frozenset(
    {"STOPPED", "TIME_EXIT_GAIN", "TIME_EXIT_FLAT", "TIME_EXIT_LOSS"}
)


@dataclass(frozen=True)
class ChallengerObservation:
    signal: ChallengerSignal
    trade: ChallengerTrade
    selected: bool
    resolution_date: date


@dataclass(frozen=True)
class ChallengerSegmentMetrics:
    segment: str
    triggered_resolved: int
    net_expectancy: Decimal
    profit_factor: Decimal | None
    profitable_wilson_lower: Decimal
    stop_rate: Decimal
    positive_window_ratio: Decimal
    maximum_drawdown: Decimal
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ChallengerPortfolioMetrics:
    accepted_trades: int
    maximum_drawdown: Decimal
    maximum_stock_trade_share: Decimal
    maximum_stock_profit_share: Decimal
    maximum_sector_trade_share: Decimal
    maximum_sector_profit_share: Decimal
    top5_profit_share: Decimal
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceTrackMetrics:
    loser_net_expectancy: Decimal
    winner_net_expectancy: Decimal
    long_short_spread: Decimal
    long_only_net_expectancy: Decimal
    long_only_eligible: bool


@dataclass(frozen=True)
class V3ComparableDay:
    signal_date: date
    selected_keys: frozenset[str]
    net_return: Decimal


@dataclass(frozen=True)
class V3ComparableArtifact:
    schema: str
    parent_research_identity: str
    input_fingerprint: str
    split_identity: str
    days: tuple[V3ComparableDay, ...]


@dataclass(frozen=True)
class PairedComparison:
    paired_dates: int
    mean_difference: Decimal | None
    confidence_interval: tuple[Decimal, Decimal] | None
    jaccard: Decimal | None
    incremental_resolved: int
    incremental_expectancy: Decimal | None
    incremental_profit_factor: Decimal | None


@dataclass(frozen=True)
class ChallengerAssessment:
    execution_metrics: ChallengerSegmentMetrics
    portfolio_metrics: ChallengerPortfolioMetrics
    paired: PairedComparison | None
    verdict: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PublicChallengerResearchReview:
    split: ChronologicalSplit
    input_fingerprint: str
    track_metrics: Mapping[str, ChallengerSegmentMetrics]
    validation_assessment: ChallengerAssessment
    funnel_counts: Mapping[str, int]
    point_in_time_complete: bool
    test_outcomes_read: bool = False
    trade_permission: str = "NO-TRADE"


@dataclass(frozen=True)
class PublicChallengerValidationReview:
    parent_research_identity: str
    input_fingerprint: str
    assessment: ChallengerAssessment
    test_eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PublicChallengerFreezeReview:
    parent_research_identity: str
    input_fingerprint: str
    split_identity: str
    frozen_rule_hash: str
    test_eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PublicChallengerTestReview:
    parent_freeze_identity: str
    parent_research_identity: str
    input_fingerprint: str
    assessment: ChallengerAssessment
    trade_permission: str = "NO-TRADE"


def _mean(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    with localcontext() as context:
        context.prec = 50
        return sum(values, Decimal("0")) / Decimal(len(values))


def _calendar(values: Sequence[date]) -> tuple[date, ...]:
    dates = tuple(values)
    if not dates or any(
        current >= following for current, following in zip(dates, dates[1:])
    ):
        raise ValueError("TRADING_DATES_NOT_STRICT")
    return dates


def _resolved(
    observations: Sequence[ChallengerObservation],
) -> tuple[ChallengerObservation, ...]:
    result: list[ChallengerObservation] = []
    for row in observations:
        if (
            row.trade.track_id != row.signal.track_id
            or row.trade.signal_date != row.signal.signal_date
        ):
            raise ValueError("OBSERVATION_SIGNAL_TRADE_MISMATCH")
        if row.trade.exit_date is not None and row.trade.exit_date != row.resolution_date:
            raise ValueError("OBSERVATION_RESOLUTION_DATE_MISMATCH")
        if (
            row.selected
            and row.trade.status in _RESOLVED_STATUSES
            and row.trade.net_return is not None
        ):
            if not row.trade.net_return.is_finite() or row.trade.net_return <= Decimal("-1"):
                raise ValueError("OBSERVATION_RETURN_INVALID")
            result.append(row)
    return tuple(
        sorted(
            result,
            key=lambda row: (
                row.resolution_date,
                normalize_code6(row.signal.code),
                row.signal.track_id,
            ),
        )
    )


def _profit_factor(values: Sequence[Decimal]) -> Decimal | None:
    gross_profit = sum((value for value in values if value > 0), Decimal("0"))
    gross_loss = abs(sum((value for value in values if value < 0), Decimal("0")))
    if gross_profit <= 0 or gross_loss <= 0:
        return None
    with localcontext() as context:
        context.prec = 50
        return gross_profit / gross_loss


def _daily_returns(
    observations: Sequence[ChallengerObservation],
) -> dict[date, Decimal]:
    grouped: dict[date, list[Decimal]] = defaultdict(list)
    for row in observations:
        if row.trade.net_return is not None:
            grouped[row.resolution_date].append(row.trade.net_return)
    return {
        trade_date: _mean(values)
        for trade_date, values in sorted(grouped.items())
    }


def _maximum_drawdown(
    observations: Sequence[ChallengerObservation],
) -> Decimal:
    equity = Decimal("1")
    peak = equity
    maximum = Decimal("0")
    for value in _daily_returns(observations).values():
        equity *= Decimal("1") + value
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, (peak - equity) / peak)
    return maximum


def _positive_window_ratio(
    observations: Sequence[ChallengerObservation],
    trading_dates: Sequence[date],
) -> Decimal:
    dates = _calendar(trading_dates)
    if len(dates) < 63:
        return Decimal("0")
    by_date = _daily_returns(observations)
    positive = 0
    windows = len(dates) - 62
    for start in range(windows):
        returns = tuple(
            by_date[trade_date]
            for trade_date in dates[start : start + 63]
            if trade_date in by_date
        )
        if returns and _mean(returns) > 0:
            positive += 1
    return Decimal(positive) / Decimal(windows)


def evaluate_execution_segment(
    observations: Sequence[ChallengerObservation],
    trading_dates: Sequence[date],
    segment: str,
) -> ChallengerSegmentMetrics:
    resolved = _resolved(observations)
    values = tuple(row.trade.net_return for row in resolved if row.trade.net_return is not None)
    winners = sum(value > 0 for value in values)
    profit_factor = _profit_factor(values)
    wilson_lower = wilson_interval(winners, len(values))[0] if values else Decimal("0")
    stop_rate = (
        Decimal(sum(row.trade.status == "STOPPED" for row in resolved))
        / Decimal(len(resolved))
        if resolved
        else Decimal("0")
    )
    net_expectancy = _mean(values)
    positive_window_ratio = _positive_window_ratio(resolved, trading_dates)
    maximum_drawdown = _maximum_drawdown(resolved)
    reasons: list[str] = []
    if len(resolved) < 30:
        reasons.append("SEGMENT_SAMPLES_TOO_LOW")
    if net_expectancy <= 0:
        reasons.append("NON_POSITIVE_EXPECTANCY")
    if profit_factor is None or profit_factor <= Decimal("1.10"):
        reasons.append("PROFIT_FACTOR_TOO_LOW")
    if wilson_lower < Decimal("0.45"):
        reasons.append("WILSON_LOWER_TOO_LOW")
    if stop_rate > Decimal("0.40"):
        reasons.append("STOP_RATE_TOO_HIGH")
    if positive_window_ratio < Decimal("0.60"):
        reasons.append("POSITIVE_WINDOW_RATIO_TOO_LOW")
    if maximum_drawdown > Decimal("0.10"):
        reasons.append("MAXIMUM_DRAWDOWN_TOO_HIGH")
    return ChallengerSegmentMetrics(
        segment=segment,
        triggered_resolved=len(resolved),
        net_expectancy=net_expectancy,
        profit_factor=profit_factor,
        profitable_wilson_lower=wilson_lower,
        stop_rate=stop_rate,
        positive_window_ratio=positive_window_ratio,
        maximum_drawdown=maximum_drawdown,
        qualifies=not reasons,
        reasons=tuple(reasons),
    )


def evaluate_portfolio_metrics(
    observations: Sequence[ChallengerObservation],
) -> ChallengerPortfolioMetrics:
    accepted = _resolved(observations)
    trade_count = len(accepted)
    stock_trades = Counter(normalize_code6(row.signal.code) for row in accepted)
    sector_trades = Counter(row.signal.sector_code for row in accepted)
    profits_by_stock: dict[str, Decimal] = defaultdict(Decimal)
    profits_by_sector: dict[str, Decimal] = defaultdict(Decimal)
    positive_returns: list[Decimal] = []
    for row in accepted:
        value = row.trade.net_return
        if value is not None and value > 0:
            code = normalize_code6(row.signal.code)
            profits_by_stock[code] += value
            profits_by_sector[row.signal.sector_code] += value
            positive_returns.append(value)
    gross_profit = sum(positive_returns, Decimal("0"))

    def count_share(values: Counter[str]) -> Decimal:
        return (
            Decimal(max(values.values())) / Decimal(trade_count)
            if trade_count and values
            else Decimal("0")
        )

    def profit_share(values: Mapping[str, Decimal]) -> Decimal:
        return (
            max(values.values()) / gross_profit
            if gross_profit > 0 and values
            else Decimal("0")
        )

    top5_profit_share = (
        sum(sorted(positive_returns, reverse=True)[:5], Decimal("0"))
        / gross_profit
        if gross_profit > 0
        else Decimal("0")
    )
    maximum_drawdown = _maximum_drawdown(accepted)
    maximum_stock_trade_share = count_share(stock_trades)
    maximum_stock_profit_share = profit_share(profits_by_stock)
    maximum_sector_trade_share = count_share(sector_trades)
    maximum_sector_profit_share = profit_share(profits_by_sector)
    reasons: list[str] = []
    if trade_count <= 0:
        reasons.append("NO_ACCEPTED_TRADES")
    if gross_profit <= 0:
        reasons.append("GROSS_PROFIT_UNAVAILABLE")
    if maximum_drawdown > Decimal("0.10"):
        reasons.append("MAXIMUM_DRAWDOWN_TOO_HIGH")
    if maximum_stock_trade_share > Decimal("0.10"):
        reasons.append("STOCK_TRADE_CONCENTRATION_TOO_HIGH")
    if maximum_stock_profit_share > Decimal("0.15"):
        reasons.append("STOCK_PROFIT_CONCENTRATION_TOO_HIGH")
    if maximum_sector_trade_share > Decimal("0.35"):
        reasons.append("SECTOR_TRADE_CONCENTRATION_TOO_HIGH")
    if maximum_sector_profit_share > Decimal("0.40"):
        reasons.append("SECTOR_PROFIT_CONCENTRATION_TOO_HIGH")
    if top5_profit_share > Decimal("0.35"):
        reasons.append("TOP5_PROFIT_CONCENTRATION_TOO_HIGH")
    return ChallengerPortfolioMetrics(
        accepted_trades=trade_count,
        maximum_drawdown=maximum_drawdown,
        maximum_stock_trade_share=maximum_stock_trade_share,
        maximum_stock_profit_share=maximum_stock_profit_share,
        maximum_sector_trade_share=maximum_sector_trade_share,
        maximum_sector_profit_share=maximum_sector_profit_share,
        top5_profit_share=top5_profit_share,
        qualifies=not reasons,
        reasons=tuple(reasons),
    )


def evaluate_reference_track(
    observations: Sequence[ChallengerObservation],
) -> ReferenceTrackMetrics:
    resolved = _resolved(observations)
    losers = tuple(
        row.trade.net_return
        for row in resolved
        if row.signal.reference_bucket == "LOSER" and row.trade.net_return is not None
    )
    winners = tuple(
        row.trade.net_return
        for row in resolved
        if row.signal.reference_bucket == "WINNER" and row.trade.net_return is not None
    )
    loser_expectancy = _mean(losers)
    winner_expectancy = _mean(winners)
    return ReferenceTrackMetrics(
        loser_net_expectancy=loser_expectancy,
        winner_net_expectancy=winner_expectancy,
        long_short_spread=loser_expectancy - winner_expectancy,
        long_only_net_expectancy=loser_expectancy,
        long_only_eligible=bool(losers) and loser_expectancy > 0,
    )


def moving_block_bootstrap_interval(
    values: Sequence[Decimal],
    *,
    block_size: int,
    samples: int,
    seed_material: str,
) -> tuple[Decimal, Decimal]:
    resolved = tuple(values)
    if (
        block_size <= 0
        or samples <= 0
        or len(resolved) < block_size
        or any(not value.is_finite() for value in resolved)
    ):
        raise ValueError("PAIRED_SAMPLE_INSUFFICIENT")
    seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)
    blocks = tuple(
        tuple(
            resolved[(start + offset) % len(resolved)]
            for offset in range(block_size)
        )
        for start in range(len(resolved))
    )
    draws_per_sample = math.ceil(len(resolved) / block_size)
    means: list[Decimal] = []
    for _ in range(samples):
        draw = tuple(
            item
            for _ in range(draws_per_sample)
            for item in blocks[rng.randrange(len(blocks))]
        )[: len(resolved)]
        means.append(_mean(draw))
    ordered = tuple(sorted(means))
    lower_index = max(0, math.ceil(samples * 0.025) - 1)
    upper_index = min(samples - 1, math.ceil(samples * 0.975) - 1)
    return ordered[lower_index], ordered[upper_index]


def _return_path_drawdown(values: Sequence[Decimal]) -> Decimal:
    equity = Decimal("1")
    peak = equity
    maximum = Decimal("0")
    for value in values:
        if not value.is_finite() or value <= Decimal("-1"):
            raise ValueError("COMPARABLE_RETURN_INVALID")
        equity *= Decimal("1") + value
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, (peak - equity) / peak)
    return maximum


def _v3_qualifies(days: Sequence[V3ComparableDay]) -> bool:
    active = tuple(row for row in days if row.selected_keys)
    values = tuple(row.net_return for row in active)
    if len(values) < 30:
        return False
    profit_factor = _profit_factor(values)
    winners = sum(value > 0 for value in values)
    if (
        _mean(values) <= 0
        or profit_factor is None
        or profit_factor <= Decimal("1.10")
        or wilson_interval(winners, len(values))[0] < Decimal("0.45")
        or _return_path_drawdown(values) > Decimal("0.10")
    ):
        return False
    if len(days) < 63:
        return False
    positive_windows = 0
    windows = len(days) - 62
    for start in range(windows):
        window = tuple(
            row.net_return
            for row in days[start : start + 63]
            if row.selected_keys
        )
        if window and _mean(window) > 0:
            positive_windows += 1
    return Decimal(positive_windows) / Decimal(windows) >= Decimal("0.60")


def _paired_comparison(
    challenger: Sequence[ChallengerObservation],
    v3_days: Sequence[V3ComparableDay],
    *,
    input_fingerprint: str,
) -> PairedComparison:
    resolved = _resolved(challenger)
    challenger_by_date: dict[date, list[ChallengerObservation]] = defaultdict(list)
    for row in resolved:
        challenger_by_date[row.signal.signal_date].append(row)
    ordered_v3 = tuple(v3_days)
    if any(
        current.signal_date >= following.signal_date
        for current, following in zip(ordered_v3, ordered_v3[1:])
    ):
        raise ValueError("V3_COMPARABLE_DATES_NOT_STRICT")
    if any(not row.net_return.is_finite() for row in ordered_v3):
        raise ValueError("V3_COMPARABLE_RETURN_INVALID")
    v3_by_date = {row.signal_date: row for row in ordered_v3}
    if any(trade_date not in v3_by_date for trade_date in challenger_by_date):
        raise ValueError("V3_COMPARABLE_COVERAGE_INCOMPLETE")
    differences: list[Decimal] = []
    challenger_opportunities: set[tuple[date, str]] = set()
    v3_opportunities: set[tuple[date, str]] = set()
    incremental: list[ChallengerObservation] = []
    for v3_day in ordered_v3:
        challenger_rows = tuple(challenger_by_date.get(v3_day.signal_date, ()))
        challenger_keys = frozenset(row.signal.code for row in challenger_rows)
        challenger_return = _mean(
            tuple(
                row.trade.net_return
                for row in challenger_rows
                if row.trade.net_return is not None
            )
        )
        challenger_opportunities.update(
            (v3_day.signal_date, key) for key in challenger_keys
        )
        v3_opportunities.update(
            (v3_day.signal_date, key) for key in v3_day.selected_keys
        )
        incremental.extend(
            row
            for row in challenger_rows
            if row.signal.code not in v3_day.selected_keys
        )
        if challenger_keys or v3_day.selected_keys:
            differences.append(challenger_return - v3_day.net_return)
    union = challenger_opportunities | v3_opportunities
    jaccard = (
        Decimal(len(challenger_opportunities & v3_opportunities))
        / Decimal(len(union))
        if union
        else None
    )
    incremental_values = tuple(
        row.trade.net_return
        for row in incremental
        if row.trade.net_return is not None
    )
    return PairedComparison(
        paired_dates=len(differences),
        mean_difference=_mean(differences) if differences else None,
        confidence_interval=(
            moving_block_bootstrap_interval(
                differences,
                block_size=5,
                samples=10_000,
                seed_material=input_fingerprint,
            )
            if len(differences) >= 5
            else None
        ),
        jaccard=jaccard,
        incremental_resolved=len(incremental_values),
        incremental_expectancy=(
            _mean(incremental_values) if incremental_values else None
        ),
        incremental_profit_factor=_profit_factor(incremental_values),
    )


def compare_with_v3(
    *,
    challenger: Sequence[ChallengerObservation],
    v3_days: Sequence[V3ComparableDay] | None,
    trading_dates: Sequence[date],
    segment: str,
    input_fingerprint: str,
) -> ChallengerAssessment:
    if not input_fingerprint:
        raise ValueError("INPUT_FINGERPRINT_EMPTY")
    if segment not in {"VALIDATION", "TEST"}:
        raise ValueError("SEGMENT_INVALID")
    calendar = _calendar(trading_dates)
    if (
        v3_days is not None
        and tuple(row.signal_date for row in v3_days) != calendar
    ):
        raise ValueError("V3_CALENDAR_MISMATCH")
    execution_metrics = evaluate_execution_segment(
        challenger,
        trading_dates=calendar,
        segment=segment,
    )
    portfolio_metrics = evaluate_portfolio_metrics(challenger)
    if v3_days is None:
        return ChallengerAssessment(
            execution_metrics=execution_metrics,
            portfolio_metrics=portfolio_metrics,
            paired=None,
            verdict="INCONCLUSIVE",
            reasons=("V3_COMPARABLE_MISSING",),
        )
    ordered_v3 = tuple(v3_days)
    paired = _paired_comparison(
        challenger,
        ordered_v3,
        input_fingerprint=input_fingerprint,
    )
    interval = paired.confidence_interval
    challenger_passes = execution_metrics.qualifies and portfolio_metrics.qualifies
    v3_passes = _v3_qualifies(ordered_v3)
    v3_drawdown = _return_path_drawdown(
        tuple(row.net_return for row in ordered_v3 if row.selected_keys)
    )
    drawdown_acceptable = (
        portfolio_metrics.maximum_drawdown
        <= v3_drawdown + Decimal("0.02")
    )
    if (
        challenger_passes
        and interval is not None
        and interval[0] > 0
        and drawdown_acceptable
    ):
        verdict = "CHALLENGER_WINS"
        reasons: tuple[str, ...] = ()
    elif (
        challenger_passes
        and interval is not None
        and interval[0] <= 0 <= interval[1]
        and paired.jaccard is not None
        and paired.jaccard <= Decimal("0.50")
        and paired.incremental_resolved >= 30
        and paired.incremental_expectancy is not None
        and paired.incremental_expectancy > 0
        and paired.incremental_profit_factor is not None
        and paired.incremental_profit_factor > Decimal("1.10")
    ):
        verdict = "COMPLEMENTARY"
        reasons = ()
    elif v3_passes and (
        not challenger_passes
        or (interval is not None and interval[1] < 0)
        or (not drawdown_acceptable and (interval is None or interval[0] <= 0))
    ):
        verdict = "V3_RETAINS"
        reasons = tuple(execution_metrics.reasons + portfolio_metrics.reasons)
    else:
        verdict = "INCONCLUSIVE"
        reasons = ("FROZEN_VERDICT_THRESHOLDS_NOT_MET",)
    return ChallengerAssessment(
        execution_metrics=execution_metrics,
        portfolio_metrics=portfolio_metrics,
        paired=paired,
        verdict=verdict,
        reasons=reasons,
    )
