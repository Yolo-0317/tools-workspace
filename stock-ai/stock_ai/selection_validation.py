"""Chronological validation and fail-closed policy promotion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from .short_term_selection import (
    BASELINE_POLICY,
    STRICT_A,
    STRICT_B,
    STRICT_C,
    SelectionPolicy,
)


SCHEMA_VERSION = "short-term-selection-validation-v1"
STRICT_RULE_VERSION = "short-term-selection-2.1.0"
STRICT_POLICIES = {
    policy.name: policy for policy in (STRICT_A, STRICT_B, STRICT_C)
}
GENE_WATCH_SCHEMA_VERSION = "limit-up-gene-watch-validation-v1"
GENE_WATCH_RULE_VERSION = "limit-up-gene-watch-1.0.0"
GENE_WATCH_EXECUTION_MODEL = "next-session-box-breakout-stop-v1"


class ValidationError(ValueError):
    """Raised when chronological research inputs are not trustworthy."""


@dataclass(frozen=True)
class ChronologicalSplit:
    train: tuple[date, ...]
    validation: tuple[date, ...]
    test: tuple[date, ...]


@dataclass(frozen=True)
class BacktestMetrics:
    trade_count: int
    wins: int
    expectancy: float
    shape_counts: Mapping[str, int]
    max_drawdown_pct: float = 0.0
    profit_loss_ratio: float = 0.0

    def __post_init__(self) -> None:
        if self.trade_count < 0 or not 0 <= self.wins <= self.trade_count:
            raise ValueError("invalid trade or win count")
        if not math.isfinite(self.expectancy):
            raise ValueError("expectancy must be finite")
        if not math.isfinite(self.max_drawdown_pct) or self.max_drawdown_pct < 0:
            raise ValueError("max_drawdown_pct must be finite and non-negative")
        if not math.isfinite(self.profit_loss_ratio) or self.profit_loss_ratio < 0:
            raise ValueError("profit_loss_ratio must be finite and non-negative")
        if any(value < 0 for value in self.shape_counts.values()):
            raise ValueError("shape counts must not be negative")
        if sum(self.shape_counts.values()) != self.trade_count:
            raise ValueError("shape counts must equal trade_count")

    @property
    def win_rate(self) -> float:
        return self.wins / self.trade_count if self.trade_count else 0.0

    @property
    def wilson_lower_bound(self) -> float:
        return wilson_lower_bound(self.wins, self.trade_count)

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_count": self.trade_count,
            "wins": self.wins,
            "win_rate": self.win_rate,
            "wilson_lower_bound": self.wilson_lower_bound,
            "expectancy": self.expectancy,
            "shape_counts": dict(self.shape_counts),
            "max_drawdown_pct": self.max_drawdown_pct,
            "profit_loss_ratio": self.profit_loss_ratio,
        }

    @classmethod
    def from_dict(cls, value: object) -> BacktestMetrics:
        if not isinstance(value, dict):
            raise ValueError("metrics must be an object")
        shape_counts = value.get("shape_counts")
        if not isinstance(shape_counts, dict):
            raise ValueError("shape_counts must be an object")
        return cls(
            trade_count=int(value["trade_count"]),
            wins=int(value["wins"]),
            expectancy=float(value["expectancy"]),
            shape_counts={str(key): int(count) for key, count in shape_counts.items()},
            max_drawdown_pct=float(value.get("max_drawdown_pct", 0.0)),
            profit_loss_ratio=float(value.get("profit_loss_ratio", 0.0)),
        )


@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PromotionCriteria:
    min_test_trades: int = 100
    min_win_rate_improvement: float = 0.05
    min_expectancy: float = 0.0
    require_shape_samples: bool = True
    min_wilson_lower_bound: float | None = None
    max_drawdown_pct: float | None = None
    min_profit_loss_ratio: float | None = None


DEFAULT_CRITERIA = PromotionCriteria()
GENE_WATCH_CRITERIA = PromotionCriteria(
    min_test_trades=100,
    min_win_rate_improvement=0.05,
    min_expectancy=0.0,
    require_shape_samples=False,
    min_wilson_lower_bound=0.45,
    max_drawdown_pct=15.0,
    min_profit_loss_ratio=1.5,
)


@dataclass(frozen=True)
class ValidationArtifact:
    schema_version: str
    rule_version: str
    generated_at: str
    data_bounds: Mapping[str, str]
    split_bounds: Mapping[str, Mapping[str, str]]
    costs: Mapping[str, float]
    selected_profile: str | None
    metrics: Mapping[str, Mapping[str, object]]
    promoted: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def chronological_splits(dates: Sequence[date]) -> ChronologicalSplit:
    resolved = tuple(dates)
    if any(current <= previous for previous, current in zip(resolved, resolved[1:])):
        raise ValidationError("dates must be strictly increasing")
    train_end = int(len(resolved) * 0.60)
    validation_end = int(len(resolved) * 0.80)
    split = ChronologicalSplit(
        train=resolved[:train_end],
        validation=resolved[train_end:validation_end],
        test=resolved[validation_end:],
    )
    if min(map(len, (split.train, split.validation, split.test)), default=0) < 120:
        raise ValidationError("each chronological segment requires at least 120 sessions")
    return split


def wilson_lower_bound(wins: int, total: int, *, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    if not 0 <= wins <= total:
        raise ValueError("wins must be between zero and total")
    proportion = wins / total
    denominator = 1.0 + z * z / total
    centre = proportion + z * z / (2.0 * total)
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    )
    return (centre - margin) / denominator


def choose_validation_profile(
    *,
    validation: Mapping[str, BacktestMetrics],
) -> str | None:
    eligible = [
        (name, metrics)
        for name, metrics in validation.items()
        if name in STRICT_POLICIES
        and metrics.trade_count >= 75
        and metrics.shape_counts.get("BREAKOUT", 0) >= 25
        and metrics.shape_counts.get("PULLBACK", 0) >= 25
        and metrics.expectancy >= 0
    ]
    if not eligible:
        return None
    eligible.sort(
        key=lambda item: (
            -item[1].wilson_lower_bound,
            -item[1].trade_count,
            item[0],
        )
    )
    return eligible[0][0]


def evaluate_promotion(
    *,
    baseline: BacktestMetrics,
    candidate: BacktestMetrics,
    chronology_valid: bool = True,
    criteria: PromotionCriteria = DEFAULT_CRITERIA,
) -> PromotionDecision:
    reasons: list[str] = []
    if not chronology_valid:
        reasons.append("CHRONOLOGY_INVALID")
    if candidate.trade_count < criteria.min_test_trades:
        reasons.append("INSUFFICIENT_TEST_TRADES")
    if (
        candidate.win_rate - baseline.win_rate + 1e-12
        < criteria.min_win_rate_improvement
    ):
        reasons.append("WIN_RATE_IMPROVEMENT_TOO_SMALL")
    if candidate.expectancy < criteria.min_expectancy:
        reasons.append("NEGATIVE_EXPECTANCY")
    if criteria.require_shape_samples and (
        candidate.shape_counts.get("BREAKOUT", 0) <= 0
        or candidate.shape_counts.get("PULLBACK", 0) <= 0
    ):
        reasons.append("SHAPE_SAMPLE_MISSING")
    if (
        criteria.min_wilson_lower_bound is not None
        and candidate.wilson_lower_bound < criteria.min_wilson_lower_bound
    ):
        reasons.append("WILSON_LOWER_BOUND_TOO_LOW")
    if (
        criteria.max_drawdown_pct is not None
        and candidate.max_drawdown_pct > criteria.max_drawdown_pct
    ):
        reasons.append("MAX_DRAWDOWN_TOO_HIGH")
    if (
        criteria.min_profit_loss_ratio is not None
        and candidate.profit_loss_ratio < criteria.min_profit_loss_ratio
    ):
        reasons.append("PROFIT_LOSS_RATIO_TOO_LOW")
    return PromotionDecision(promoted=not reasons, reasons=tuple(reasons))


def write_validation_artifact(path: Path | str, artifact: ValidationArtifact) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise ValueError("date must be a string")
    return date.fromisoformat(value)


def _validate_artifact_payload(
    payload: object,
    *,
    expected_data_end: date | None,
) -> SelectionPolicy:
    if not isinstance(payload, dict):
        raise ValueError("artifact must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unknown schema")
    if payload.get("rule_version") != STRICT_RULE_VERSION:
        raise ValueError("unknown rule version")
    datetime.fromisoformat(str(payload["generated_at"]))
    selected_profile = payload.get("selected_profile")
    if selected_profile not in STRICT_POLICIES:
        raise ValueError("unknown profile")
    if payload.get("promoted") is not True or payload.get("reasons") not in ([], ()):
        raise ValueError("artifact was not promoted")

    data_bounds = payload.get("data_bounds")
    if not isinstance(data_bounds, dict):
        raise ValueError("missing data bounds")
    data_start = _parse_date(data_bounds.get("start"))
    data_end = _parse_date(data_bounds.get("end"))
    if data_start > data_end or (expected_data_end is not None and data_end != expected_data_end):
        raise ValueError("stale or invalid data bounds")

    split_bounds = payload.get("split_bounds")
    if not isinstance(split_bounds, dict):
        raise ValueError("missing split bounds")
    intervals: list[tuple[date, date]] = []
    for name in ("train", "validation", "test"):
        interval = split_bounds.get(name)
        if not isinstance(interval, dict):
            raise ValueError("missing split interval")
        start = _parse_date(interval.get("start"))
        end = _parse_date(interval.get("end"))
        if start > end:
            raise ValueError("invalid split interval")
        intervals.append((start, end))
    if not intervals[0][1] < intervals[1][0] or not intervals[1][1] < intervals[2][0]:
        raise ValueError("overlapping split intervals")

    costs = payload.get("costs")
    if not isinstance(costs, dict):
        raise ValueError("missing costs")
    for name in ("commission_rate", "slippage_rate"):
        rate = float(costs[name])
        if not math.isfinite(rate) or rate < 0:
            raise ValueError("invalid cost")

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("missing metrics")
    baseline = BacktestMetrics.from_dict(metrics["baseline_test"])
    candidate = BacktestMetrics.from_dict(metrics["candidate_test"])
    decision = evaluate_promotion(baseline=baseline, candidate=candidate)
    if not decision.promoted:
        raise ValueError("stored metrics do not pass promotion")
    return STRICT_POLICIES[str(selected_profile)]


def load_promoted_policy(
    path: Path | str,
    *,
    expected_data_end: date | None = None,
) -> SelectionPolicy:
    """Resolve a promoted strict policy or safely fall back to baseline 2.0."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return _validate_artifact_payload(payload, expected_data_end=expected_data_end)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return BASELINE_POLICY


