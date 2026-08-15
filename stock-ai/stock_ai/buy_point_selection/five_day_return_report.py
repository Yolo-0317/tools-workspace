"""Immutable research and freeze artifacts for five-day return shadows."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
    FiveDayExit,
    FiveDayTrade,
)
from .five_day_return_profiles import (
    SIZING_VERSION,
    FiveDayReturnProfile,
    build_five_day_return_profiles,
    five_day_profile_hash,
)
from .five_day_return_runtime import (
    FiveDayForwardScreen,
    FiveDayForwardSettlement,
    FiveDayResearchReview,
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
    FiveDayTestReview,
)
from .five_day_return_validation import (
    FIVE_DAY_FREEZE_SCHEMA,
    FiveDayCalibration,
    FiveDayFreeze,
    FiveDayObservation,
    FiveDayPortfolioMetrics,
    FiveDaySegmentMetrics,
    FiveDayTestAssessment,
    FrozenFiveDayProfile,
    _resolved_count,
    _segment_metrics_from_observations,
    build_five_day_calibrations,
    build_five_day_portfolio_metrics,
    evaluate_frozen_test,
    evaluate_validation_freeze,
)
from .models import DetectedSetup, SetupType
from .validation import ChronologicalSplit, chronological_split


FIVE_DAY_ARTIFACT_SCHEMA = "buy-point-five-day-return-shadow-v1"


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _split_section(values: Sequence[date]) -> dict[str, object]:
    dates = tuple(values)
    return {
        "start": dates[0].isoformat(),
        "end": dates[-1].isoformat(),
        "count": len(dates),
        "dates": [value.isoformat() for value in dates],
    }


def _split_payload(value: ChronologicalSplit) -> dict[str, object]:
    return {
        "train": _split_section(value.train),
        "validation": _split_section(value.validation),
        "test": _split_section(value.test),
    }


def _profile_payload(value: FiveDayReturnProfile) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "entry_kind": value.entry_kind,
        "stop_kind": value.stop_kind,
    }


def _setup_payload(value: DetectedSetup) -> dict[str, object]:
    return {
        "code": normalize_code6(value.code),
        "setup_type": value.setup_type.value,
        "analysis_date": value.analysis_date.isoformat(),
        "structure_start": value.structure_start.isoformat(),
        "structure_high": str(value.structure_high),
        "structure_low": str(value.structure_low),
        "quality": str(value.quality),
        "reasons": list(value.reasons),
        "metrics": {
            key: str(item) for key, item in sorted(value.metrics.items())
        },
    }


def _candidate_payload(value: FiveDaySignalCandidate) -> dict[str, object]:
    return {
        "code": normalize_code6(value.code),
        "signal_date": value.signal_date.isoformat(),
        "setup": _setup_payload(value.setup),
        "market_status": value.market_status,
        "sector_code": value.sector_code,
        "sector_resonating": value.sector_resonating,
        "anti_chase_passed": value.anti_chase_passed,
        "average_amount5_qian": str(value.average_amount5_qian),
        "valid_through_trade_date": value.valid_through_trade_date.isoformat(),
        "executable_shares": value.executable_shares,
    }


def _plan_payload(value: FiveDaySignalPlan) -> dict[str, object]:
    return {
        "candidate": _candidate_payload(value.candidate),
        "profile": _profile_payload(value.profile),
        "structure_id": value.structure_id,
        "signal_close": str(value.signal_close),
        "breakout_trigger": str(value.breakout_trigger),
        "structure_stop": _decimal(value.structure_stop),
        "reference_entry": str(value.reference_entry),
        "resistance_basis": value.resistance_basis,
        "resistance_effective_r": _decimal(value.resistance_effective_r),
        "status": value.status,
        "trade_permission": value.trade_permission,
        "executable_shares": value.executable_shares,
    }


def _exit_payload(value: FiveDayExit | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "planned_exit_date": value.planned_exit_date.isoformat(),
        "actual_exit_date": value.actual_exit_date.isoformat(),
        "price": str(value.price),
        "reason": value.reason,
        "fees": str(value.fees),
        "delayed": value.delayed,
    }


def _trade_payload(value: FiveDayTrade) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "structure_id": value.structure_id,
        "code": normalize_code6(value.code),
        "signal_date": value.signal_date.isoformat(),
        "status": value.status,
        "entry_date": (
            None if value.entry_date is None else value.entry_date.isoformat()
        ),
        "entry_price": _decimal(value.entry_price),
        "stop_price": _decimal(value.stop_price),
        "evaluation_target_notional": str(value.evaluation_target_notional),
        "evaluation_shares": value.evaluation_shares,
        "evaluation_notional": str(value.evaluation_notional),
        "entry_fees": str(value.entry_fees),
        "exit": _exit_payload(value.exit),
        "net_pnl": str(value.net_pnl),
        "net_return": _decimal(value.net_return),
        "mfe": _decimal(value.mfe),
        "mae": _decimal(value.mae),
        "intraday_order_ambiguous": value.intraday_order_ambiguous,
        "reasons": list(value.reasons),
        "executable_shares": value.executable_shares,
    }


def _observation_payload(value: FiveDayObservation) -> dict[str, object]:
    return {
        "plan": _plan_payload(value.plan),
        "trade": _trade_payload(value.trade),
        "resolution_date": value.resolution_date.isoformat(),
        "executable_shares": 0,
    }


def _calibration_payload(value: FiveDayCalibration) -> dict[str, object]:
    return {
        "key": value.key,
        "profile_id": value.profile_id,
        "setup_type": value.setup_type.value,
        "market_status": value.market_status,
        "sector_resonating": value.sector_resonating,
        "data_end": value.data_end.isoformat(),
        "total_plans": value.total_plans,
        "triggered_resolved": value.triggered_resolved,
        "positive_net": value.positive_net,
        "profitable_rate": str(value.profitable_rate),
        "profitable_interval": [
            str(value.profitable_interval[0]),
            str(value.profitable_interval[1]),
        ],
        "net_expectancy": str(value.net_expectancy),
        "profit_factor": _decimal(value.profit_factor),
        "stop_rate": str(value.stop_rate),
        "mae_p75": str(value.mae_p75),
        "positive_window_ratio": str(value.positive_window_ratio),
    }


def _segment_payload(value: FiveDaySegmentMetrics) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "segment": value.segment,
        "triggered_resolved": value.triggered_resolved,
        "net_expectancy": str(value.net_expectancy),
        "profit_factor": _decimal(value.profit_factor),
        "profitable_wilson_lower": str(value.profitable_wilson_lower),
        "stop_rate": str(value.stop_rate),
        "positive_window_ratio": str(value.positive_window_ratio),
        "maximum_drawdown": str(value.maximum_drawdown),
        "qualifies": value.qualifies,
        "reasons": list(value.reasons),
    }


def _portfolio_payload(value: FiveDayPortfolioMetrics) -> dict[str, object]:
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


def _recompute_review(review: FiveDayResearchReview) -> FiveDayResearchReview:
    train_set = frozenset(review.split.train)
    validation_set = frozenset(review.split.validation)
    train = tuple(
        value
        for value in review.observations
        if value.plan.candidate.signal_date in train_set
    )
    validation = tuple(
        value
        for value in review.observations
        if value.plan.candidate.signal_date in validation_set
    )
    calibrations = build_five_day_calibrations(
        train, trading_dates=review.split.train
    )
    metrics = tuple(
        _segment_metrics_from_observations(
            profile_id=profile.profile_id,
            segment="validation",
            observations=validation,
            trading_dates=review.split.validation,
            ranking_calibrations=calibrations,
            cumulative_samples=_resolved_count(
                review.observations,
                profile.profile_id,
                data_end=review.split.validation[-1],
            ),
            required_cumulative_samples=70,
        )
        for profile in build_five_day_return_profiles()
    )
    qualified = frozenset(value.profile_id for value in metrics if value.qualifies)
    combined = tuple(
        value
        for value in validation
        if value.plan.profile.profile_id in qualified
        and value.resolution_date <= review.split.validation[-1]
    )
    portfolio = build_five_day_portfolio_metrics(
        tuple(value.plan for value in combined),
        combined,
        calibrations,
    )
    return replace(
        review,
        train_calibrations=calibrations,
        validation_metrics=metrics,
        validation_portfolio=portfolio,
    )


def _research_content(review: FiveDayResearchReview) -> dict[str, object]:
    return {
        "observations": [
            _observation_payload(value)
            for value in sorted(
                review.observations,
                key=lambda item: (
                    item.plan.candidate.signal_date,
                    normalize_code6(item.plan.candidate.code),
                    item.plan.profile.profile_id,
                ),
            )
        ],
        "train_calibrations": {
            key: _calibration_payload(value)
            for key, value in sorted(review.train_calibrations.items())
        },
        "validation_metrics": [
            _segment_payload(value) for value in review.validation_metrics
        ],
        "validation_portfolio": _portfolio_payload(
            review.validation_portfolio
        ),
        "point_in_time_complete": review.point_in_time_complete,
        "test_outcomes_read": review.test_outcomes_read,
    }


def five_day_research_payload(
    review: FiveDayResearchReview,
) -> dict[str, object]:
    expected = _recompute_review(review)
    if (
        review.train_calibrations != expected.train_calibrations
        or review.validation_metrics != expected.validation_metrics
        or review.validation_portfolio != expected.validation_portfolio
    ):
        raise ValueError("five-day research summaries do not match raw rows")
    if (
        review.sizing_version != SIZING_VERSION
        or review.evaluator_version != EVALUATOR_VERSION
        or review.cost_version != COST_VERSION
        or review.profile_matrix_hash
        != five_day_profile_hash(build_five_day_return_profiles())
        or review.test_outcomes_read
        or any(
            value.plan.candidate.signal_date in frozenset(review.split.test)
            for value in review.observations
        )
        or any(
            value.plan.executable_shares != 0
            or value.plan.candidate.executable_shares != 0
            or value.trade.executable_shares != 0
            for value in review.observations
        )
    ):
        raise ValueError("five-day research safety or lineage mismatch")
    content = _research_content(review)
    content_revision = _sha256(content)
    lineage = {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "stage": "research",
        "split": _split_payload(review.split),
        "input_fingerprint": review.input_fingerprint,
        "formal_rule_version": review.formal_rule_version,
        "formal_policy_hash": review.formal_policy_hash,
        "profile_matrix_hash": review.profile_matrix_hash,
        "sizing_version": review.sizing_version,
        "evaluator_version": review.evaluator_version,
        "cost_version": review.cost_version,
        "content_revision": content_revision,
    }
    return {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "stage": "research",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": True,
        "promotion_eligible": False,
        "artifact_identity": _sha256(lineage),
        "content_revision": content_revision,
        "split": _split_payload(review.split),
        "input_fingerprint": review.input_fingerprint,
        "formal_rule_version": review.formal_rule_version,
        "formal_policy_hash": review.formal_policy_hash,
        "profile_matrix_hash": review.profile_matrix_hash,
        "sizing_version": review.sizing_version,
        "evaluator_version": review.evaluator_version,
        "cost_version": review.cost_version,
        **content,
    }


def _date_or_none(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))


def _decimal_or_none(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _parse_split(value: Mapping[str, object]) -> ChronologicalSplit:
    def section(name: str) -> tuple[date, ...]:
        raw = value[name]
        if not isinstance(raw, dict):
            raise ValueError
        dates = tuple(date.fromisoformat(str(item)) for item in raw["dates"])
        if (
            raw["start"] != dates[0].isoformat()
            or raw["end"] != dates[-1].isoformat()
            or int(raw["count"]) != len(dates)
        ):
            raise ValueError
        return dates

    split = ChronologicalSplit(section("train"), section("validation"), section("test"))
    if chronological_split((*split.train, *split.validation, *split.test)) != split:
        raise ValueError
    return split


def _profile_from_payload(value: Mapping[str, object]) -> FiveDayReturnProfile:
    matches = tuple(
        profile
        for profile in build_five_day_return_profiles()
        if profile.profile_id == value.get("profile_id")
    )
    if len(matches) != 1 or _profile_payload(matches[0]) != dict(value):
        raise ValueError
    return matches[0]


def _setup_from_payload(value: Mapping[str, object]) -> DetectedSetup:
    return DetectedSetup(
        code=normalize_code6(str(value["code"])),
        setup_type=SetupType(str(value["setup_type"])),
        analysis_date=date.fromisoformat(str(value["analysis_date"])),
        structure_start=date.fromisoformat(str(value["structure_start"])),
        structure_high=Decimal(str(value["structure_high"])),
        structure_low=Decimal(str(value["structure_low"])),
        quality=Decimal(str(value["quality"])),
        reasons=tuple(str(item) for item in value["reasons"]),
        metrics={
            str(key): Decimal(str(item))
            for key, item in dict(value["metrics"]).items()
        },
    )


def _plan_from_payload(value: Mapping[str, object]) -> FiveDaySignalPlan:
    plan_raw = dict(value)
    candidate_raw = dict(plan_raw["candidate"])
    profile = _profile_from_payload(dict(plan_raw["profile"]))
    candidate = FiveDaySignalCandidate(
        code=normalize_code6(str(candidate_raw["code"])),
        signal_date=date.fromisoformat(str(candidate_raw["signal_date"])),
        setup=_setup_from_payload(dict(candidate_raw["setup"])),
        market_status=str(candidate_raw["market_status"]),
        sector_code=str(candidate_raw["sector_code"]),
        sector_resonating=bool(candidate_raw["sector_resonating"]),
        anti_chase_passed=bool(candidate_raw["anti_chase_passed"]),
        average_amount5_qian=Decimal(
            str(candidate_raw["average_amount5_qian"])
        ),
        valid_through_trade_date=date.fromisoformat(
            str(candidate_raw["valid_through_trade_date"])
        ),
        executable_shares=int(candidate_raw["executable_shares"]),
    )
    plan = FiveDaySignalPlan(
        candidate=candidate,
        profile=profile,
        structure_id=str(plan_raw["structure_id"]),
        signal_close=Decimal(str(plan_raw["signal_close"])),
        breakout_trigger=Decimal(str(plan_raw["breakout_trigger"])),
        structure_stop=_decimal_or_none(plan_raw["structure_stop"]),
        reference_entry=Decimal(str(plan_raw["reference_entry"])),
        resistance_basis=str(plan_raw["resistance_basis"]),
        resistance_effective_r=_decimal_or_none(
            plan_raw["resistance_effective_r"]
        ),
        status=str(plan_raw["status"]),
        trade_permission=str(plan_raw["trade_permission"]),
        executable_shares=int(plan_raw["executable_shares"]),
    )
    if (
        candidate.executable_shares != 0
        or plan.executable_shares != 0
        or plan.status != "CASE_ANALYSIS_ONLY"
        or plan.trade_permission != "NO-TRADE"
        or candidate.code != candidate.setup.code
        or candidate.signal_date != candidate.setup.analysis_date
    ):
        raise ValueError
    return plan


def _observation_from_payload(value: Mapping[str, object]) -> FiveDayObservation:
    plan = _plan_from_payload(dict(value["plan"]))
    candidate = plan.candidate
    trade_raw = dict(value["trade"])
    exit_raw = trade_raw["exit"]
    exit_value = None
    if isinstance(exit_raw, dict):
        exit_value = FiveDayExit(
            planned_exit_date=date.fromisoformat(
                str(exit_raw["planned_exit_date"])
            ),
            actual_exit_date=date.fromisoformat(
                str(exit_raw["actual_exit_date"])
            ),
            price=Decimal(str(exit_raw["price"])),
            reason=str(exit_raw["reason"]),
            fees=Decimal(str(exit_raw["fees"])),
            delayed=bool(exit_raw["delayed"]),
        )
    trade = FiveDayTrade(
        profile_id=str(trade_raw["profile_id"]),
        structure_id=str(trade_raw["structure_id"]),
        code=normalize_code6(str(trade_raw["code"])),
        signal_date=date.fromisoformat(str(trade_raw["signal_date"])),
        status=str(trade_raw["status"]),
        entry_date=_date_or_none(trade_raw["entry_date"]),
        entry_price=_decimal_or_none(trade_raw["entry_price"]),
        stop_price=_decimal_or_none(trade_raw["stop_price"]),
        evaluation_target_notional=Decimal(
            str(trade_raw["evaluation_target_notional"])
        ),
        evaluation_shares=int(trade_raw["evaluation_shares"]),
        evaluation_notional=Decimal(str(trade_raw["evaluation_notional"])),
        entry_fees=Decimal(str(trade_raw["entry_fees"])),
        exit=exit_value,
        net_pnl=Decimal(str(trade_raw["net_pnl"])),
        net_return=_decimal_or_none(trade_raw["net_return"]),
        mfe=_decimal_or_none(trade_raw["mfe"]),
        mae=_decimal_or_none(trade_raw["mae"]),
        intraday_order_ambiguous=bool(
            trade_raw["intraday_order_ambiguous"]
        ),
        reasons=tuple(str(item) for item in trade_raw["reasons"]),
        executable_shares=int(trade_raw["executable_shares"]),
    )
    if (
        int(value["executable_shares"]) != 0
        or trade.executable_shares != 0
        or trade.profile_id != plan.profile.profile_id
        or trade.structure_id != plan.structure_id
        or trade.code != candidate.code
        or trade.signal_date != candidate.signal_date
    ):
        raise ValueError
    return FiveDayObservation(
        plan,
        trade,
        date.fromisoformat(str(value["resolution_date"])),
    )


def _calibration_from_payload(value: Mapping[str, object]) -> FiveDayCalibration:
    interval = tuple(Decimal(str(item)) for item in value["profitable_interval"])
    if len(interval) != 2:
        raise ValueError
    return FiveDayCalibration(
        key=str(value["key"]),
        profile_id=str(value["profile_id"]),
        setup_type=SetupType(str(value["setup_type"])),
        market_status=(
            None if value["market_status"] is None else str(value["market_status"])
        ),
        sector_resonating=(
            None
            if value["sector_resonating"] is None
            else bool(value["sector_resonating"])
        ),
        data_end=date.fromisoformat(str(value["data_end"])),
        total_plans=int(value["total_plans"]),
        triggered_resolved=int(value["triggered_resolved"]),
        positive_net=int(value["positive_net"]),
        profitable_rate=Decimal(str(value["profitable_rate"])),
        profitable_interval=(interval[0], interval[1]),
        net_expectancy=Decimal(str(value["net_expectancy"])),
        profit_factor=_decimal_or_none(value["profit_factor"]),
        stop_rate=Decimal(str(value["stop_rate"])),
        mae_p75=Decimal(str(value["mae_p75"])),
        positive_window_ratio=Decimal(str(value["positive_window_ratio"])),
    )


def _segment_from_payload(value: Mapping[str, object]) -> FiveDaySegmentMetrics:
    return FiveDaySegmentMetrics(
        profile_id=str(value["profile_id"]),
        segment=str(value["segment"]),
        triggered_resolved=int(value["triggered_resolved"]),
        net_expectancy=Decimal(str(value["net_expectancy"])),
        profit_factor=_decimal_or_none(value["profit_factor"]),
        profitable_wilson_lower=Decimal(
            str(value["profitable_wilson_lower"])
        ),
        stop_rate=Decimal(str(value["stop_rate"])),
        positive_window_ratio=Decimal(str(value["positive_window_ratio"])),
        maximum_drawdown=Decimal(str(value["maximum_drawdown"])),
        qualifies=bool(value["qualifies"]),
        reasons=tuple(str(item) for item in value["reasons"]),
    )


def _portfolio_from_payload(value: Mapping[str, object]) -> FiveDayPortfolioMetrics:
    return FiveDayPortfolioMetrics(
        accepted_trades=int(value["accepted_trades"]),
        maximum_drawdown=Decimal(str(value["maximum_drawdown"])),
        maximum_stock_trade_share=Decimal(
            str(value["maximum_stock_trade_share"])
        ),
        maximum_stock_profit_share=Decimal(
            str(value["maximum_stock_profit_share"])
        ),
        maximum_sector_trade_share=Decimal(
            str(value["maximum_sector_trade_share"])
        ),
        maximum_sector_profit_share=Decimal(
            str(value["maximum_sector_profit_share"])
        ),
        top5_profit_share=Decimal(str(value["top5_profit_share"])),
        qualifies=bool(value["qualifies"]),
        reasons=tuple(str(item) for item in value["reasons"]),
    )


def load_five_day_research(path: str | Path) -> FiveDayResearchReview:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            payload["schema"] != FIVE_DAY_ARTIFACT_SCHEMA
            or payload["stage"] != "research"
            or payload["status"] != "CASE_ANALYSIS_ONLY"
            or payload["trade_permission"] != "NO-TRADE"
            or payload["retrospective"] is not True
            or payload["promotion_eligible"] is not False
            or payload["test_outcomes_read"] is not False
        ):
            raise ValueError
        split = _parse_split(dict(payload["split"]))
        observations = tuple(
            _observation_from_payload(dict(item))
            for item in payload["observations"]
        )
        calibrations = {
            str(key): _calibration_from_payload(dict(item))
            for key, item in dict(payload["train_calibrations"]).items()
        }
        review = FiveDayResearchReview(
            split=split,
            input_fingerprint=str(payload["input_fingerprint"]),
            formal_rule_version=str(payload["formal_rule_version"]),
            formal_policy_hash=str(payload["formal_policy_hash"]),
            profile_matrix_hash=str(payload["profile_matrix_hash"]),
            sizing_version=str(payload["sizing_version"]),
            evaluator_version=str(payload["evaluator_version"]),
            cost_version=str(payload["cost_version"]),
            observations=observations,
            train_calibrations=calibrations,
            validation_metrics=tuple(
                _segment_from_payload(dict(item))
                for item in payload["validation_metrics"]
            ),
            validation_portfolio=_portfolio_from_payload(
                dict(payload["validation_portfolio"])
            ),
            point_in_time_complete=bool(payload["point_in_time_complete"]),
            test_outcomes_read=False,
        )
        expected = five_day_research_payload(review)
        if payload != expected:
            raise ValueError
        return review
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("five-day research artifact is invalid") from None


def _write_exclusive_or_verify(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("immutable artifact content mismatch")


def write_five_day_research(
    review: FiveDayResearchReview, output_dir: str | Path
) -> Path:
    payload = five_day_research_payload(review)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"research-{payload['artifact_identity']}.json"
    content = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n"
    _write_exclusive_or_verify(path, content)
    return path


def _frozen_profile_payload(value: FrozenFiveDayProfile) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "rank": value.rank,
        "train_validation_samples": value.train_validation_samples,
        "validation_metrics": _segment_payload(value.validation_metrics),
        "executable_shares": 0,
    }


def five_day_freeze_payload(value: FiveDayFreeze) -> dict[str, object]:
    return {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "freeze_schema": value.schema,
        "stage": "freeze",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": True,
        "promotion_eligible": False,
        "parent_research_identity": value.research_identity,
        "profile_matrix_hash": value.profile_matrix_hash,
        "sizing_version": value.sizing_version,
        "evaluator_version": value.evaluator_version,
        "cost_version": value.cost_version,
        "profiles": [_frozen_profile_payload(item) for item in value.profiles],
        "calibrations": {
            key: _calibration_payload(item)
            for key, item in sorted(value.calibrations.items())
        },
        "empty": value.empty,
        "freeze_hash": value.freeze_hash,
        "executable_shares": 0,
    }


def write_five_day_freeze(
    value: FiveDayFreeze, output_dir: str | Path
) -> Path:
    payload = five_day_freeze_payload(value)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"freeze-{value.freeze_hash}.json"
    content = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n"
    _write_exclusive_or_verify(path, content)
    return path


def load_five_day_freeze(
    path: str | Path,
    research_path: str | Path,
) -> FiveDayFreeze:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        review = load_five_day_research(research_path)
        if not review.point_in_time_complete or review.test_outcomes_read:
            raise ValueError
        research_identity = five_day_research_payload(review)["artifact_identity"]
        expected = evaluate_validation_freeze(
            review.observations,
            train_dates=review.split.train,
            validation_dates=review.split.validation,
            profile_matrix_hash=review.profile_matrix_hash,
            research_identity=str(research_identity),
        )
        if (
            payload.get("schema") != FIVE_DAY_ARTIFACT_SCHEMA
            or payload.get("freeze_schema") != FIVE_DAY_FREEZE_SCHEMA
            or payload.get("stage") != "freeze"
            or payload.get("status") != "CASE_ANALYSIS_ONLY"
            or payload.get("trade_permission") != "NO-TRADE"
            or payload.get("retrospective") is not True
            or payload.get("promotion_eligible") is not False
            or payload.get("executable_shares") != 0
            or payload != five_day_freeze_payload(expected)
        ):
            raise ValueError
        return expected
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("five-day freeze artifact is invalid") from None


def _test_content(review: FiveDayTestReview) -> dict[str, object]:
    return {
        "test_consumed": True,
        "observations": [
            _observation_payload(value)
            for value in sorted(
                review.observations,
                key=lambda item: (
                    item.plan.candidate.signal_date,
                    normalize_code6(item.plan.candidate.code),
                    item.plan.profile.profile_id,
                ),
            )
        ],
        "profile_metrics": [
            _segment_payload(value)
            for value in review.assessment.profile_metrics
        ],
        "portfolio_metrics": _portfolio_payload(
            review.assessment.portfolio_metrics
        ),
        "forward_eligible_profile_ids": list(
            review.assessment.eligible_profile_ids
        ),
        "reasons": list(review.assessment.reasons),
        "executable_shares": 0,
    }


def five_day_test_payload(review: FiveDayTestReview) -> dict[str, object]:
    signal_dates = tuple(review.signal_dates)
    signal_set = frozenset(signal_dates)
    metric_ids = tuple(
        value.profile_id for value in review.assessment.profile_metrics
    )
    eligible_ids = tuple(review.assessment.eligible_profile_ids)
    if (
        not signal_dates
        or any(
            current <= previous
            for previous, current in zip(signal_dates, signal_dates[1:])
        )
        or review.sizing_version != SIZING_VERSION
        or review.evaluator_version != EVALUATOR_VERSION
        or review.cost_version != COST_VERSION
        or len(review.research_identity) != 64
        or len(review.freeze_hash) != 64
        or len(metric_ids) != len(frozenset(metric_ids))
        or any(
            value.segment != "test"
            for value in review.assessment.profile_metrics
        )
        or len(eligible_ids) != len(frozenset(eligible_ids))
        or not frozenset(eligible_ids).issubset(metric_ids)
        or (eligible_ids and not review.assessment.portfolio_metrics.qualifies)
        or not frozenset(
            value.plan.profile.profile_id for value in review.observations
        ).issubset(metric_ids)
        or any(
            value.plan.candidate.signal_date not in signal_set
            or value.trade.status == "PENDING"
            or value.plan.executable_shares != 0
            or value.plan.candidate.executable_shares != 0
            or value.trade.executable_shares != 0
            for value in review.observations
        )
    ):
        raise ValueError("five-day test safety or lineage mismatch")
    content = _test_content(review)
    content_revision = _sha256(content)
    lineage = {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "stage": "test",
        "parent_research_identity": review.research_identity,
        "parent_freeze_hash": review.freeze_hash,
        "signal_dates": _split_section(signal_dates),
        "input_fingerprint": review.input_fingerprint,
        "sizing_version": review.sizing_version,
        "evaluator_version": review.evaluator_version,
        "cost_version": review.cost_version,
        "content_revision": content_revision,
    }
    return {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "stage": "test",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": True,
        "promotion_eligible": False,
        "artifact_identity": _sha256(lineage),
        "content_revision": content_revision,
        "parent_research_identity": review.research_identity,
        "parent_freeze_hash": review.freeze_hash,
        "signal_dates": _split_section(signal_dates),
        "input_fingerprint": review.input_fingerprint,
        "sizing_version": review.sizing_version,
        "evaluator_version": review.evaluator_version,
        "cost_version": review.cost_version,
        **content,
    }


def write_five_day_test_once(
    review: FiveDayTestReview, output_dir: str | Path
) -> Path:
    payload = five_day_test_payload(review)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"test-{review.freeze_hash}.json"
    content = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        raise ValueError(
            "five-day test already exists for freeze hash"
        ) from None
    return path


def _test_dates_from_payload(value: Mapping[str, object]) -> tuple[date, ...]:
    dates = tuple(date.fromisoformat(str(item)) for item in value["dates"])
    if (
        not dates
        or value["start"] != dates[0].isoformat()
        or value["end"] != dates[-1].isoformat()
        or int(value["count"]) != len(dates)
        or any(
            current <= previous
            for previous, current in zip(dates, dates[1:])
        )
    ):
        raise ValueError
    return dates


def load_five_day_test(
    path: str | Path,
    freeze_path: str | Path,
    research_path: str | Path,
) -> FiveDayTestReview:
    try:
        research = load_five_day_research(research_path)
        freeze = load_five_day_freeze(freeze_path, research_path)
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            payload["schema"] != FIVE_DAY_ARTIFACT_SCHEMA
            or payload["stage"] != "test"
            or payload["status"] != "CASE_ANALYSIS_ONLY"
            or payload["trade_permission"] != "NO-TRADE"
            or payload["retrospective"] is not True
            or payload["promotion_eligible"] is not False
            or payload["test_consumed"] is not True
            or payload["executable_shares"] != 0
        ):
            raise ValueError
        signal_dates = _test_dates_from_payload(dict(payload["signal_dates"]))
        observations = tuple(
            _observation_from_payload(dict(item))
            for item in payload["observations"]
        )
        assessment = FiveDayTestAssessment(
            profile_metrics=tuple(
                _segment_from_payload(dict(item))
                for item in payload["profile_metrics"]
            ),
            portfolio_metrics=_portfolio_from_payload(
                dict(payload["portfolio_metrics"])
            ),
            eligible_profile_ids=tuple(
                str(item) for item in payload["forward_eligible_profile_ids"]
            ),
            reasons=tuple(str(item) for item in payload["reasons"]),
        )
        review = FiveDayTestReview(
            signal_dates=signal_dates,
            research_identity=str(payload["parent_research_identity"]),
            freeze_hash=str(payload["parent_freeze_hash"]),
            input_fingerprint=str(payload["input_fingerprint"]),
            observations=observations,
            assessment=assessment,
            sizing_version=str(payload["sizing_version"]),
            evaluator_version=str(payload["evaluator_version"]),
            cost_version=str(payload["cost_version"]),
        )
        research_identity = str(
            five_day_research_payload(research)["artifact_identity"]
        )
        frozen_ids = frozenset(value.profile_id for value in freeze.profiles)
        expected_assessment = evaluate_frozen_test(
            freeze,
            observations,
            test_dates=research.split.test,
        )
        if (
            signal_dates != research.split.test
            or review.research_identity != research_identity
            or review.freeze_hash != freeze.freeze_hash
            or not review.input_fingerprint.startswith(
                f"{research.input_fingerprint}:"
            )
            or any(
                value.plan.candidate.signal_date not in frozenset(signal_dates)
                or value.plan.profile.profile_id not in frozen_ids
                for value in observations
            )
            or assessment != expected_assessment
            or payload != five_day_test_payload(review)
        ):
            raise ValueError
        return review
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("five-day test artifact is invalid") from None


def _forward_screen_content(
    screen: FiveDayForwardScreen,
) -> dict[str, object]:
    return {
        "candidates": [_plan_payload(value) for value in screen.candidates],
        "risk_coverage_complete": screen.risk_coverage_complete,
        "executable_shares": 0,
    }


def five_day_forward_screen_payload(
    screen: FiveDayForwardScreen,
) -> dict[str, object]:
    memberships = tuple(
        (
            normalize_code6(value.candidate.code),
            value.structure_id,
            value.profile.profile_id,
        )
        for value in screen.candidates
    )
    code_structures = tuple(
        (normalize_code6(value.candidate.code), value.structure_id)
        for value in screen.candidates
    )
    if (
        len(screen.freeze_hash) != 64
        or len(screen.test_identity) != 64
        or not screen.risk_coverage_complete
        or len(screen.candidates) > 3
        or len(memberships) != len(frozenset(memberships))
        or len(code_structures) != len(frozenset(code_structures))
        or any(
            value.candidate.signal_date != screen.signal_date
            or value.candidate.executable_shares != 0
            or value.executable_shares != 0
            or value.status != "CASE_ANALYSIS_ONLY"
            or value.trade_permission != "NO-TRADE"
            for value in screen.candidates
        )
    ):
        raise ValueError("five-day forward screen safety mismatch")
    content = _forward_screen_content(screen)
    content_revision = _sha256(content)
    lineage = {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "stage": "forward-screen",
        "parent_freeze_hash": screen.freeze_hash,
        "parent_test_identity": screen.test_identity,
        "signal_date": screen.signal_date.isoformat(),
        "input_fingerprint": screen.input_fingerprint,
        "sizing_version": SIZING_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "cost_version": COST_VERSION,
        "candidate_membership": memberships,
        "content_revision": content_revision,
    }
    return {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "stage": "forward-screen",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": False,
        "promotion_eligible": False,
        "artifact_identity": _sha256(lineage),
        "content_revision": content_revision,
        "parent_freeze_hash": screen.freeze_hash,
        "parent_test_identity": screen.test_identity,
        "signal_date": screen.signal_date.isoformat(),
        "input_fingerprint": screen.input_fingerprint,
        "sizing_version": SIZING_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "cost_version": COST_VERSION,
        **content,
    }


def write_five_day_forward_screen(
    screen: FiveDayForwardScreen,
    output_dir: str | Path,
) -> Path:
    payload = five_day_forward_screen_payload(screen)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (
        f"forward-screen-{screen.signal_date.isoformat()}-"
        f"{payload['artifact_identity']}.json"
    )
    content = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n"
    _write_exclusive_or_verify(path, content)
    return path


def load_five_day_forward_screen(
    path: str | Path,
    freeze_path: str | Path,
    test_path: str | Path,
    research_path: str | Path,
) -> FiveDayForwardScreen:
    from .five_day_return_validation import rank_five_day_plans

    try:
        freeze = load_five_day_freeze(freeze_path, research_path)
        test = load_five_day_test(test_path, freeze_path, research_path)
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            payload["schema"] != FIVE_DAY_ARTIFACT_SCHEMA
            or payload["stage"] != "forward-screen"
            or payload["status"] != "CASE_ANALYSIS_ONLY"
            or payload["trade_permission"] != "NO-TRADE"
            or payload["retrospective"] is not False
            or payload["promotion_eligible"] is not False
            or payload["executable_shares"] != 0
            or payload["sizing_version"] != SIZING_VERSION
            or payload["evaluator_version"] != EVALUATOR_VERSION
            or payload["cost_version"] != COST_VERSION
        ):
            raise ValueError
        candidates = tuple(
            _plan_from_payload(dict(item))
            for item in payload["candidates"]
        )
        screen = FiveDayForwardScreen(
            signal_date=date.fromisoformat(str(payload["signal_date"])),
            freeze_hash=str(payload["parent_freeze_hash"]),
            test_identity=str(payload["parent_test_identity"]),
            input_fingerprint=str(payload["input_fingerprint"]),
            candidates=candidates,
            risk_coverage_complete=bool(
                payload["risk_coverage_complete"]
            ),
        )
        test_identity = str(five_day_test_payload(test)["artifact_identity"])
        eligible_ids = frozenset(test.assessment.eligible_profile_ids)
        ranked = rank_five_day_plans(
            candidates,
            freeze.calibrations,
            daily_limit=3,
        ).plans
        if (
            screen.signal_date <= test.signal_dates[-1]
            or screen.freeze_hash != freeze.freeze_hash
            or screen.test_identity != test_identity
            or not screen.input_fingerprint.startswith(
                f"{test.input_fingerprint}:"
            )
            or any(
                value.profile.profile_id not in eligible_ids
                for value in candidates
            )
            or candidates != ranked
            or payload != five_day_forward_screen_payload(screen)
        ):
            raise ValueError
        return screen
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ValueError(
            "five-day forward screen artifact is invalid"
        ) from None


def _forward_settlement_content(
    settlement: FiveDayForwardSettlement,
) -> dict[str, object]:
    return {
        "candidates": [
            _plan_payload(value) for value in settlement.candidates
        ],
        "outcomes": [
            _observation_payload(value) for value in settlement.outcomes
        ],
        "risk_coverage_complete": settlement.risk_coverage_complete,
        "executable_shares": 0,
    }


def five_day_forward_settlement_payload(
    settlement: FiveDayForwardSettlement,
) -> dict[str, object]:
    terminal_statuses = frozenset(
        {
            "NOT_TRIGGERED",
            "CANCELLED",
            "STOPPED",
            "TIME_EXIT_GAIN",
            "TIME_EXIT_FLAT",
            "TIME_EXIT_LOSS",
        }
    )
    memberships = tuple(
        (
            normalize_code6(value.candidate.code),
            value.structure_id,
            value.profile.profile_id,
        )
        for value in settlement.candidates
    )
    if (
        len(settlement.parent_screen_identity) != 64
        or len(settlement.freeze_hash) != 64
        or len(settlement.test_identity) != 64
        or not settlement.risk_coverage_complete
        or settlement.outcome_cutoff < settlement.signal_date
        or len(settlement.candidates) > 3
        or len(settlement.candidates) != len(settlement.outcomes)
        or len(memberships) != len(frozenset(memberships))
        or any(
            outcome.plan != candidate
            or outcome.plan.candidate.signal_date != settlement.signal_date
            or outcome.trade.status not in terminal_statuses
            or outcome.trade.profile_id != candidate.profile.profile_id
            or outcome.trade.structure_id != candidate.structure_id
            or normalize_code6(outcome.trade.code)
            != normalize_code6(candidate.candidate.code)
            or outcome.trade.signal_date != candidate.candidate.signal_date
            or outcome.resolution_date > settlement.outcome_cutoff
            or outcome.plan.candidate.executable_shares != 0
            or outcome.plan.executable_shares != 0
            or outcome.trade.executable_shares != 0
            for candidate, outcome in zip(
                settlement.candidates,
                settlement.outcomes,
            )
        )
    ):
        raise ValueError("five-day forward settlement safety mismatch")
    content = _forward_settlement_content(settlement)
    content_revision = _sha256(content)
    lineage = {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "stage": "forward-settlement",
        "parent_screen_identity": settlement.parent_screen_identity,
        "parent_freeze_hash": settlement.freeze_hash,
        "parent_test_identity": settlement.test_identity,
        "signal_date": settlement.signal_date.isoformat(),
        "outcome_cutoff": settlement.outcome_cutoff.isoformat(),
        "input_fingerprint": settlement.input_fingerprint,
        "sizing_version": SIZING_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "cost_version": COST_VERSION,
        "content_revision": content_revision,
    }
    return {
        "schema": FIVE_DAY_ARTIFACT_SCHEMA,
        "stage": "forward-settlement",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": False,
        "promotion_eligible": False,
        "artifact_identity": _sha256(lineage),
        "content_revision": content_revision,
        "parent_screen_identity": settlement.parent_screen_identity,
        "parent_freeze_hash": settlement.freeze_hash,
        "parent_test_identity": settlement.test_identity,
        "signal_date": settlement.signal_date.isoformat(),
        "outcome_cutoff": settlement.outcome_cutoff.isoformat(),
        "input_fingerprint": settlement.input_fingerprint,
        "sizing_version": SIZING_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "cost_version": COST_VERSION,
        **content,
    }


def write_five_day_forward_settlement(
    settlement: FiveDayForwardSettlement,
    output_dir: str | Path,
) -> Path:
    payload = five_day_forward_settlement_payload(settlement)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (
        f"forward-settlement-{settlement.parent_screen_identity}.json"
    )
    content = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n"
    _write_exclusive_or_verify(path, content)
    return path


def load_five_day_forward_settlement(
    path: str | Path,
    screen_path: str | Path,
    freeze_path: str | Path,
    test_path: str | Path,
    research_path: str | Path,
) -> FiveDayForwardSettlement:
    try:
        screen = load_five_day_forward_screen(
            screen_path,
            freeze_path,
            test_path,
            research_path,
        )
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            payload["schema"] != FIVE_DAY_ARTIFACT_SCHEMA
            or payload["stage"] != "forward-settlement"
            or payload["status"] != "CASE_ANALYSIS_ONLY"
            or payload["trade_permission"] != "NO-TRADE"
            or payload["retrospective"] is not False
            or payload["promotion_eligible"] is not False
            or payload["executable_shares"] != 0
            or payload["sizing_version"] != SIZING_VERSION
            or payload["evaluator_version"] != EVALUATOR_VERSION
            or payload["cost_version"] != COST_VERSION
        ):
            raise ValueError
        candidates = tuple(
            _plan_from_payload(dict(item))
            for item in payload["candidates"]
        )
        outcomes = tuple(
            _observation_from_payload(dict(item))
            for item in payload["outcomes"]
        )
        settlement = FiveDayForwardSettlement(
            parent_screen_identity=str(
                payload["parent_screen_identity"]
            ),
            signal_date=date.fromisoformat(str(payload["signal_date"])),
            outcome_cutoff=date.fromisoformat(
                str(payload["outcome_cutoff"])
            ),
            freeze_hash=str(payload["parent_freeze_hash"]),
            test_identity=str(payload["parent_test_identity"]),
            input_fingerprint=str(payload["input_fingerprint"]),
            candidates=candidates,
            outcomes=outcomes,
            risk_coverage_complete=bool(
                payload["risk_coverage_complete"]
            ),
        )
        screen_identity = str(
            five_day_forward_screen_payload(screen)["artifact_identity"]
        )
        if (
            settlement.parent_screen_identity != screen_identity
            or settlement.signal_date != screen.signal_date
            or settlement.freeze_hash != screen.freeze_hash
            or settlement.test_identity != screen.test_identity
            or not settlement.input_fingerprint.startswith(
                f"{screen.input_fingerprint}:"
            )
            or settlement.candidates != screen.candidates
            or any(
                outcome.plan != candidate
                for candidate, outcome in zip(candidates, outcomes)
            )
            or payload != five_day_forward_settlement_payload(settlement)
        ):
            raise ValueError
        return settlement
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ValueError(
            "five-day forward settlement artifact is invalid"
        ) from None
