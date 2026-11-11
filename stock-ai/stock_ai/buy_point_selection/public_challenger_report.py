"""Immutable aggregate-only artifacts for the public strategy challenger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from .five_day_return_execution import COST_VERSION
from .public_challenger_execution import PUBLIC_CHALLENGER_EVALUATOR_VERSION
from .public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    PUBLIC_CHALLENGER_SIGNAL_VERSION,
    RESIDUAL_TRACK,
)
from .public_challenger_validation import (
    ChallengerAssessment,
    ChallengerPortfolioMetrics,
    ChallengerSegmentMetrics,
    PairedComparison,
    PublicChallengerFreezeReview,
    PublicChallengerResearchReview,
    PublicChallengerTestReview,
    PublicChallengerValidationReview,
)
from .validation import ChronologicalSplit


RESEARCH_SCHEMA = "public-short-term-challenger-research-v1"
VALIDATION_SCHEMA = "public-short-term-challenger-validation-v1"
FREEZE_SCHEMA = "public-short-term-challenger-freeze-v1"
TEST_SCHEMA = "public-short-term-challenger-test-v1"
SOURCE_DEVIATION_VERSION = "a-share-public-reversal-deviation-v1"
_TRACKS = frozenset({CONTRARIAN_TRACK, RESIDUAL_TRACK, EXECUTION_TRACK})
_FORBIDDEN_DETAIL_KEYS = frozenset(
    {"code", "codes", "holdings", "observations", "positions", "selected_keys"}
)


@dataclass(frozen=True)
class PublicChallengerResearchArtifact:
    artifact_identity: str
    input_fingerprint: str
    split_identity: str
    validation_eligible: bool
    review: PublicChallengerResearchReview
    payload: Mapping[str, object]


@dataclass(frozen=True)
class PublicChallengerFreezeArtifact:
    artifact_identity: str
    parent_research_identity: str
    input_fingerprint: str
    split_identity: str
    test_eligible: bool
    review: PublicChallengerFreezeReview
    payload: Mapping[str, object]


@dataclass(frozen=True)
class PublicChallengerTestArtifact:
    artifact_identity: str
    parent_freeze_identity: str
    parent_research_identity: str
    input_fingerprint: str
    split_identity: str
    review: PublicChallengerTestReview
    payload: Mapping[str, object]


def _require_keys(
    value: Mapping[str, object],
    expected: frozenset[str],
    label: str,
) -> None:
    if frozenset(value) != expected:
        raise ValueError(f"{label} fields invalid")


def _digest(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_digest(value: object) -> bool:
    text = str(value)
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _artifact_identity(content: Mapping[str, object]) -> str:
    return _digest(dict(content))


def _serialized(payload: Mapping[str, object]) -> str:
    return json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _write_exclusive_or_verify(path: Path, serialized: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(
                "immutable public challenger artifact conflict"
            ) from None


def _split_payload(split: ChronologicalSplit) -> dict[str, object]:
    return {
        "train": [value.isoformat() for value in split.train],
        "validation": [value.isoformat() for value in split.validation],
        "test": [value.isoformat() for value in split.test],
    }


def _validate_split(split: ChronologicalSplit) -> None:
    dates = split.train + split.validation + split.test
    if (
        len(split.train) < 378
        or len(split.validation) < 126
        or len(split.test) < 126
        or any(current >= following for current, following in zip(dates, dates[1:]))
    ):
        raise ValueError("public challenger split invalid")


def _split_from_payload(value: object) -> ChronologicalSplit:
    if not isinstance(value, dict):
        raise ValueError("public challenger split invalid")
    _require_keys(value, frozenset({"train", "validation", "test"}), "split")

    def dates(key: str) -> tuple[date, ...]:
        raw = value[key]
        if not isinstance(raw, list):
            raise ValueError("public challenger split invalid")
        return tuple(date.fromisoformat(str(item)) for item in raw)

    result = ChronologicalSplit(dates("train"), dates("validation"), dates("test"))
    _validate_split(result)
    return result


def _segment_payload(value: ChallengerSegmentMetrics) -> dict[str, object]:
    return {
        "segment": value.segment,
        "triggered_resolved": value.triggered_resolved,
        "net_expectancy": str(value.net_expectancy),
        "profit_factor": None if value.profit_factor is None else str(value.profit_factor),
        "profitable_wilson_lower": str(value.profitable_wilson_lower),
        "stop_rate": str(value.stop_rate),
        "positive_window_ratio": str(value.positive_window_ratio),
        "maximum_drawdown": str(value.maximum_drawdown),
        "qualifies": value.qualifies,
        "reasons": list(value.reasons),
    }


_SEGMENT_KEYS = frozenset(
    {
        "segment",
        "triggered_resolved",
        "net_expectancy",
        "profit_factor",
        "profitable_wilson_lower",
        "stop_rate",
        "positive_window_ratio",
        "maximum_drawdown",
        "qualifies",
        "reasons",
    }
)


def _segment_from_payload(value: object) -> ChallengerSegmentMetrics:
    if not isinstance(value, dict):
        raise ValueError("segment fields invalid")
    _require_keys(value, _SEGMENT_KEYS, "segment")
    reasons = value["reasons"]
    if not isinstance(reasons, list) or type(value["qualifies"]) is not bool:
        raise ValueError("segment fields invalid")
    profit_factor = value["profit_factor"]
    return ChallengerSegmentMetrics(
        segment=str(value["segment"]),
        triggered_resolved=int(value["triggered_resolved"]),
        net_expectancy=Decimal(str(value["net_expectancy"])),
        profit_factor=(None if profit_factor is None else Decimal(str(profit_factor))),
        profitable_wilson_lower=Decimal(str(value["profitable_wilson_lower"])),
        stop_rate=Decimal(str(value["stop_rate"])),
        positive_window_ratio=Decimal(str(value["positive_window_ratio"])),
        maximum_drawdown=Decimal(str(value["maximum_drawdown"])),
        qualifies=value["qualifies"],
        reasons=tuple(str(item) for item in reasons),
    )


def _portfolio_payload(value: ChallengerPortfolioMetrics) -> dict[str, object]:
    return {
        "accepted_trades": value.accepted_trades,
        "maximum_drawdown": str(value.maximum_drawdown),
        "maximum_stock_trade_share": str(value.maximum_stock_trade_share),
        "maximum_stock_profit_share": str(value.maximum_stock_profit_share),
        "maximum_sector_trade_share": str(value.maximum_sector_trade_share),
        "maximum_sector_profit_share": str(value.maximum_sector_profit_share),
        "top5_profit_share": str(value.top5_profit_share),
        "qualifies": value.qualifies,
        "reasons": list(value.reasons),
    }


_PORTFOLIO_KEYS = frozenset(
    {
        "accepted_trades",
        "maximum_drawdown",
        "maximum_stock_trade_share",
        "maximum_stock_profit_share",
        "maximum_sector_trade_share",
        "maximum_sector_profit_share",
        "top5_profit_share",
        "qualifies",
        "reasons",
    }
)


def _portfolio_from_payload(value: object) -> ChallengerPortfolioMetrics:
    if not isinstance(value, dict):
        raise ValueError("portfolio fields invalid")
    _require_keys(value, _PORTFOLIO_KEYS, "portfolio")
    reasons = value["reasons"]
    if not isinstance(reasons, list) or type(value["qualifies"]) is not bool:
        raise ValueError("portfolio fields invalid")
    return ChallengerPortfolioMetrics(
        accepted_trades=int(value["accepted_trades"]),
        maximum_drawdown=Decimal(str(value["maximum_drawdown"])),
        maximum_stock_trade_share=Decimal(str(value["maximum_stock_trade_share"])),
        maximum_stock_profit_share=Decimal(str(value["maximum_stock_profit_share"])),
        maximum_sector_trade_share=Decimal(str(value["maximum_sector_trade_share"])),
        maximum_sector_profit_share=Decimal(str(value["maximum_sector_profit_share"])),
        top5_profit_share=Decimal(str(value["top5_profit_share"])),
        qualifies=value["qualifies"],
        reasons=tuple(str(item) for item in reasons),
    )


def _paired_payload(value: PairedComparison | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "paired_dates": value.paired_dates,
        "mean_difference": None if value.mean_difference is None else str(value.mean_difference),
        "confidence_interval": (
            None
            if value.confidence_interval is None
            else [str(value.confidence_interval[0]), str(value.confidence_interval[1])]
        ),
        "jaccard": None if value.jaccard is None else str(value.jaccard),
        "incremental_resolved": value.incremental_resolved,
        "incremental_expectancy": (
            None
            if value.incremental_expectancy is None
            else str(value.incremental_expectancy)
        ),
        "incremental_profit_factor": (
            None
            if value.incremental_profit_factor is None
            else str(value.incremental_profit_factor)
        ),
    }


_PAIRED_KEYS = frozenset(
    {
        "paired_dates",
        "mean_difference",
        "confidence_interval",
        "jaccard",
        "incremental_resolved",
        "incremental_expectancy",
        "incremental_profit_factor",
    }
)


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _paired_from_payload(value: object) -> PairedComparison | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("paired fields invalid")
    _require_keys(value, _PAIRED_KEYS, "paired")
    raw_interval = value["confidence_interval"]
    interval = None
    if raw_interval is not None:
        if not isinstance(raw_interval, list) or len(raw_interval) != 2:
            raise ValueError("paired fields invalid")
        interval = (Decimal(str(raw_interval[0])), Decimal(str(raw_interval[1])))
    return PairedComparison(
        paired_dates=int(value["paired_dates"]),
        mean_difference=_optional_decimal(value["mean_difference"]),
        confidence_interval=interval,
        jaccard=_optional_decimal(value["jaccard"]),
        incremental_resolved=int(value["incremental_resolved"]),
        incremental_expectancy=_optional_decimal(value["incremental_expectancy"]),
        incremental_profit_factor=_optional_decimal(value["incremental_profit_factor"]),
    )


def _assessment_payload(value: ChallengerAssessment) -> dict[str, object]:
    return {
        "execution_metrics": _segment_payload(value.execution_metrics),
        "portfolio_metrics": _portfolio_payload(value.portfolio_metrics),
        "paired": _paired_payload(value.paired),
        "verdict": value.verdict,
        "reasons": list(value.reasons),
    }


def _assessment_from_payload(value: object) -> ChallengerAssessment:
    if not isinstance(value, dict):
        raise ValueError("assessment fields invalid")
    _require_keys(
        value,
        frozenset({"execution_metrics", "portfolio_metrics", "paired", "verdict", "reasons"}),
        "assessment",
    )
    reasons = value["reasons"]
    if not isinstance(reasons, list):
        raise ValueError("assessment fields invalid")
    verdict = str(value["verdict"])
    if verdict not in {"CHALLENGER_WINS", "COMPLEMENTARY", "V3_RETAINS", "INCONCLUSIVE"}:
        raise ValueError("assessment verdict invalid")
    return ChallengerAssessment(
        execution_metrics=_segment_from_payload(value["execution_metrics"]),
        portfolio_metrics=_portfolio_from_payload(value["portfolio_metrics"]),
        paired=_paired_from_payload(value["paired"]),
        verdict=verdict,
        reasons=tuple(str(item) for item in reasons),
    )


def _contains_detail(value: object, *, key: str | None = None) -> bool:
    if key is not None and key.lower() in _FORBIDDEN_DETAIL_KEYS:
        return True
    if isinstance(value, dict):
        return any(_contains_detail(item, key=str(name)) for name, item in value.items())
    if isinstance(value, list):
        return any(_contains_detail(item) for item in value)
    return isinstance(value, str) and len(value) == 6 and value.isdigit()


_RESEARCH_CONTENT_KEYS = frozenset(
    {
        "schema",
        "input_fingerprint",
        "split_identity",
        "split",
        "signal_version",
        "evaluator_version",
        "cost_version",
        "source_deviation_version",
        "residual_fraction",
        "track_metrics",
        "validation_assessment",
        "funnel_counts",
        "point_in_time_complete",
        "test_outcomes_read",
        "trade_permission",
        "promotion_eligible",
        "validation_eligible",
    }
)
_RESEARCH_KEYS = _RESEARCH_CONTENT_KEYS | {"artifact_identity"}


def _research_payload(review: PublicChallengerResearchReview) -> dict[str, object]:
    _validate_split(review.split)
    if not _is_digest(review.input_fingerprint):
        raise ValueError("input fingerprint invalid")
    if (
        review.trade_permission != "NO-TRADE"
        or review.test_outcomes_read
        or frozenset(review.track_metrics) != _TRACKS
    ):
        raise ValueError("public challenger research review invalid")
    split_payload = _split_payload(review.split)
    validation_eligible = (
        review.point_in_time_complete
        and review.validation_assessment.execution_metrics.qualifies
        and review.validation_assessment.portfolio_metrics.qualifies
    )
    content: dict[str, object] = {
        "schema": RESEARCH_SCHEMA,
        "input_fingerprint": review.input_fingerprint,
        "split_identity": _digest(split_payload),
        "split": split_payload,
        "signal_version": PUBLIC_CHALLENGER_SIGNAL_VERSION,
        "evaluator_version": PUBLIC_CHALLENGER_EVALUATOR_VERSION,
        "cost_version": COST_VERSION,
        "source_deviation_version": SOURCE_DEVIATION_VERSION,
        "residual_fraction": "0.10",
        "track_metrics": {
            key: _segment_payload(review.track_metrics[key])
            for key in sorted(review.track_metrics)
        },
        "validation_assessment": _assessment_payload(review.validation_assessment),
        "funnel_counts": {
            key: int(value) for key, value in sorted(review.funnel_counts.items())
        },
        "point_in_time_complete": review.point_in_time_complete,
        "test_outcomes_read": review.test_outcomes_read,
        "trade_permission": review.trade_permission,
        "promotion_eligible": False,
        "validation_eligible": validation_eligible,
    }
    if _contains_detail(content):
        raise ValueError("public challenger aggregate contains stock detail")
    return {**content, "artifact_identity": _artifact_identity(content)}


def write_challenger_research(
    review: PublicChallengerResearchReview,
    output_dir: Path,
) -> Path:
    payload = _research_payload(review)
    identity = str(payload["artifact_identity"])
    path = Path(output_dir) / f"public-short-term-challenger-research-{identity}.json"
    _write_exclusive_or_verify(path, _serialized(payload))
    return path


def _read_payload(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("public challenger artifact invalid") from exc
    if not isinstance(value, dict):
        raise ValueError("public challenger artifact invalid")
    return value


def load_challenger_research(path: Path) -> PublicChallengerResearchArtifact:
    target = Path(path)
    payload = _read_payload(target)
    _require_keys(payload, _RESEARCH_KEYS, "research artifact")
    identity = str(payload["artifact_identity"])
    content = {key: value for key, value in payload.items() if key != "artifact_identity"}
    if _artifact_identity(content) != identity:
        raise ValueError("artifact identity mismatch")
    if target.name != f"public-short-term-challenger-research-{identity}.json":
        raise ValueError("artifact filename mismatch")
    if (
        payload["schema"] != RESEARCH_SCHEMA
        or payload["signal_version"] != PUBLIC_CHALLENGER_SIGNAL_VERSION
        or payload["evaluator_version"] != PUBLIC_CHALLENGER_EVALUATOR_VERSION
        or payload["cost_version"] != COST_VERSION
        or payload["source_deviation_version"] != SOURCE_DEVIATION_VERSION
        or payload["residual_fraction"] != "0.10"
        or payload["trade_permission"] != "NO-TRADE"
        or payload["promotion_eligible"] is not False
        or payload["test_outcomes_read"] is not False
        or _contains_detail(payload)
    ):
        raise ValueError("public challenger research artifact invalid")
    split = _split_from_payload(payload["split"])
    if payload["split_identity"] != _digest(_split_payload(split)):
        raise ValueError("split identity mismatch")
    raw_metrics = payload["track_metrics"]
    if not isinstance(raw_metrics, dict) or frozenset(raw_metrics) != _TRACKS:
        raise ValueError("public challenger track metrics invalid")
    track_metrics = {
        key: _segment_from_payload(raw_metrics[key]) for key in sorted(raw_metrics)
    }
    raw_funnel = payload["funnel_counts"]
    if not isinstance(raw_funnel, dict):
        raise ValueError("public challenger funnel invalid")
    assessment = _assessment_from_payload(payload["validation_assessment"])
    review = PublicChallengerResearchReview(
        split=split,
        input_fingerprint=str(payload["input_fingerprint"]),
        track_metrics=track_metrics,
        validation_assessment=assessment,
        funnel_counts={key: int(value) for key, value in sorted(raw_funnel.items())},
        point_in_time_complete=bool(payload["point_in_time_complete"]),
        test_outcomes_read=False,
        trade_permission="NO-TRADE",
    )
    expected = _research_payload(review)
    if expected != payload:
        raise ValueError("public challenger research artifact inconsistent")
    return PublicChallengerResearchArtifact(
        artifact_identity=identity,
        input_fingerprint=review.input_fingerprint,
        split_identity=str(payload["split_identity"]),
        validation_eligible=bool(payload["validation_eligible"]),
        review=review,
        payload=payload,
    )


def write_challenger_validation(
    review: PublicChallengerValidationReview,
    output_dir: Path,
) -> Path:
    directory = Path(output_dir)
    parent_path = directory / (
        "public-short-term-challenger-research-"
        f"{review.parent_research_identity}.json"
    )
    if not parent_path.exists():
        raise ValueError("parent lineage mismatch")
    parent = load_challenger_research(parent_path)
    if parent.artifact_identity != review.parent_research_identity:
        raise ValueError("parent lineage mismatch")
    if parent.input_fingerprint != review.input_fingerprint:
        raise ValueError("input fingerprint mismatch")
    expected_eligible = (
        parent.validation_eligible
        and review.assessment.execution_metrics.qualifies
        and review.assessment.portfolio_metrics.qualifies
    )
    if review.test_eligible != expected_eligible:
        raise ValueError("validation eligibility mismatch")
    content: dict[str, object] = {
        "schema": VALIDATION_SCHEMA,
        "parent_research_identity": review.parent_research_identity,
        "input_fingerprint": review.input_fingerprint,
        "split_identity": parent.split_identity,
        "signal_version": PUBLIC_CHALLENGER_SIGNAL_VERSION,
        "evaluator_version": PUBLIC_CHALLENGER_EVALUATOR_VERSION,
        "cost_version": COST_VERSION,
        "source_deviation_version": SOURCE_DEVIATION_VERSION,
        "assessment": _assessment_payload(review.assessment),
        "test_eligible": review.test_eligible,
        "reasons": list(review.reasons),
        "trade_permission": "NO-TRADE",
        "promotion_eligible": False,
    }
    if _contains_detail(content):
        raise ValueError("public challenger aggregate contains stock detail")
    payload = {**content, "artifact_identity": _artifact_identity(content)}
    identity = str(payload["artifact_identity"])
    path = directory / f"public-short-term-challenger-validation-{identity}.json"
    _write_exclusive_or_verify(path, _serialized(payload))
    return path


_VALIDATION_CONTENT_KEYS = frozenset(
    {
        "schema",
        "parent_research_identity",
        "input_fingerprint",
        "split_identity",
        "signal_version",
        "evaluator_version",
        "cost_version",
        "source_deviation_version",
        "assessment",
        "test_eligible",
        "reasons",
        "trade_permission",
        "promotion_eligible",
    }
)
_VALIDATION_KEYS = _VALIDATION_CONTENT_KEYS | {"artifact_identity"}


def _load_validation(path: Path) -> tuple[dict[str, object], PublicChallengerValidationReview]:
    payload = _read_payload(path)
    _require_keys(payload, _VALIDATION_KEYS, "validation artifact")
    identity = str(payload["artifact_identity"])
    content = {key: value for key, value in payload.items() if key != "artifact_identity"}
    if _artifact_identity(content) != identity:
        raise ValueError("artifact identity mismatch")
    if path.name != f"public-short-term-challenger-validation-{identity}.json":
        raise ValueError("artifact filename mismatch")
    if (
        payload["schema"] != VALIDATION_SCHEMA
        or payload["signal_version"] != PUBLIC_CHALLENGER_SIGNAL_VERSION
        or payload["evaluator_version"] != PUBLIC_CHALLENGER_EVALUATOR_VERSION
        or payload["cost_version"] != COST_VERSION
        or payload["source_deviation_version"] != SOURCE_DEVIATION_VERSION
        or payload["trade_permission"] != "NO-TRADE"
        or payload["promotion_eligible"] is not False
        or type(payload["test_eligible"]) is not bool
        or _contains_detail(payload)
    ):
        raise ValueError("public challenger validation artifact invalid")
    reasons = payload["reasons"]
    if not isinstance(reasons, list):
        raise ValueError("public challenger validation artifact invalid")
    review = PublicChallengerValidationReview(
        parent_research_identity=str(payload["parent_research_identity"]),
        input_fingerprint=str(payload["input_fingerprint"]),
        assessment=_assessment_from_payload(payload["assessment"]),
        test_eligible=payload["test_eligible"],
        reasons=tuple(str(item) for item in reasons),
    )
    return payload, review


_FROZEN_RULES = {
    "residual_fraction": "0.10",
    "estimation_sessions": 60,
    "signal_sessions": 5,
    "minimum_sector_members": 10,
    "confirmation_sessions": 2,
    "reclaim_close_location": "0.60",
    "chase_cap": "0.03",
    "atr_buffer": "0.2",
    "minimum_risk_fraction": "0.015",
    "maximum_risk_fraction": "0.05",
    "holding_sessions": 5,
}


def _matching_validation(
    directory: Path,
    parent_research_identity: str,
) -> tuple[dict[str, object], PublicChallengerValidationReview]:
    matches: list[tuple[dict[str, object], PublicChallengerValidationReview]] = []
    for path in sorted(directory.glob("public-short-term-challenger-validation-*.json")):
        payload, review = _load_validation(path)
        if review.parent_research_identity == parent_research_identity:
            matches.append((payload, review))
    if len(matches) != 1:
        raise ValueError("parent lineage mismatch")
    return matches[0]


def write_challenger_freeze(
    review: PublicChallengerFreezeReview,
    output_dir: Path,
) -> Path:
    directory = Path(output_dir)
    parent_path = directory / (
        "public-short-term-challenger-research-"
        f"{review.parent_research_identity}.json"
    )
    if not parent_path.exists():
        raise ValueError("parent lineage mismatch")
    parent = load_challenger_research(parent_path)
    if parent.input_fingerprint != review.input_fingerprint:
        raise ValueError("input fingerprint mismatch")
    if parent.split_identity != review.split_identity:
        raise ValueError("split identity mismatch")
    validation_payload, validation_review = _matching_validation(
        directory,
        review.parent_research_identity,
    )
    if (
        validation_review.input_fingerprint != review.input_fingerprint
        or str(validation_payload["split_identity"]) != review.split_identity
    ):
        raise ValueError("parent lineage mismatch")
    if validation_review.test_eligible != review.test_eligible:
        raise ValueError("freeze eligibility mismatch")
    if not _is_digest(review.frozen_rule_hash):
        raise ValueError("frozen rule hash invalid")
    content: dict[str, object] = {
        "schema": FREEZE_SCHEMA,
        "parent_research_identity": review.parent_research_identity,
        "parent_validation_identity": validation_payload["artifact_identity"],
        "input_fingerprint": review.input_fingerprint,
        "split_identity": review.split_identity,
        "frozen_rule_hash": review.frozen_rule_hash,
        "signal_version": PUBLIC_CHALLENGER_SIGNAL_VERSION,
        "evaluator_version": PUBLIC_CHALLENGER_EVALUATOR_VERSION,
        "cost_version": COST_VERSION,
        "source_deviation_version": SOURCE_DEVIATION_VERSION,
        **_FROZEN_RULES,
        "test_eligible": review.test_eligible,
        "reasons": list(review.reasons),
        "trade_permission": "NO-TRADE",
        "promotion_eligible": False,
    }
    if _contains_detail(content):
        raise ValueError("public challenger aggregate contains stock detail")
    payload = {**content, "artifact_identity": _artifact_identity(content)}
    identity = str(payload["artifact_identity"])
    path = directory / f"public-short-term-challenger-freeze-{identity}.json"
    _write_exclusive_or_verify(path, _serialized(payload))
    return path


_FREEZE_CONTENT_KEYS = frozenset(
    {
        "schema",
        "parent_research_identity",
        "parent_validation_identity",
        "input_fingerprint",
        "split_identity",
        "frozen_rule_hash",
        "signal_version",
        "evaluator_version",
        "cost_version",
        "source_deviation_version",
        *_FROZEN_RULES.keys(),
        "test_eligible",
        "reasons",
        "trade_permission",
        "promotion_eligible",
    }
)
_FREEZE_KEYS = _FREEZE_CONTENT_KEYS | {"artifact_identity"}


def load_challenger_freeze(path: Path) -> PublicChallengerFreezeArtifact:
    target = Path(path)
    payload = _read_payload(target)
    _require_keys(payload, _FREEZE_KEYS, "freeze artifact")
    identity = str(payload["artifact_identity"])
    content = {key: value for key, value in payload.items() if key != "artifact_identity"}
    if _artifact_identity(content) != identity:
        raise ValueError("artifact identity mismatch")
    if target.name != f"public-short-term-challenger-freeze-{identity}.json":
        raise ValueError("artifact filename mismatch")
    if (
        payload["schema"] != FREEZE_SCHEMA
        or payload["signal_version"] != PUBLIC_CHALLENGER_SIGNAL_VERSION
        or payload["evaluator_version"] != PUBLIC_CHALLENGER_EVALUATOR_VERSION
        or payload["cost_version"] != COST_VERSION
        or payload["source_deviation_version"] != SOURCE_DEVIATION_VERSION
        or any(payload[key] != value for key, value in _FROZEN_RULES.items())
        or not _is_digest(payload["frozen_rule_hash"])
        or not _is_digest(payload["input_fingerprint"])
        or payload["trade_permission"] != "NO-TRADE"
        or payload["promotion_eligible"] is not False
        or type(payload["test_eligible"]) is not bool
        or _contains_detail(payload)
    ):
        raise ValueError("public challenger freeze artifact invalid")
    reasons = payload["reasons"]
    if not isinstance(reasons, list):
        raise ValueError("public challenger freeze artifact invalid")
    directory = target.parent
    parent_identity = str(payload["parent_research_identity"])
    parent_path = directory / f"public-short-term-challenger-research-{parent_identity}.json"
    if not parent_path.exists():
        raise ValueError("parent lineage mismatch")
    parent = load_challenger_research(parent_path)
    if parent.input_fingerprint != payload["input_fingerprint"]:
        raise ValueError("input fingerprint mismatch")
    if parent.split_identity != payload["split_identity"]:
        raise ValueError("split identity mismatch")
    validation_identity = str(payload["parent_validation_identity"])
    validation_path = directory / (
        f"public-short-term-challenger-validation-{validation_identity}.json"
    )
    if not validation_path.exists():
        raise ValueError("parent lineage mismatch")
    validation_payload, validation_review = _load_validation(validation_path)
    if (
        validation_payload["artifact_identity"] != validation_identity
        or validation_review.parent_research_identity != parent_identity
        or validation_review.input_fingerprint != parent.input_fingerprint
        or validation_review.test_eligible != payload["test_eligible"]
    ):
        raise ValueError("parent lineage mismatch")
    review = PublicChallengerFreezeReview(
        parent_research_identity=parent_identity,
        input_fingerprint=str(payload["input_fingerprint"]),
        split_identity=str(payload["split_identity"]),
        frozen_rule_hash=str(payload["frozen_rule_hash"]),
        test_eligible=payload["test_eligible"],
        reasons=tuple(str(item) for item in reasons),
    )
    return PublicChallengerFreezeArtifact(
        artifact_identity=identity,
        parent_research_identity=parent_identity,
        input_fingerprint=review.input_fingerprint,
        split_identity=review.split_identity,
        test_eligible=review.test_eligible,
        review=review,
        payload=payload,
    )


def _test_payload(
    review: PublicChallengerTestReview,
    freeze: PublicChallengerFreezeArtifact,
) -> dict[str, object]:
    if freeze.parent_research_identity != review.parent_research_identity:
        raise ValueError("parent lineage mismatch")
    if freeze.input_fingerprint != review.input_fingerprint:
        raise ValueError("input fingerprint mismatch")
    if not freeze.test_eligible:
        raise ValueError("freeze is not test eligible")
    if review.trade_permission != "NO-TRADE":
        raise ValueError("test trade permission invalid")
    content: dict[str, object] = {
        "schema": TEST_SCHEMA,
        "parent_freeze_identity": review.parent_freeze_identity,
        "parent_research_identity": review.parent_research_identity,
        "input_fingerprint": review.input_fingerprint,
        "split_identity": freeze.split_identity,
        "signal_version": PUBLIC_CHALLENGER_SIGNAL_VERSION,
        "evaluator_version": PUBLIC_CHALLENGER_EVALUATOR_VERSION,
        "cost_version": COST_VERSION,
        "source_deviation_version": SOURCE_DEVIATION_VERSION,
        "assessment": _assessment_payload(review.assessment),
        "trade_permission": review.trade_permission,
        "promotion_eligible": False,
    }
    if _contains_detail(content):
        raise ValueError("public challenger aggregate contains stock detail")
    return {**content, "artifact_identity": _artifact_identity(content)}


_TEST_CONTENT_KEYS = frozenset(
    {
        "schema",
        "parent_freeze_identity",
        "parent_research_identity",
        "input_fingerprint",
        "split_identity",
        "signal_version",
        "evaluator_version",
        "cost_version",
        "source_deviation_version",
        "assessment",
        "trade_permission",
        "promotion_eligible",
    }
)
_TEST_KEYS = _TEST_CONTENT_KEYS | {"artifact_identity"}


def write_challenger_test_once(
    review: PublicChallengerTestReview,
    output_dir: Path,
) -> Path:
    directory = Path(output_dir)
    freeze_path = directory / (
        f"public-short-term-challenger-freeze-{review.parent_freeze_identity}.json"
    )
    if not freeze_path.exists():
        raise ValueError("parent lineage mismatch")
    freeze = load_challenger_freeze(freeze_path)
    payload = _test_payload(review, freeze)
    path = directory / (
        f"public-short-term-challenger-test-{review.parent_freeze_identity}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(_serialized(payload))
    except FileExistsError:
        raise ValueError("public challenger test artifact already exists") from None
    return path


def load_challenger_test(path: Path) -> PublicChallengerTestArtifact:
    target = Path(path)
    payload = _read_payload(target)
    _require_keys(payload, _TEST_KEYS, "test artifact")
    identity = str(payload["artifact_identity"])
    content = {
        key: value for key, value in payload.items() if key != "artifact_identity"
    }
    if _artifact_identity(content) != identity:
        raise ValueError("artifact identity mismatch")
    freeze_identity = str(payload["parent_freeze_identity"])
    if target.name != f"public-short-term-challenger-test-{freeze_identity}.json":
        raise ValueError("artifact filename mismatch")
    if (
        payload["schema"] != TEST_SCHEMA
        or payload["signal_version"] != PUBLIC_CHALLENGER_SIGNAL_VERSION
        or payload["evaluator_version"] != PUBLIC_CHALLENGER_EVALUATOR_VERSION
        or payload["cost_version"] != COST_VERSION
        or payload["source_deviation_version"] != SOURCE_DEVIATION_VERSION
        or payload["trade_permission"] != "NO-TRADE"
        or payload["promotion_eligible"] is not False
        or _contains_detail(payload)
    ):
        raise ValueError("public challenger test artifact invalid")
    freeze_path = target.parent / (
        f"public-short-term-challenger-freeze-{freeze_identity}.json"
    )
    if not freeze_path.exists():
        raise ValueError("parent lineage mismatch")
    freeze = load_challenger_freeze(freeze_path)
    review = PublicChallengerTestReview(
        parent_freeze_identity=freeze_identity,
        parent_research_identity=str(payload["parent_research_identity"]),
        input_fingerprint=str(payload["input_fingerprint"]),
        assessment=_assessment_from_payload(payload["assessment"]),
        trade_permission=str(payload["trade_permission"]),
    )
    if str(payload["split_identity"]) != freeze.split_identity:
        raise ValueError("split identity mismatch")
    if _test_payload(review, freeze) != payload:
        raise ValueError("public challenger test artifact inconsistent")
    return PublicChallengerTestArtifact(
        artifact_identity=identity,
        parent_freeze_identity=freeze_identity,
        parent_research_identity=review.parent_research_identity,
        input_fingerprint=review.input_fingerprint,
        split_identity=freeze.split_identity,
        review=review,
        payload=payload,
    )
