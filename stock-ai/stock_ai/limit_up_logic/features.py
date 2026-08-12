from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Sequence

from .models import LimitUpBar, LimitUpFeatures


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def normalize_bars(
    rows: Sequence[Mapping[str, Any] | LimitUpBar],
) -> tuple[LimitUpBar, ...]:
    normalized: list[LimitUpBar] = []
    for row in rows:
        if isinstance(row, LimitUpBar):
            normalized.append(row)
            continue
        normalized.append(
            LimitUpBar(
                trade_date=_as_date(row["trade_date"]),
                open=_as_float(row.get("open")),
                high=_as_float(row.get("high")),
                low=_as_float(row.get("low")),
                close=_as_float(row.get("close")),
                pct_chg=_as_float(row.get("pct_chg")),
                amount=_as_float(row.get("amount")),
                pre_close=(
                    _as_float(row.get("pre_close"))
                    if row.get("pre_close") not in (None, "")
                    else None
                ),
                turnover_rate=(
                    _as_float(row.get("turnover_rate"))
                    if row.get("turnover_rate") not in (None, "")
                    else None
                ),
            )
        )
    return tuple(sorted(normalized, key=lambda item: item.trade_date))


def limit_up_threshold(code: str, *, is_st: bool = False) -> float | None:
    if is_st:
        return None
    code6 = "".join(ch for ch in str(code) if ch.isdigit())[:6]
    if code6.startswith(("30", "68")):
        return 19.5
    return 9.5


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _safe_ratio(numerator: float, denominator: float | None) -> float | None:
    if denominator in (None, 0):
        return None
    return numerator / denominator


def extract_limit_up_features(
    code: str,
    bars: Sequence[LimitUpBar] | Sequence[Mapping[str, Any]],
    *,
    is_st: bool = False,
) -> LimitUpFeatures:
    normalized = normalize_bars(bars)
    n = len(normalized)
    if n < 10:
        return LimitUpFeatures(
            bar_count=n,
            data_sufficient=False,
            trend_complete=False,
            limit_up_gene="UNKNOWN",
            recent_limit_up_count=0,
            recent_limit_up_indices=(),
            days_since_last_limit_up=None,
            last_limit_up_date=None,
            last_limit_up_close=None,
            last_limit_up_low=None,
            post_limit_retention=False,
            post_limit_support_broken=False,
            post_limit_volume_breakdown=False,
            post_limit_holding_days=0,
            post_limit_shrink=False,
            ma5=None,
            ma10=None,
            ma20=None,
            amount_ratio5=None,
            amount_ratio20=None,
            close_location=None,
            upper_shadow_ratio=None,
            return5=None,
            distance_from_last_limit_close=None,
            distance_from_prior_high20=None,
            latest_pct_chg=normalized[-1].pct_chg if normalized else None,
            latest_trade_date=normalized[-1].trade_date if normalized else None,
            missing_fields=("daily_bars_10",),
        )

    threshold = limit_up_threshold(code, is_st=is_st)
    recent_start = max(0, n - 20)
    indices = tuple(
        index
        for index in range(recent_start, n)
        if threshold is not None and normalized[index].pct_chg >= threshold
    )
    latest_index = n - 1
    last_index = indices[-1] if indices else None
    post = normalized[last_index + 1 :] if last_index is not None else ()
    last_bar = normalized[last_index] if last_index is not None else None
    post_limit_retention = bool(
        last_bar
        and post
        and all(item.close >= last_bar.close * 0.97 for item in post[:3])
        and all(item.low >= last_bar.low for item in post[:3])
    )
    post_limit_support_broken = bool(
        last_bar and post and any(item.close < last_bar.low for item in post)
    )
    pre_amount = _mean([item.amount for item in normalized[max(0, (last_index or 0) - 5) : (last_index or 0)]])
    post_limit_volume_breakdown = bool(
        last_bar
        and post
        and any(
            item.close < last_bar.low
            and pre_amount not in (None, 0)
            and item.amount > float(pre_amount)
            for item in post
        )
    )
    if len(indices) >= 2 or (last_bar and len(post) >= 3 and post_limit_retention):
        gene = "STRONG"
    elif last_bar and post and not post_limit_support_broken:
        gene = "MEDIUM"
    else:
        gene = "WEAK"

    closes = [item.close for item in normalized]
    amounts = [item.amount for item in normalized]
    latest = normalized[-1]
    ma5 = _mean(closes[-5:])
    ma10 = _mean(closes[-10:])
    ma20 = _mean(closes[-20:]) if n >= 20 else None
    prior_amount5 = _mean(amounts[-6:-1])
    average_amount20 = _mean(amounts[-20:]) if n >= 20 else None
    day_range = latest.high - latest.low
    close_location = (latest.close - latest.low) / day_range if day_range > 0 else None
    upper_shadow_ratio = (
        (latest.high - max(latest.open, latest.close)) / day_range if day_range > 0 else None
    )
    prior_high20 = max(item.high for item in normalized[-21:-1]) if n >= 21 else None
    post_limit_shrink = bool(
        last_bar
        and len(post) >= 2
        and latest.amount < _mean([item.amount for item in normalized[last_index : -1]])
    )
    missing: list[str] = []
    if n < 20:
        missing.append("daily_bars_20")
    if all(item.turnover_rate is None for item in normalized):
        missing.append("turnover_rate")

    return LimitUpFeatures(
        bar_count=n,
        data_sufficient=True,
        trend_complete=n >= 20,
        limit_up_gene=gene,
        recent_limit_up_count=len(indices),
        recent_limit_up_indices=indices,
        days_since_last_limit_up=(latest_index - last_index if last_index is not None else None),
        last_limit_up_date=last_bar.trade_date if last_bar else None,
        last_limit_up_close=last_bar.close if last_bar else None,
        last_limit_up_low=last_bar.low if last_bar else None,
        post_limit_retention=post_limit_retention,
        post_limit_support_broken=post_limit_support_broken,
        post_limit_volume_breakdown=post_limit_volume_breakdown,
        post_limit_holding_days=len(post),
        post_limit_shrink=post_limit_shrink,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        amount_ratio5=_safe_ratio(latest.amount, prior_amount5),
        amount_ratio20=_safe_ratio(latest.amount, average_amount20),
        close_location=close_location,
        upper_shadow_ratio=upper_shadow_ratio,
        return5=(latest.close / closes[-6] - 1 if n >= 6 and closes[-6] else None),
        distance_from_last_limit_close=(
            latest.close / last_bar.close - 1 if last_bar and last_bar.close else None
        ),
        distance_from_prior_high20=(
            latest.close / prior_high20 - 1 if prior_high20 else None
        ),
        latest_pct_chg=latest.pct_chg,
        latest_trade_date=latest.trade_date,
        missing_fields=tuple(missing),
    )

