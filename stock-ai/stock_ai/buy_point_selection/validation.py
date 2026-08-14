"""Chronological metrics and fail-closed promotion for buy-point selection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import SelectionPolicy, SetupType


class ValidationError(ValueError):
    """Raised when chronology or frozen validation identity is invalid."""


@dataclass(frozen=True)
class ChronologicalSplit:
    train: tuple[date, ...]
    validation: tuple[date, ...]
    test: tuple[date, ...]


@dataclass(frozen=True)
class TradeObservation:
    exit_date: date
    setup_type: SetupType
    sector_code: str
    net_return: Decimal
    net_pnl: Decimal


@dataclass(frozen=True)
class SetupMetrics:
    triggered_trades: int
    net_expectancy: Decimal
    positive_rolling_window_ratio: Decimal
    frozen_test_expectancy: Decimal
    average_profit_loss_ratio: Decimal
    profit_factor: Decimal
    frozen_test_trades: int = 1


@dataclass(frozen=True)
class StrategyMetrics:
    aggregate: SetupMetrics
    by_setup: Mapping[str, SetupMetrics]
    maximum_drawdown: Decimal
    top5_profit_share: Decimal
    maximum_sector_trade_share: Decimal
    maximum_sector_profit_share: Decimal
    point_in_time_complete: bool


@dataclass(frozen=True)
class SetupPromotionDecision:
    setup_type: SetupType
    promoted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    reasons: tuple[str, ...]
    setup_decisions: Mapping[str, SetupPromotionDecision]


@dataclass(frozen=True)
class HistoricalRelease:
    live_eligible: bool
    rule_version: str
    policy_hash: str
    reasons: tuple[str, ...]


def chronological_split(trading_dates: Sequence[date]) -> ChronologicalSplit:
    ordered = tuple(trading_dates)
    if len(ordered) < 630:
        raise ValidationError("at least 630 sessions are required for a 252/126/126 split")
    if any(current <= previous for previous, current in zip(ordered, ordered[1:])):
        raise ValidationError("trading dates must be unique and strictly increasing")
    train_end = int(len(ordered) * 0.60)
    validation_end = int(len(ordered) * 0.80)
    split = ChronologicalSplit(
        train=ordered[:train_end],
        validation=ordered[train_end:validation_end],
        test=ordered[validation_end:],
    )
    if len(split.train) < 252 or len(split.validation) < 126 or len(split.test) < 126:
        raise ValidationError("split segments must contain at least 252/126/126 sessions")
    return split


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")


def _rolling_positive_ratio(
    observations: Sequence[TradeObservation], trading_dates: Sequence[date]
) -> Decimal:
    dates = tuple(trading_dates)
    if len(dates) < 63:
        return Decimal("0")
    positive = 0
    windows = 0
    for start in range(len(dates) - 62):
        window_dates = set(dates[start : start + 63])
        returns = [value.net_return for value in observations if value.exit_date in window_dates]
        windows += 1
        if returns and _average(returns) > 0:
            positive += 1
    return Decimal(positive) / Decimal(windows)


def _setup_metrics(
    observations: Sequence[TradeObservation],
    test_dates: frozenset[date],
    trading_dates: Sequence[date],
) -> SetupMetrics:
    returns = [value.net_return for value in observations]
    winners = [value.net_return for value in observations if value.net_return > 0]
    losers = [abs(value.net_return) for value in observations if value.net_return < 0]
    profit = sum((value.net_pnl for value in observations if value.net_pnl > 0), Decimal("0"))
    loss = abs(sum((value.net_pnl for value in observations if value.net_pnl < 0), Decimal("0")))
    test_returns = [value.net_return for value in observations if value.exit_date in test_dates]
    return SetupMetrics(
        triggered_trades=len(observations),
        net_expectancy=_average(returns),
        positive_rolling_window_ratio=_rolling_positive_ratio(observations, trading_dates),
        frozen_test_expectancy=_average(test_returns),
        average_profit_loss_ratio=(
            _average(winners) / _average(losers)
            if winners and losers
            else Decimal("0")
        ),
        profit_factor=profit / loss if profit > 0 and loss > 0 else Decimal("0"),
        frozen_test_trades=len(test_returns),
    )


def _maximum_drawdown(
    observations: Sequence[TradeObservation], initial_equity: Decimal
) -> Decimal:
    equity = initial_equity
    peak = initial_equity
    maximum = Decimal("0")
    for value in sorted(observations, key=lambda item: item.exit_date):
        equity += value.net_pnl
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, (peak - equity) / peak)
    return maximum


def compute_metrics(
    observations: Sequence[TradeObservation],
    *,
    test_dates: Sequence[date],
    trading_dates: Sequence[date] | None = None,
    point_in_time_complete: bool,
    initial_equity: Decimal = Decimal("40000"),
) -> StrategyMetrics:
    ordered = tuple(sorted(observations, key=lambda value: value.exit_date))
    test_set = frozenset(test_dates)
    sessions = tuple(trading_dates) if trading_dates is not None else tuple(
        sorted({value.exit_date for value in ordered})
    )
    by_setup = {
        setup_type.value: _setup_metrics(
            [value for value in ordered if value.setup_type is setup_type], test_set, sessions
        )
        for setup_type in SetupType
    }
    winners = sorted(
        (value.net_pnl for value in ordered if value.net_pnl > 0), reverse=True
    )
    gross_profit = sum(winners, Decimal("0"))
    top5_profit_share = (
        sum(winners[:5], Decimal("0")) / gross_profit
        if gross_profit > 0
        else Decimal("1")
    )
    counts: dict[str, int] = {}
    sector_profits: dict[str, Decimal] = {}
    for value in ordered:
        counts[value.sector_code] = counts.get(value.sector_code, 0) + 1
        if value.net_pnl > 0:
            sector_profits[value.sector_code] = (
                sector_profits.get(value.sector_code, Decimal("0")) + value.net_pnl
            )
    maximum_sector_trade_share = (
        Decimal(max(counts.values())) / Decimal(len(ordered)) if ordered else Decimal("1")
    )
    maximum_sector_profit_share = (
        max(sector_profits.values()) / gross_profit
        if sector_profits and gross_profit > 0
        else Decimal("1")
    )
    return StrategyMetrics(
        aggregate=_setup_metrics(ordered, test_set, sessions),
        by_setup=by_setup,
        maximum_drawdown=_maximum_drawdown(ordered, initial_equity),
        top5_profit_share=top5_profit_share,
        maximum_sector_trade_share=maximum_sector_trade_share,
        maximum_sector_profit_share=maximum_sector_profit_share,
        point_in_time_complete=point_in_time_complete,
    )


def _performance_reasons(metrics: SetupMetrics, minimum_trades: int) -> tuple[str, ...]:
    reasons: list[str] = []
    if metrics.triggered_trades < minimum_trades:
        reasons.append("INSUFFICIENT_TRIGGERED_TRADES")
    if metrics.net_expectancy <= 0:
        reasons.append("NEGATIVE_EXPECTANCY")
    if metrics.positive_rolling_window_ratio < Decimal("0.60"):
        reasons.append("ROLLING_STABILITY_BELOW_60_PERCENT")
    if metrics.frozen_test_trades <= 0:
        reasons.append("FROZEN_TEST_SAMPLE_MISSING")
    elif metrics.frozen_test_expectancy < 0:
        reasons.append("NEGATIVE_FROZEN_TEST_EXPECTANCY")
    if metrics.average_profit_loss_ratio < Decimal("1.5"):
        reasons.append("PROFIT_LOSS_RATIO_BELOW_1_5")
    if metrics.profit_factor < Decimal("1.3"):
        reasons.append("PROFIT_FACTOR_BELOW_1_3")
    return tuple(reasons)


def evaluate_promotion(metrics: StrategyMetrics) -> PromotionDecision:
    global_reasons = list(_performance_reasons(metrics.aggregate, 100))
    if metrics.maximum_drawdown > Decimal("0.08"):
        global_reasons.append("MAXIMUM_DRAWDOWN_ABOVE_8_PERCENT")
    if metrics.top5_profit_share > Decimal("0.35"):
        global_reasons.append("TOP5_PROFIT_CONCENTRATION")
    if metrics.maximum_sector_trade_share > Decimal("0.35"):
        global_reasons.append("SECTOR_TRADE_CONCENTRATION")
    if metrics.maximum_sector_profit_share > Decimal("0.40"):
        global_reasons.append("SECTOR_PROFIT_CONCENTRATION")
    if not metrics.point_in_time_complete:
        global_reasons.append("POINT_IN_TIME_COVERAGE_INCOMPLETE")

    setup_decisions: dict[str, SetupPromotionDecision] = {}
    for key, value in metrics.by_setup.items():
        setup_type = SetupType(key)
        reasons = _performance_reasons(value, 30)
        setup_decisions[key] = SetupPromotionDecision(setup_type, not reasons, reasons)
    any_setup_promoted = any(value.promoted for value in setup_decisions.values())
    return PromotionDecision(
        promoted=not global_reasons and any_setup_promoted,
        reasons=tuple(global_reasons),
        setup_decisions=setup_decisions,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def policy_hash(policy: SelectionPolicy) -> str:
    payload = json.dumps(
        _json_safe(asdict(policy)), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def metrics_payload(metrics: StrategyMetrics) -> dict[str, Any]:
    return _json_safe(asdict(metrics))


def write_artifact(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_text(
        json.dumps(_json_safe(dict(payload)), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def load_historical_release(
    path: str | Path,
    *,
    expected_rule_version: str,
    expected_policy_hash: str,
) -> HistoricalRelease:
    target = Path(path)
    if not target.exists():
        return HistoricalRelease(
            False,
            expected_rule_version,
            expected_policy_hash,
            ("VALIDATION_ARTIFACT_MISSING",),
        )
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return HistoricalRelease(
            False,
            expected_rule_version,
            expected_policy_hash,
            ("VALIDATION_ARTIFACT_INVALID",),
        )
    reasons: list[str] = []
    if payload.get("schema") != "buy-point-selection-validation-v1":
        reasons.append("VALIDATION_SCHEMA_MISMATCH")
    if payload.get("rule_version") != expected_rule_version:
        reasons.append("VALIDATION_RULE_VERSION_MISMATCH")
    if payload.get("policy_hash") != expected_policy_hash:
        reasons.append("VALIDATION_POLICY_HASH_MISMATCH")
    if not payload.get("promoted", False):
        reasons.extend(payload.get("reasons") or ("HISTORICAL_PROMOTION_FAILED",))
    return HistoricalRelease(
        live_eligible=not reasons,
        rule_version=str(payload.get("rule_version", expected_rule_version)),
        policy_hash=str(payload.get("policy_hash", expected_policy_hash)),
        reasons=tuple(dict.fromkeys(reasons)),
    )
