"""Chronological metrics and fail-closed promotion for buy-point selection."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from .execution import SimulatedTrade
from .models import OutcomeLabel, SelectionPolicy, SetupType


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
    outcome: OutcomeLabel
    market_status: str
    sector_resonating: bool
    mfe: Decimal | None
    mae: Decimal | None


@dataclass(frozen=True)
class SetupMetrics:
    triggered_trades: int
    net_expectancy: Decimal
    positive_rolling_window_ratio: Decimal
    frozen_test_expectancy: Decimal
    average_profit_loss_ratio: Decimal
    profit_factor: Decimal
    frozen_test_trades: int = 1
    total_plans: int = 0
    untriggered_plans: int = 0


@dataclass(frozen=True)
class OutcomeCalibration:
    key: str
    setup_type: SetupType
    market_status: str | None
    sector_resonating: bool | None
    data_end: date
    total_plans: int
    triggered_trades: int
    untriggered_plans: int
    target_2r_rate: Decimal
    target_2r_interval: tuple[Decimal, Decimal]
    stop_first_rate: Decimal
    stop_first_interval: tuple[Decimal, Decimal]
    net_expectancy: Decimal
    positive_rolling_window_ratio: Decimal
    frozen_test_expectancy: Decimal
    average_profit_loss_ratio: Decimal
    profit_factor: Decimal
    mfe_median: Decimal
    mfe_p25: Decimal
    mae_median: Decimal
    mae_p75: Decimal
    promoted: bool
    reasons: tuple[str, ...]


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
    calibrations: Mapping[str, OutcomeCalibration] = field(default_factory=dict)


_NON_TRIGGERED_OUTCOMES = frozenset(
    (OutcomeLabel.NOT_TRIGGERED, OutcomeLabel.PENDING)
)


def _is_triggered(value: TradeObservation) -> bool:
    return value.outcome not in _NON_TRIGGERED_OUTCOMES


def trade_observation_from_simulation(
    trade: SimulatedTrade,
    *,
    setup_type: SetupType,
    market_status: str,
    sector_resonating: bool,
    resolution_date: date,
) -> TradeObservation:
    return TradeObservation(
        exit_date=resolution_date,
        setup_type=setup_type,
        sector_code=trade.sector_code,
        net_return=trade.net_return or Decimal("0"),
        net_pnl=trade.net_pnl,
        outcome=trade.outcome,
        market_status=market_status,
        sector_resonating=sector_resonating,
        mfe=trade.mfe,
        mae=trade.mae,
    )


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
        returns = [
            value.net_return
            for value in observations
            if value.exit_date in window_dates and _is_triggered(value)
        ]
        windows += 1
        if returns and _average(returns) > 0:
            positive += 1
    return Decimal(positive) / Decimal(windows)


def _setup_metrics(
    observations: Sequence[TradeObservation],
    test_dates: frozenset[date],
    trading_dates: Sequence[date],
) -> SetupMetrics:
    triggered = [value for value in observations if _is_triggered(value)]
    returns = [value.net_return for value in triggered]
    winners = [value.net_return for value in triggered if value.net_return > 0]
    losers = [abs(value.net_return) for value in triggered if value.net_return < 0]
    profit = sum((value.net_pnl for value in triggered if value.net_pnl > 0), Decimal("0"))
    loss = abs(sum((value.net_pnl for value in triggered if value.net_pnl < 0), Decimal("0")))
    test_returns = [value.net_return for value in triggered if value.exit_date in test_dates]
    return SetupMetrics(
        triggered_trades=len(triggered),
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
        total_plans=len(observations),
        untriggered_plans=len(observations) - len(triggered),
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
    triggered = tuple(value for value in ordered if _is_triggered(value))
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
        (value.net_pnl for value in triggered if value.net_pnl > 0), reverse=True
    )
    gross_profit = sum(winners, Decimal("0"))
    top5_profit_share = (
        sum(winners[:5], Decimal("0")) / gross_profit
        if gross_profit > 0
        else Decimal("1")
    )
    counts: dict[str, int] = {}
    sector_profits: dict[str, Decimal] = {}
    for value in triggered:
        counts[value.sector_code] = counts.get(value.sector_code, 0) + 1
        if value.net_pnl > 0:
            sector_profits[value.sector_code] = (
                sector_profits.get(value.sector_code, Decimal("0")) + value.net_pnl
            )
    maximum_sector_trade_share = (
        Decimal(max(counts.values())) / Decimal(len(triggered)) if triggered else Decimal("1")
    )
    maximum_sector_profit_share = (
        max(sector_profits.values()) / gross_profit
        if sector_profits and gross_profit > 0
        else Decimal("1")
    )
    return StrategyMetrics(
        aggregate=_setup_metrics(ordered, test_set, sessions),
        by_setup=by_setup,
        maximum_drawdown=_maximum_drawdown(triggered, initial_equity),
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


def calibration_key(
    setup_type: SetupType,
    market_status: str | None,
    sector_resonating: bool | None,
) -> str:
    market = market_status if market_status is not None else "*"
    sector = (
        "*"
        if sector_resonating is None
        else "1" if sector_resonating else "0"
    )
    return f"{setup_type.value}|{market}|{sector}"


def _wilson_interval(successes: int, total: int) -> tuple[Decimal, Decimal]:
    if total <= 0:
        return Decimal("0"), Decimal("1")
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return (
        Decimal(str(max(0.0, centre - margin))),
        Decimal(str(min(1.0, centre + margin))),
    )


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = tuple(sorted(values))
    if not ordered:
        return Decimal("0")
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def _nearest_rank(values: Sequence[Decimal], percentile: Decimal) -> Decimal:
    ordered = tuple(sorted(values))
    if not ordered:
        return Decimal("0")
    rank = math.ceil(float(percentile) * len(ordered))
    return ordered[max(0, rank - 1)]


def _outcome_calibration(
    key: str,
    setup_type: SetupType,
    market_status: str | None,
    sector_resonating: bool | None,
    observations: Sequence[TradeObservation],
    *,
    test_dates: frozenset[date],
    trading_dates: Sequence[date],
) -> OutcomeCalibration:
    metrics = _setup_metrics(observations, test_dates, trading_dates)
    triggered = tuple(value for value in observations if _is_triggered(value))
    target_count = sum(
        value.outcome is OutcomeLabel.TARGET_2R_FIRST for value in triggered
    )
    stop_count = sum(value.outcome is OutcomeLabel.STOP_FIRST for value in triggered)
    denominator = Decimal(len(triggered))
    target_rate = Decimal(target_count) / denominator if triggered else Decimal("0")
    stop_rate = Decimal(stop_count) / denominator if triggered else Decimal("0")
    mfe_values = tuple(value.mfe for value in triggered if value.mfe is not None)
    mae_values = tuple(value.mae for value in triggered if value.mae is not None)
    reasons = _performance_reasons(metrics, 30)
    return OutcomeCalibration(
        key=key,
        setup_type=setup_type,
        market_status=market_status,
        sector_resonating=sector_resonating,
        data_end=max(value.exit_date for value in observations),
        total_plans=metrics.total_plans,
        triggered_trades=metrics.triggered_trades,
        untriggered_plans=metrics.untriggered_plans,
        target_2r_rate=target_rate,
        target_2r_interval=_wilson_interval(target_count, len(triggered)),
        stop_first_rate=stop_rate,
        stop_first_interval=_wilson_interval(stop_count, len(triggered)),
        net_expectancy=metrics.net_expectancy,
        positive_rolling_window_ratio=metrics.positive_rolling_window_ratio,
        frozen_test_expectancy=metrics.frozen_test_expectancy,
        average_profit_loss_ratio=metrics.average_profit_loss_ratio,
        profit_factor=metrics.profit_factor,
        mfe_median=_median(mfe_values),
        mfe_p25=_nearest_rank(mfe_values, Decimal("0.25")),
        mae_median=_median(mae_values),
        mae_p75=_nearest_rank(mae_values, Decimal("0.75")),
        promoted=not reasons,
        reasons=reasons,
    )


def build_outcome_calibrations(
    observations: Sequence[TradeObservation],
    *,
    test_dates: Sequence[date],
    trading_dates: Sequence[date],
) -> dict[str, OutcomeCalibration]:
    grouped: dict[
        tuple[SetupType, str | None, bool | None], list[TradeObservation]
    ] = {}
    for value in observations:
        for identity in (
            (value.setup_type, value.market_status, value.sector_resonating),
            (value.setup_type, value.market_status, None),
            (value.setup_type, None, None),
        ):
            grouped.setdefault(identity, []).append(value)
    test_set = frozenset(test_dates)
    calibrations: dict[str, OutcomeCalibration] = {}
    for identity, values in grouped.items():
        setup_type, market_status, sector_resonating = identity
        key = calibration_key(setup_type, market_status, sector_resonating)
        calibrations[key] = _outcome_calibration(
            key,
            setup_type,
            market_status,
            sector_resonating,
            values,
            test_dates=test_set,
            trading_dates=trading_dates,
        )
    return dict(sorted(calibrations.items()))


def resolve_outcome_calibration(
    calibrations: Mapping[str, OutcomeCalibration],
    setup_type: SetupType,
    market_status: str,
    sector_resonating: bool,
    *,
    minimum_triggered: int = 30,
) -> OutcomeCalibration | None:
    for key in (
        calibration_key(setup_type, market_status, sector_resonating),
        calibration_key(setup_type, market_status, None),
        calibration_key(setup_type, None, None),
    ):
        value = calibrations.get(key)
        if value is not None and value.triggered_trades >= minimum_triggered:
            return value
    return None


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


def calibrations_payload(
    calibrations: Mapping[str, OutcomeCalibration],
) -> dict[str, Any]:
    return {
        key: _json_safe(asdict(value))
        for key, value in sorted(calibrations.items())
    }


def _decimal_pair(value: object) -> tuple[Decimal, Decimal]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("calibration interval must contain two values")
    return Decimal(str(value[0])), Decimal(str(value[1]))


def _calibration_from_payload(key: str, value: object) -> OutcomeCalibration:
    if not isinstance(value, dict):
        raise ValueError("calibration must be an object")
    if str(value.get("key")) != key:
        raise ValueError("calibration key mismatch")
    return OutcomeCalibration(
        key=key,
        setup_type=SetupType(str(value["setup_type"])),
        market_status=(
            str(value["market_status"])
            if value.get("market_status") is not None
            else None
        ),
        sector_resonating=(
            bool(value["sector_resonating"])
            if value.get("sector_resonating") is not None
            else None
        ),
        data_end=date.fromisoformat(str(value["data_end"])),
        total_plans=int(value["total_plans"]),
        triggered_trades=int(value["triggered_trades"]),
        untriggered_plans=int(value["untriggered_plans"]),
        target_2r_rate=Decimal(str(value["target_2r_rate"])),
        target_2r_interval=_decimal_pair(value["target_2r_interval"]),
        stop_first_rate=Decimal(str(value["stop_first_rate"])),
        stop_first_interval=_decimal_pair(value["stop_first_interval"]),
        net_expectancy=Decimal(str(value["net_expectancy"])),
        positive_rolling_window_ratio=Decimal(
            str(value["positive_rolling_window_ratio"])
        ),
        frozen_test_expectancy=Decimal(str(value["frozen_test_expectancy"])),
        average_profit_loss_ratio=Decimal(
            str(value["average_profit_loss_ratio"])
        ),
        profit_factor=Decimal(str(value["profit_factor"])),
        mfe_median=Decimal(str(value["mfe_median"])),
        mfe_p25=Decimal(str(value["mfe_p25"])),
        mae_median=Decimal(str(value["mae_median"])),
        mae_p75=Decimal(str(value["mae_p75"])),
        promoted=bool(value["promoted"]),
        reasons=tuple(str(reason) for reason in value.get("reasons", ())),
    )


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
    calibrations: dict[str, OutcomeCalibration] = {}
    if payload.get("schema") != "buy-point-selection-validation-v2":
        reasons.append("VALIDATION_SCHEMA_MISMATCH")
    else:
        try:
            raw_calibrations = payload.get("calibrations")
            if not isinstance(raw_calibrations, dict):
                raise ValueError("calibrations must be an object")
            calibrations = {
                str(key): _calibration_from_payload(str(key), value)
                for key, value in raw_calibrations.items()
            }
        except (KeyError, TypeError, ValueError):
            reasons.append("VALIDATION_CALIBRATIONS_INVALID")
            calibrations = {}
        if payload.get("promoted", False) and not calibrations:
            reasons.append("VALIDATION_CALIBRATIONS_MISSING")
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
        calibrations=calibrations,
    )
