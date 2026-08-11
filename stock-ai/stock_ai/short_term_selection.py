"""Pure, completed-bar short-term candidate selection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date
import re
from typing import Literal, Mapping, Sequence

from .market_codes import is_sh_sz_main_board_code, normalize_code6
from .technical_indicators import (
    IndicatorInputError,
    TechnicalIndicatorSnapshot,
    compute_technical_indicators,
)


CandidateType = Literal["BREAKOUT", "PULLBACK"]


@dataclass(frozen=True)
class SelectionBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    pct_chg: float
    amount_qian: float


@dataclass(frozen=True)
class CandidateSignal:
    code: str
    name: str
    sector: str
    candidate_type: CandidateType
    setup_score: float
    liquidity_score: float
    trend_score: float
    catalyst_score: float
    source_strategies: tuple[str, ...]
    reasons: tuple[str, ...]
    metrics: dict[str, float]


@dataclass(frozen=True)
class RejectedSignal:
    code: str
    reason: str


@dataclass(frozen=True)
class SelectionResult:
    analysis_date: date
    candidates: tuple[CandidateSignal, ...]
    rejected: tuple[RejectedSignal, ...]


@dataclass(frozen=True)
class SelectionPolicy:
    name: str
    rule_version: str
    strict: bool
    breakout_adx_min: float = 0.0
    breakout_rsi_min: float = 0.0
    breakout_rsi_max: float = 100.0
    breakout_atr_pct_min: float = 0.0
    breakout_atr_pct_max: float = 1.0
    breakout_trend_r2_min: float = 0.0
    breakout_relative_strength_min: float = 0.0
    breakout_pct_min: float = 0.0
    breakout_pct_max: float = 1.0
    breakout_amount_ratio_max: float = 3.0
    pullback_adx_min: float = 0.0
    pullback_rsi_min: float = 0.0
    pullback_rsi_max: float = 100.0
    pullback_atr_pct_min: float = 0.0
    pullback_atr_pct_max: float = 1.0
    pullback_trend_r2_min: float = 0.0
    pullback_relative_strength_min: float = 0.0
    pullback_amount_ratio_max: float = 1.0


BASELINE_POLICY = SelectionPolicy(
    name="BASELINE",
    rule_version="short-term-selection-2.0.0",
    strict=False,
)

STRICT_A = SelectionPolicy(
    name="STRICT_A",
    rule_version="short-term-selection-2.1.0",
    strict=True,
    breakout_adx_min=22.0,
    breakout_rsi_min=55.0,
    breakout_rsi_max=70.0,
    breakout_atr_pct_min=0.015,
    breakout_atr_pct_max=0.05,
    breakout_trend_r2_min=0.55,
    breakout_relative_strength_min=0.75,
    breakout_pct_min=0.005,
    breakout_pct_max=0.04,
    breakout_amount_ratio_max=2.5,
    pullback_adx_min=20.0,
    pullback_rsi_min=48.0,
    pullback_rsi_max=65.0,
    pullback_atr_pct_min=0.012,
    pullback_atr_pct_max=0.045,
    pullback_trend_r2_min=0.50,
    pullback_relative_strength_min=0.70,
    pullback_amount_ratio_max=0.80,
)

STRICT_B = replace(
    STRICT_A,
    name="STRICT_B",
    breakout_adx_min=24.0,
    breakout_trend_r2_min=0.60,
    breakout_relative_strength_min=0.80,
    pullback_adx_min=22.0,
    pullback_trend_r2_min=0.55,
    pullback_relative_strength_min=0.75,
)

STRICT_C = replace(
    STRICT_A,
    name="STRICT_C",
    breakout_rsi_min=57.0,
    breakout_rsi_max=67.0,
    breakout_atr_pct_max=0.04,
    pullback_rsi_min=50.0,
    pullback_rsi_max=62.0,
    pullback_atr_pct_max=0.035,
)


def _candidate_sort_key(candidate: CandidateSignal) -> tuple[float, float, float, str]:
    return (
        -candidate.setup_score,
        -float(candidate.metrics.get("risk_reward_hint", 0)),
        -float(candidate.metrics.get("average_amount5", 0)),
        candidate.code,
    )


def allocate_candidates(
    candidates: Sequence[CandidateSignal],
    *,
    limit: int = 5,
    breakout_quota: int = 3,
    pullback_quota: int = 2,
    max_per_sector: int = 2,
) -> tuple[CandidateSignal, ...]:
    best_by_code: dict[str, CandidateSignal] = {}
    for item in candidates:
        current = best_by_code.get(item.code)
        if current is None or _candidate_sort_key(item) < _candidate_sort_key(current):
            best_by_code[item.code] = item
    eligible = tuple(best_by_code.values())
    selected: list[CandidateSignal] = []
    sector_counts: dict[str, int] = {}
    for candidate_type, quota in (("BREAKOUT", breakout_quota), ("PULLBACK", pullback_quota)):
        taken = 0
        matching = sorted(
            (item for item in eligible if item.candidate_type == candidate_type),
            key=_candidate_sort_key,
        )
        for item in matching:
            if len(selected) >= limit or taken >= quota:
                break
            if sector_counts.get(item.sector, 0) >= max_per_sector:
                continue
            selected.append(item)
            sector_counts[item.sector] = sector_counts.get(item.sector, 0) + 1
            taken += 1
    selected_keys = {(item.code, item.candidate_type) for item in selected}
    for item in sorted(eligible, key=_candidate_sort_key):
        if len(selected) >= limit:
            break
        if (item.code, item.candidate_type) in selected_keys:
            continue
        if sector_counts.get(item.sector, 0) >= max_per_sector:
            continue
        selected.append(item)
        selected_keys.add((item.code, item.candidate_type))
        sector_counts[item.sector] = sector_counts.get(item.sector, 0) + 1
    return tuple(sorted(selected, key=_candidate_sort_key))


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_float(value: object) -> float:
    return float(value)


def _normalize_bar(value: Mapping[str, object] | SelectionBar) -> SelectionBar:
    if isinstance(value, SelectionBar):
        return value
    return SelectionBar(
        trade_date=_as_date(value["trade_date"]),
        open=_as_float(value["open"]),
        high=_as_float(value["high"]),
        low=_as_float(value["low"]),
        close=_as_float(value["close"]),
        pct_chg=_as_float(value.get("pct_chg", 0)),
        amount_qian=_as_float(value.get("amount_qian", value.get("amount", 0))),
    )


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _sources(value: object) -> tuple[str, ...]:
    return tuple(dict.fromkeys(part.strip() for part in re.split(r"[+,，]", str(value or "")) if part.strip()))


def _breakout_signal(
    code: str,
    name: str,
    sector: str,
    sources: tuple[str, ...],
    bars: Sequence[SelectionBar],
) -> CandidateSignal | None:
    closes = [bar.close for bar in bars]
    ma5 = _mean(closes[-5:])
    ma10 = _mean(closes[-10:])
    ma20 = _mean(closes[-20:])
    previous_ma20 = _mean(closes[-25:-5])
    latest = bars[-1]
    previous = bars[-2]
    prior_high20 = max(bar.high for bar in bars[-21:-1])
    average_amount5 = _mean([bar.amount_qian for bar in bars[-6:-1]])
    amount_ratio = latest.amount_qian / average_amount5
    day_range = latest.high - latest.low
    close_location = (latest.close - latest.low) / day_range if day_range > 0 else 0
    gap_pct = (latest.open / previous.close - 1) * 100

    if not (
        ma5 > ma10 > ma20
        and latest.close > prior_high20
        and close_location >= 0.70
        and 1.2 <= amount_ratio <= 3.0
        and gap_pct <= 3.0
        and 0 <= latest.pct_chg <= 7.0
    ):
        return None

    trend_points = 20.0
    trend_points += 10.0 if ma20 > previous_ma20 else 0.0
    distance_from_ma20 = latest.close / ma20 - 1
    trend_points += 10.0 if 0.02 <= distance_from_ma20 <= 0.12 else 0.0
    quality_points = 15.0 + min(10.0, close_location * 10.0) + 5.0
    liquidity_points = 10.0 if average_amount5 >= 200_000 else 5.0
    liquidity_points += 10.0 if amount_ratio <= 2.0 else 5.0
    consensus_points = 10.0 if len(sources) >= 3 else 5.0 if len(sources) >= 2 else 0.0
    setup_score = round(trend_points + quality_points + liquidity_points + consensus_points, 1)
    if setup_score < 70:
        return None

    support = max(ma10, min(bar.low for bar in bars[-10:]))
    risk = latest.close - support
    reward = prior_high20 - latest.close
    risk_reward_hint = reward / risk if risk > 0 and reward > 0 else 0.0
    return CandidateSignal(
        code=code,
        name=name,
        sector=sector,
        candidate_type="BREAKOUT",
        setup_score=setup_score,
        liquidity_score=round(min(1.0, liquidity_points / 20.0), 4),
        trend_score=round(min(1.0, trend_points / 40.0), 4),
        catalyst_score=0.0,
        source_strategies=sources,
        reasons=("MA5>MA10>MA20", "突破前20日高点", "放量且收盘位于日内上部"),
        metrics={
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "prior_high20": prior_high20,
            "average_amount5": average_amount5,
            "amount_ratio": amount_ratio,
            "close_location": close_location,
            "gap_pct": gap_pct,
            "risk_reward_hint": risk_reward_hint,
        },
    )


def _has_recent_volume_breakdown(bars: Sequence[SelectionBar]) -> bool:
    for index in (len(bars) - 2, len(bars) - 1):
        closes = [bar.close for bar in bars[index - 9 : index + 1]]
        ma10 = _mean(closes)
        previous_amount5 = _mean([bar.amount_qian for bar in bars[index - 5 : index]])
        if bars[index].close < ma10 and bars[index].amount_qian > previous_amount5:
            return True
    return False


def _pullback_signal(
    code: str,
    name: str,
    sector: str,
    sources: tuple[str, ...],
    bars: Sequence[SelectionBar],
) -> CandidateSignal | None:
    closes = [bar.close for bar in bars]
    ma5 = _mean(closes[-5:])
    ma10 = _mean(closes[-10:])
    ma20 = _mean(closes[-20:])
    previous_ma20 = _mean(closes[-25:-5])
    latest = bars[-1]
    return10 = latest.close / bars[-11].close - 1
    recent_high = max(bar.high for bar in bars[-10:])
    drawdown = (recent_high - latest.close) / recent_high
    average_amount5 = _mean([bar.amount_qian for bar in bars[-6:-1]])
    amount_ratio = latest.amount_qian / average_amount5
    day_range = latest.high - latest.low
    close_location = (latest.close - latest.low) / day_range if day_range > 0 else 0

    if not (
        ma5 > ma10 > ma20
        and 0.05 <= return10 <= 0.25
        and ma10 <= latest.close <= ma5 * 1.02
        and amount_ratio <= 1.2
        and 0.02 <= drawdown <= 0.10
        and latest.close > ma20
        and not _has_recent_volume_breakdown(bars)
    ):
        return None

    trend_points = 20.0
    trend_points += 10.0 if ma20 > previous_ma20 else 0.0
    trend_points += 10.0
    quality_points = 10.0
    quality_points += 10.0 if latest.close >= latest.open or close_location >= 0.5 else 0.0
    quality_points += 10.0 if drawdown <= 0.06 else 5.0
    liquidity_points = 10.0 if average_amount5 >= 200_000 else 5.0
    liquidity_points += 10.0 if amount_ratio <= 0.9 else 5.0
    consensus_points = 10.0 if len(sources) >= 3 else 5.0 if len(sources) >= 2 else 0.0
    setup_score = round(trend_points + quality_points + liquidity_points + consensus_points, 1)
    if setup_score < 70:
        return None

    support = max(ma10, ma20)
    risk = latest.close - support
    reward = recent_high - latest.close
    risk_reward_hint = reward / risk if risk > 0 and reward > 0 else 0.0
    return CandidateSignal(
        code=code,
        name=name,
        sector=sector,
        candidate_type="PULLBACK",
        setup_score=setup_score,
        liquidity_score=round(min(1.0, liquidity_points / 20.0), 4),
        trend_score=round(min(1.0, trend_points / 40.0), 4),
        catalyst_score=0.0,
        source_strategies=sources,
        reasons=("MA5>MA10>MA20", "强趋势回踩MA5/MA10", "回踩缩量并出现止跌"),
        metrics={
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "return10": return10,
            "recent_high": recent_high,
            "drawdown_from_high": drawdown,
            "average_amount5": average_amount5,
            "amount_ratio": amount_ratio,
            "close_location": close_location,
            "risk_reward_hint": risk_reward_hint,
        },
    )


def _strict_rejection_reason(
    signal: CandidateSignal,
    bars: Sequence[SelectionBar],
    indicators: TechnicalIndicatorSnapshot,
    relative_strength: float | None,
    policy: SelectionPolicy,
) -> str | None:
    if indicators.trend_slope_20 <= 0:
        return "TREND_NOT_POSITIVE"
    if relative_strength is None:
        return "RELATIVE_STRENGTH_MISSING"

    if signal.candidate_type == "BREAKOUT":
        if indicators.adx14 < policy.breakout_adx_min:
            return "ADX_WEAK"
        if indicators.rsi14 < policy.breakout_rsi_min:
            return "RSI_WEAK"
        if indicators.rsi14 > policy.breakout_rsi_max:
            return "RSI_OVERHEATED"
        if not policy.breakout_atr_pct_min <= indicators.atr_pct <= policy.breakout_atr_pct_max:
            return "VOLATILITY_OUT_OF_RANGE"
        if indicators.trend_r2_20 < policy.breakout_trend_r2_min:
            return "TREND_UNSTABLE"
        if relative_strength < policy.breakout_relative_strength_min:
            return "RELATIVE_STRENGTH_LOW"
        if indicators.breakout_pct < policy.breakout_pct_min:
            return "BREAKOUT_TOO_SHALLOW"
        if indicators.breakout_pct > policy.breakout_pct_max:
            return "BREAKOUT_OVEREXTENDED"
        if indicators.amount_ratio < 1.2:
            return "VOLUME_EXPANSION_INSUFFICIENT"
        if indicators.amount_ratio > policy.breakout_amount_ratio_max:
            return "VOLUME_EXPANSION_EXCESSIVE"
        return None

    if indicators.adx14 < policy.pullback_adx_min:
        return "ADX_WEAK"
    if indicators.rsi14 < policy.pullback_rsi_min:
        return "RSI_WEAK"
    if indicators.rsi14 > policy.pullback_rsi_max:
        return "RSI_OVERHEATED"
    if not policy.pullback_atr_pct_min <= indicators.atr_pct <= policy.pullback_atr_pct_max:
        return "VOLATILITY_OUT_OF_RANGE"
    if indicators.trend_r2_20 < policy.pullback_trend_r2_min:
        return "TREND_UNSTABLE"
    if relative_strength < policy.pullback_relative_strength_min:
        return "RELATIVE_STRENGTH_LOW"
    if indicators.pullback_amount_ratio > policy.pullback_amount_ratio_max:
        return "PULLBACK_VOLUME_NOT_CONTRACTING"
    latest = bars[-1]
    day_range = latest.high - latest.low
    close_location = (latest.close - latest.low) / day_range if day_range > 0 else 0.0
    if latest.close < latest.open and close_location < 0.5:
        return "STOP_CONFIRMATION_MISSING"
    return None


def _with_strict_metrics(
    signal: CandidateSignal,
    indicators: TechnicalIndicatorSnapshot,
    relative_strength: float,
) -> CandidateSignal:
    return replace(
        signal,
        metrics={
            **signal.metrics,
            **asdict(indicators),
            "relative_strength_percentile": relative_strength,
        },
    )


def select_short_term_candidates(
    *,
    analysis_date: date,
    rows: Sequence[Mapping[str, object]],
    bars_by_code: Mapping[str, Sequence[Mapping[str, object] | SelectionBar]],
    holding_codes: set[str],
    st_codes: set[str],
    relative_strength_by_code: Mapping[str, float] | None = None,
    technical_indicators_by_code: Mapping[str, TechnicalIndicatorSnapshot] | None = None,
    policy: SelectionPolicy | None = None,
    limit: int = 5,
    max_per_sector: int = 2,
) -> SelectionResult:
    resolved_policy = policy or BASELINE_POLICY
    candidates: list[CandidateSignal] = []
    rejected: list[RejectedSignal] = []
    for row in rows:
        code = normalize_code6(str(row.get("代码", "")))
        name = str(row.get("名称", code)).strip() or code
        if not is_sh_sz_main_board_code(code):
            rejected.append(RejectedSignal(code, "非沪深主板"))
            continue
        if code in holding_codes:
            rejected.append(RejectedSignal(code, "当前持仓"))
            continue
        if code in st_codes or "ST" in name.upper() or "退" in name:
            rejected.append(RejectedSignal(code, "风险股票"))
            continue
        try:
            bars = tuple(
                bar
                for bar in sorted(
                    (_normalize_bar(item) for item in bars_by_code.get(code, ())),
                    key=lambda item: item.trade_date,
                )
                if bar.trade_date <= analysis_date
            )
        except (KeyError, TypeError, ValueError):
            rejected.append(RejectedSignal(code, "日线字段无效"))
            continue
        if len({bar.trade_date for bar in bars}) != len(bars):
            rejected.append(RejectedSignal(code, "日线交易日重复"))
            continue
        if len(bars) < 60:
            rejected.append(RejectedSignal(code, "上市不足60个交易日"))
            continue
        if bars[-1].trade_date != analysis_date:
            rejected.append(RejectedSignal(code, "最近日线日期不匹配"))
            continue
        if any(bar.amount_qian <= 0 or bar.high < bar.low for bar in bars[-20:]):
            rejected.append(RejectedSignal(code, "停牌或日线字段无效"))
            continue
        average_amount5 = _mean([bar.amount_qian for bar in bars[-6:-1]])
        if average_amount5 < 100_000:
            rejected.append(RejectedSignal(code, "流动性不足"))
            continue
        if bars[-1].pct_chg > 7:
            rejected.append(RejectedSignal(code, "当日涨幅超过7%"))
            continue
        sector = str(row.get("所属行业", "未知行业")).strip() or "未知行业"
        sources = _sources(row.get("策略来源", ""))
        signal = _breakout_signal(code, name, sector, sources, bars)
        if signal is None:
            signal = _pullback_signal(code, name, sector, sources, bars)
        if signal is None:
            rejected.append(RejectedSignal(code, "未命中短线形态"))
            continue
        if resolved_policy.strict:
            try:
                indicators = (
                    technical_indicators_by_code.get(code)
                    if technical_indicators_by_code is not None
                    else None
                ) or compute_technical_indicators(bars)
            except IndicatorInputError:
                rejected.append(RejectedSignal(code, "INDICATOR_INVALID"))
                continue
            relative_strength = (
                relative_strength_by_code.get(code)
                if relative_strength_by_code is not None
                else None
            )
            strict_reason = _strict_rejection_reason(
                signal,
                bars,
                indicators,
                relative_strength,
                resolved_policy,
            )
            if strict_reason is not None:
                rejected.append(RejectedSignal(code, strict_reason))
                continue
            signal = _with_strict_metrics(signal, indicators, float(relative_strength))
        candidates.append(signal)
    selected = allocate_candidates(
        candidates,
        limit=limit,
        max_per_sector=max_per_sector,
    )
    return SelectionResult(analysis_date, selected, tuple(rejected))