def _validate_gene_watch_payload(payload: object, *, expected_data_end: date) -> bool:
    if not isinstance(payload, dict):
        raise ValueError("artifact must be an object")
    if payload.get("schema_version") != GENE_WATCH_SCHEMA_VERSION:
        raise ValueError("unknown gene-watch schema")
    if payload.get("rule_version") != GENE_WATCH_RULE_VERSION:
        raise ValueError("unknown gene-watch rule")
    if payload.get("execution_model") != GENE_WATCH_EXECUTION_MODEL:
        raise ValueError("unknown gene-watch execution model")
    datetime.fromisoformat(str(payload["generated_at"]))
    if payload.get("selected_profile") != "limit_up_gene_watch":
        raise ValueError("gene-watch profile was not selected")
    if payload.get("promoted") is not True or payload.get("reasons") not in ([], ()):
        raise ValueError("gene-watch artifact was not promoted")
    if int(payload.get("hold_days", 0)) != 5:
        raise ValueError("unexpected holding period")

    data_bounds = payload.get("data_bounds")
    if not isinstance(data_bounds, dict):
        raise ValueError("missing data bounds")
    data_start = _parse_date(data_bounds.get("start"))
    data_end = _parse_date(data_bounds.get("end"))
    if data_start > data_end or data_end != expected_data_end:
        raise ValueError("stale or invalid data bounds")

    split_bounds = payload.get("split_bounds")
    if not isinstance(split_bounds, dict):
        raise ValueError("missing split bounds")
    intervals: list[tuple[date, date]] = []
    for name in ("train", "validation", "test"):
        interval = split_bounds.get(name)
        if not isinstance(interval, dict):
            raise ValueError("missing split interval")
        start = _parse_date(interval.get("start"))
        end = _parse_date(interval.get("end"))
        if start > end:
            raise ValueError("invalid split interval")
        intervals.append((start, end))
    if not intervals[0][1] < intervals[1][0] or not intervals[1][1] < intervals[2][0]:
        raise ValueError("overlapping split intervals")
    if intervals[-1][1] != data_end:
        raise ValueError("test bound does not reach data end")

    costs = payload.get("costs")
    if not isinstance(costs, dict):
        raise ValueError("missing costs")
    for name in ("commission_rate", "slippage_rate"):
        rate = float(costs[name])
        if not math.isfinite(rate) or rate < 0:
            raise ValueError("invalid cost")

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("missing metrics")
    for key in ("baseline_test", "candidate_test"):
        raw = metrics.get(key)
        if not isinstance(raw, dict):
            raise ValueError("missing metric set")
        if "max_drawdown_pct" not in raw or "profit_loss_ratio" not in raw:
            raise ValueError("legacy metrics cannot promote gene watch")
    baseline = BacktestMetrics.from_dict(metrics["baseline_test"])
    candidate = BacktestMetrics.from_dict(metrics["candidate_test"])
    decision = evaluate_promotion(
        baseline=baseline,
        candidate=candidate,
        criteria=GENE_WATCH_CRITERIA,
    )
    if not decision.promoted:
        raise ValueError("stored gene-watch metrics do not pass promotion")
    return True


def load_gene_watch_promotion(
    path: Path | str,
    *,
    expected_data_end: date,
) -> bool:
    """Fail closed on any missing, stale, malformed, or non-passing artifact."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return _validate_gene_watch_payload(
            payload,
            expected_data_end=expected_data_end,
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return False
