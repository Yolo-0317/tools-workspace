"""Deterministic end-of-day trade-plan drafts for one A-share symbol."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import math
from typing import Any, Literal

from short_term_trading.daily_sync import DailyBar, normalize_code
from short_term_trading.evidence import (
    EvidenceSnapshot,
    is_chip_snapshot_for_trade_date,
    is_fresh,
)


def _ceil_cent(value: float) -> float:
    return math.ceil((value - 1e-9) * 100) / 100


def _floor_cent(value: float) -> float:
    return math.floor((value + 1e-9) * 100) / 100


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _atr14(bars: list[DailyBar]) -> float:
    true_ranges: list[float] = []
    for index in range(1, len(bars)):
        current = bars[index]
        previous_close = bars[index - 1].close
        true_ranges.append(max(current.high - current.low, abs(current.high - previous_close), abs(current.low - previous_close)))
    if len(true_ranges) < 14:
        raise ValueError("at least 15 daily bars are required for ATR14")
    return _mean(true_ranges[-14:])


@dataclass(frozen=True)
class RiskProfile:
    per_trade_loss_budget: float = 500.0
    ticket_limit: float = 4000.0
    remaining_exposure: float = 4000.0


@dataclass(frozen=True)
class TradePlanDraft:
    code: str
    status: str
    reason: str
    as_of: str
    trigger_price: float | None
    entry_ceiling: float | None
    invalidation_price: float | None
    first_reduce_price: float | None
    pullback_low: float | None
    pullback_high: float | None
    maximum_shares: int | None
    indicators: dict[str, float]
    evidence_refs: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _no_trade(code: str, as_of: datetime, reason: str, indicators: dict[str, float] | None = None) -> TradePlanDraft:
    return TradePlanDraft(
        code=code,
        status="NO_TRADE",
        reason=reason,
        as_of=as_of.isoformat(),
        trigger_price=None,
        entry_ceiling=None,
        invalidation_price=None,
        first_reduce_price=None,
        pullback_low=None,
        pullback_high=None,
        maximum_shares=0,
        indicators=indicators or {},
        evidence_refs={},
    )


def _maximum_shares(code: str, entry: float, invalidation: float, profile: RiskProfile) -> int:
    risk_per_share = entry - invalidation
    if risk_per_share <= 0:
        return 0
    allowed = min(
        math.floor(profile.per_trade_loss_budget / risk_per_share),
        math.floor(profile.ticket_limit / entry),
        math.floor(profile.remaining_exposure / entry),
    )
    if code.startswith("688"):
        return allowed if allowed >= 200 else 0
    rounded = (allowed // 100) * 100
    return rounded if rounded >= 100 else 0


def build_eod_trade_plan(
    code: str,
    bars: list[DailyBar],
    chip_snapshot: EvidenceSnapshot | None,
    *,
    profile: RiskProfile = RiskProfile(),
    now: datetime,
    expected_trade_date: date | None = None,
    candidate_type: Literal["BREAKOUT", "PULLBACK"] = "BREAKOUT",
    market_status: Literal["ALLOW", "LIMITED", "FREEZE"] = "ALLOW",
    portfolio_approved: bool = True,
) -> TradePlanDraft:
    normalized_code = normalize_code(code)
    ordered = sorted(bars, key=lambda item: item.trade_date)
    if len(ordered) < 20:
        return _no_trade(normalized_code, now, "日线不足 20 根，不能计算价格计划")
    closes = [bar.close for bar in ordered]
    indicators = {
        "ma5": _mean(closes[-5:]),
        "ma10": _mean(closes[-10:]),
        "ma20": _mean(closes[-20:]),
        "high20": max(bar.high for bar in ordered[-20:]),
        "prior_high20": max(bar.high for bar in ordered[-21:-1]),
        "low10": min(bar.low for bar in ordered[-10:]),
    }
    try:
        indicators["atr14"] = _atr14(ordered)
    except ValueError as exc:
        return _no_trade(normalized_code, now, str(exc), indicators)
    if chip_snapshot is None:
        return _no_trade(normalized_code, now, "缺少最近收盘筹码快照", indicators)
    chip_is_valid = (
        is_chip_snapshot_for_trade_date(chip_snapshot, expected_trade_date)
        if expected_trade_date is not None
        else chip_snapshot.kind == "chip" and is_fresh(chip_snapshot, now)
    )
    if not chip_is_valid:
        return _no_trade(normalized_code, now, "筹码快照过期或类型错误", indicators)
    chip = chip_snapshot.data
    try:
        cost_high = float(chip["cost_90_high"])
        cost_low = float(chip["cost_90_low"])
    except (KeyError, TypeError, ValueError):
        return _no_trade(normalized_code, now, "筹码成本区字段无效", indicators)

    atr = indicators["atr14"]
    if candidate_type == "PULLBACK":
        trigger = _ceil_cent(ordered[-1].high)
    else:
        resistance = max(indicators["prior_high20"], cost_high)
        trigger = _ceil_cent(resistance + 0.10 * atr)
    entry_ceiling = _ceil_cent(min(trigger + 0.50 * atr, trigger * 1.015))
    if candidate_type == "PULLBACK":
        pullback_low = max(indicators["ma10"], cost_low)
        pullback_high = max(indicators["ma5"], cost_high)
        support = max(
            value
            for value in (ordered[-1].low, indicators["ma10"], cost_low)
            if value < trigger
        )
    else:
        pullback_low = max(indicators["ma5"] - 0.25 * atr, cost_high - 0.25 * atr)
        pullback_high = max(indicators["ma5"] + 0.25 * atr, cost_high + 0.25 * atr)
        support = max(indicators["low10"], cost_low, indicators["ma10"])
    invalidation = _floor_cent(support - 0.10 * atr)
    risk_fraction = (trigger - invalidation) / trigger if trigger > 0 else 0
    indicators["risk_fraction"] = risk_fraction
    if trigger <= invalidation or not 0.015 <= risk_fraction <= 0.05:
        return _no_trade(normalized_code, now, "触发价到失效价风险距离不在 1.5%–5.0%", indicators)
    effective_profile = profile
    if market_status == "LIMITED":
        effective_profile = RiskProfile(
            per_trade_loss_budget=profile.per_trade_loss_budget / 2,
            ticket_limit=profile.ticket_limit / 2,
            remaining_exposure=profile.remaining_exposure / 2,
        )
    if market_status == "FREEZE":
        maximum_shares = 0
    elif portfolio_approved:
        maximum_shares = _maximum_shares(
            normalized_code, trigger, invalidation, effective_profile
        )
    else:
        maximum_shares = None
    if market_status != "FREEZE" and portfolio_approved and maximum_shares == 0:
        return _no_trade(normalized_code, now, "风险预算不足以覆盖最小申报数量", indicators)
    first_reduce = _ceil_cent(trigger + 1.5 * (trigger - invalidation))
    indicators["risk_reward_ratio"] = (
        (first_reduce - trigger) / (trigger - invalidation)
    )
    return TradePlanDraft(
        code=normalized_code,
        status="WAIT_ENTRY",
        reason="收盘计划已生成；仅在 T+1 盘中五项确认与组合风控全部通过后，才可变为 BUY_ALLOWED",
        as_of=now.isoformat(),
        trigger_price=trigger,
        entry_ceiling=entry_ceiling,
        invalidation_price=invalidation,
        first_reduce_price=first_reduce,
        pullback_low=round(pullback_low, 2),
        pullback_high=round(pullback_high, 2),
        maximum_shares=maximum_shares,
        indicators={key: round(value, 4) for key, value in indicators.items()},
        evidence_refs={"chip": chip_snapshot.raw_evidence_ref},
    )
