#!/usr/bin/env python3
"""Run manual, read-only threshold-shadow research stages."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_ai.market_codes import normalize_code6
from scripts.analysis.review_buy_point_case import (
    CaseReviewInputs,
    load_mysql_case_inputs,
)
from stock_ai.buy_point_selection.case_report import revision_identity
from stock_ai.buy_point_selection.case_review import (
    CaseOutcome,
    evaluate_case_plan,
    replay_case_signals,
)
from stock_ai.buy_point_selection.models import SelectionPolicy
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ThresholdProfileMetrics,
    ThresholdShadowOutcome,
    aggregate_profile_metrics,
    compare_exact_recall,
    evaluate_threshold_outcomes,
    freeze_threshold_profiles,
    select_frozen_daily_candidates,
)
from stock_ai.buy_point_selection.threshold_shadow_report import (
    ThresholdWindowReview,
    load_threshold_freeze_artifact,
    load_threshold_research_artifact,
    write_threshold_freeze,
    write_threshold_shadow_revision,
)
from stock_ai.buy_point_selection.threshold_shadow_research import (
    ThresholdProfile,
    build_threshold_profiles,
    profile_matrix_hash,
    replay_threshold_shadows,
)
from stock_ai.buy_point_selection.models import SetupType
from stock_ai.buy_point_selection.validation import policy_hash


DEFAULT_OUTPUT_DIR = "output/research/buy_point_threshold_shadows"
RESEARCH_WINDOWS = (
    (
        tuple(date(2026, 7, day) for day in range(20, 25)),
        date(2026, 7, 31),
    ),
    (
        tuple(date(2026, 7, day) for day in range(27, 32)),
        date(2026, 8, 7),
    ),
)
TEST_WINDOW = (
    tuple(date(2026, 8, day) for day in range(3, 8)),
    date(2026, 8, 14),
)


@dataclass(frozen=True)
class V5RecallLineage:
    case_identity: str
    winner_keys: frozenset[tuple[date, str]]
    risk_coverage_complete: bool


def case_input_fingerprint(inputs: CaseReviewInputs) -> str:
    payload = {
        "trading_dates": [value.isoformat() for value in sorted(set(inputs.trading_dates))],
        "bars": [
            {
                "code": normalize_code6(code),
                "rows": [
                    [
                        row.trade_date.isoformat(),
                        str(row.open),
                        str(row.high),
                        str(row.low),
                        str(row.close),
                        str(row.pct_chg),
                        str(row.amount_qian),
                    ]
                    for row in sorted(values, key=lambda item: item.trade_date)
                ],
            }
            for code, values in sorted(inputs.bars_by_code.items())
        ],
        "memberships": [
            [
                row.code,
                row.sector_code,
                row.sector_name,
                row.valid_from.isoformat(),
                None if row.valid_to is None else row.valid_to.isoformat(),
                row.source,
            ]
            for row in sorted(
                inputs.memberships,
                key=lambda item: (item.code, item.valid_from, item.sector_code),
            )
        ],
        "risk_flags": [
            [
                row.code,
                row.flag_type,
                row.severity,
                row.effective_from.isoformat(),
                None if row.effective_to is None else row.effective_to.isoformat(),
                row.source,
                row.evidence_ref,
            ]
            for row in sorted(
                inputs.risk_flags,
                key=lambda item: (item.code, item.effective_from, item.flag_type),
            )
        ],
        "coverage": [
            [
                day.isoformat(),
                row.sector_complete,
                row.st_complete,
                row.announcement_complete,
            ]
            for day, row in sorted(inputs.coverage_by_date.items())
        ],
        "markets": [
            [
                day.isoformat(),
                row.indexes_above_ma20,
                str(row.breadth_pct),
                str(row.amount_ratio),
                row.complete,
            ]
            for day, row in sorted(inputs.market_snapshots.items())
        ],
        "holdings": [
            [day.isoformat(), sorted(normalize_code6(code) for code in codes)]
            for day, codes in sorted(inputs.holding_codes_by_date.items())
        ],
        "holdings_complete": [
            [day.isoformat(), complete]
            for day, complete in sorted(inputs.holdings_complete_by_date.items())
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_v5_recall_lineage(
    path: str | Path,
    expected_dates: Sequence[date],
    cutoff: date,
) -> V5RecallLineage:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema") != "buy-point-case-review-v5"
        or payload.get("status") != "CASE_ANALYSIS_ONLY"
        or payload.get("trade_permission") != "NO-TRADE"
    ):
        raise ValueError("expected safe v5 case artifact")
    dates = [value.isoformat() for value in sorted(set(expected_dates))]
    if payload.get("signal_dates") != dates or payload.get("outcome_cutoff") != cutoff.isoformat():
        raise ValueError("v5 case window mismatch")
    artifact_revision = payload.get("revision_identity")
    lineage_identity = str(payload["case_identity"])
    if artifact_revision is not None:
        if (
            not isinstance(artifact_revision, str)
            or len(artifact_revision) != 16
            or any(value not in "0123456789abcdef" for value in artifact_revision)
        ):
            raise ValueError("v5 revision identity malformed")
        if revision_identity(payload) != artifact_revision:
            raise ValueError("v5 revision identity mismatch")
        lineage_identity = artifact_revision
    winners = payload.get("daily_recall_winners")
    metrics = payload.get("daily_recall_metrics")
    if not isinstance(winners, list) or not isinstance(metrics, dict):
        raise ValueError("v5 daily recall evidence missing")
    if any(value.get("executable_shares") != 0 for value in winners):
        raise ValueError("v5 daily recall rows must be zero-share")
    by_date = metrics.get("by_date")
    if (
        int(metrics.get("winner_pairs", -1)) != len(winners)
        or not isinstance(by_date, list)
        or sum(int(value.get("winner_pairs", -1)) for value in by_date) != len(winners)
    ):
        raise ValueError("v5 daily recall rows do not reconcile")
    keys = frozenset(
        (
            date.fromisoformat(str(value["signal_date"])),
            normalize_code6(str(value["code"])),
        )
        for value in winners
    )
    return V5RecallLineage(
        lineage_identity,
        keys,
        bool(payload.get("risk_coverage_complete", False)),
    )


def build_research_review(
    start: date,
    end: date,
    cutoff: date,
    v5_case_path: str | Path,
    *,
    input_loader: Callable[[date, date, date], CaseReviewInputs] = load_mysql_case_inputs,
) -> ThresholdWindowReview:
    inputs = input_loader(start, end, cutoff)
    signal_dates = tuple(
        value for value in sorted(set(inputs.trading_dates)) if start <= value <= end
    )
    if not signal_dates:
        raise ValueError("signal window has no trading dates")
    if any(not inputs.holdings_complete_by_date.get(value, False) for value in signal_dates):
        raise ValueError("signal window holdings are incomplete")
    future_dates = tuple(
        value
        for value in sorted(set(inputs.trading_dates))
        if signal_dates[-1] < value <= cutoff
    )
    if len(future_dates) != 5:
        raise ValueError("signal window must contain exactly five outcome sessions")
    lineage = load_v5_recall_lineage(v5_case_path, signal_dates, cutoff)
    policy = SelectionPolicy()
    profiles = build_threshold_profiles(policy)
    formal_replay = replay_case_signals(
        signal_dates=signal_dates,
        trading_dates=inputs.trading_dates,
        bars_by_code=inputs.bars_by_code,
        memberships=inputs.memberships,
        risk_flags=inputs.risk_flags,
        coverage_by_date=inputs.coverage_by_date,
        market_snapshots=inputs.market_snapshots,
        holding_codes_by_date=inputs.holding_codes_by_date,
        policy=policy,
    )
    shadow_replay = replay_threshold_shadows(
        signal_dates=signal_dates,
        trading_dates=inputs.trading_dates,
        bars_by_code=inputs.bars_by_code,
        memberships=inputs.memberships,
        risk_flags=inputs.risk_flags,
        coverage_by_date=inputs.coverage_by_date,
        market_snapshots=inputs.market_snapshots,
        holding_codes_by_date=inputs.holding_codes_by_date,
        profiles=profiles,
        formal_policy=policy,
    )
    shadow_outcomes = evaluate_threshold_outcomes(
        shadow_replay.candidates,
        inputs.bars_by_code,
        outcome_cutoff=cutoff,
    )
    formal_candidates = formal_replay.strict_shadow
    formal_outcomes = tuple(
        evaluate_case_plan(
            candidate,
            inputs.bars_by_code.get(candidate.code, ()),
            outcome_cutoff=cutoff,
        )
        for candidate in formal_candidates
    )
    formal_keys = {
        (value.signal_date, normalize_code6(value.code))
        for value in formal_candidates
    }
    risk_complete = all(
        inputs.coverage_by_date.get(value) is not None
        and inputs.coverage_by_date[value].announcement_complete
        for value in signal_dates
    )
    return ThresholdWindowReview(
        "research",
        signal_dates,
        cutoff,
        lineage.case_identity,
        case_input_fingerprint(inputs),
        policy.rule_version,
        policy_hash(policy),
        profile_matrix_hash(profiles),
        None,
        profiles,
        shadow_replay,
        shadow_outcomes,
        aggregate_profile_metrics(
            tuple(value.profile_id for value in shadow_replay.candidates),
            shadow_outcomes,
        ),
        formal_candidates,
        formal_outcomes,
        (),
        (),
        compare_exact_recall(
            shadow_replay.candidates,
            lineage.winner_keys,
            formal_keys,
        ),
        risk_complete and lineage.risk_coverage_complete,
        False,
    )


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _profile_from_payload(value: dict[str, object]) -> ThresholdProfile:
    return ThresholdProfile(
        str(value["profile_id"]),
        SetupType(str(value["setup_type"])),
        str(value["policy_field"]),
        str(value["direction"]),
        Decimal(str(value["relaxation_rate"])),
        Decimal(str(value["formal_value"])),
        Decimal(str(value["shadow_value"])),
        str(value["failure_reason"]),
        str(value["metric_name"]),
    )


def _metrics_from_payload(value: dict[str, object]) -> ThresholdProfileMetrics:
    return ThresholdProfileMetrics(
        str(value["profile_id"]),
        int(value["candidate_count"]),
        int(value["triggered"]),
        int(value["resolved"]),
        int(value["positive_net"]),
        int(value["stop_first"]),
        _optional_decimal(value.get("mean_net_return")),
        _optional_decimal(value.get("median_net_return")),
        _optional_decimal(value.get("positive_net_rate")),
        _optional_decimal(value.get("stop_first_rate")),
        _optional_decimal(value.get("mean_mfe")),
        _optional_decimal(value.get("mean_mae")),
        bool(value["qualifies"]),
        tuple(str(item) for item in value["qualification_reasons"]),
    )


def _shadow_outcome_from_payload(
    value: dict[str, object],
) -> ThresholdShadowOutcome:
    signal_date = date.fromisoformat(str(value["signal_date"]))
    code = normalize_code6(str(value["code"]))
    outcome = CaseOutcome(
        code=code,
        signal_date=signal_date,
        tier="THRESHOLD_SHADOW",
        status=str(value["status"]),
        mfe=_optional_decimal(value.get("mfe")),
        mae=_optional_decimal(value.get("mae")),
        trigger_date=(
            None
            if value.get("trigger_date") is None
            else date.fromisoformat(str(value["trigger_date"]))
        ),
        net_return=_optional_decimal(value.get("net_return")),
        close_return=_optional_decimal(value.get("close_return")),
        stop_first=bool(value["stop_first"]),
        intraday_order_ambiguous=bool(value["intraday_order_ambiguous"]),
        structure_id=str(value["structure_id"]),
    )
    return ThresholdShadowOutcome(
        str(value["profile_id"]), code, signal_date, outcome
    )


def _research_identity(payload: dict[str, object]) -> str:
    identity = {
        "schema": payload["schema"],
        "stage": payload["stage"],
        "signal_dates": sorted(str(item) for item in payload["signal_dates"]),
        "outcome_cutoff": payload["outcome_cutoff"],
        "v5_case_identity": payload["v5_case_identity"],
        "input_fingerprint": payload["input_fingerprint"],
        "formal_rule_version": payload["formal_rule_version"],
        "formal_policy_hash": payload["formal_policy_hash"],
        "profile_matrix_hash": payload["profile_matrix_hash"],
        "freeze_hash": payload["freeze_hash"],
        "evaluator_version": payload["evaluator_version"],
        "cost_version": payload["cost_version"],
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _validated_research_rows(
    path: str | Path,
) -> tuple[
    dict[str, object],
    tuple[str, ...],
    tuple[ThresholdShadowOutcome, ...],
]:
    payload = load_threshold_research_artifact(path)
    if (
        payload.get("evaluator_version") != "case-evaluator-v1"
        or payload.get("cost_version") != "execution-costs-default-v1"
        or payload.get("freeze_hash") is not None
        or payload.get("test_consumed")
        or payload.get("promotion_eligible")
        or payload.get("artifact_identity") != _research_identity(payload)
    ):
        raise ValueError("research artifact lineage mismatch")
    profiles = tuple(
        _profile_from_payload(value) for value in payload.get("profiles", ())
    )
    expected_profiles = build_threshold_profiles(SelectionPolicy())
    if profiles != tuple(sorted(expected_profiles, key=lambda item: item.profile_id)):
        raise ValueError("research profile matrix mismatch")
    if payload.get("profile_matrix_hash") != profile_matrix_hash(expected_profiles):
        raise ValueError("research profile matrix hash mismatch")
    rows = tuple(payload.get("candidates", ()))
    outcomes_payload = tuple(payload.get("shadow_outcomes", ()))
    if any(int(value.get("executable_shares", -1)) != 0 for value in rows):
        raise ValueError("research candidates must be zero-share")
    if any(
        int(value.get("executable_shares", -1)) != 0
        for value in outcomes_payload
    ):
        raise ValueError("research outcomes must be zero-share")
    candidate_profile_ids = tuple(str(value["profile_id"]) for value in rows)
    outcomes = tuple(
        _shadow_outcome_from_payload(value) for value in outcomes_payload
    )
    candidate_keys = sorted(
        (
            str(value["profile_id"]),
            str(value["signal_date"]),
            normalize_code6(str(value["code"])),
        )
        for value in rows
    )
    outcome_keys = sorted(
        (value.profile_id, value.signal_date.isoformat(), value.code)
        for value in outcomes
    )
    metrics = payload.get("metrics")
    if (
        not isinstance(metrics, dict)
        or int(metrics.get("candidates", -1)) != len(rows)
        or int(metrics.get("shadow_outcomes", -1)) != len(outcomes)
        or candidate_keys != outcome_keys
    ):
        raise ValueError("research raw rows do not reconcile")
    expected_metrics = aggregate_profile_metrics(candidate_profile_ids, outcomes)
    reported_metrics = tuple(
        _metrics_from_payload(value)
        for value in payload.get("profile_metrics", ())
    )
    if reported_metrics != expected_metrics:
        raise ValueError("research profile metrics do not reconcile")
    return payload, candidate_profile_ids, outcomes


def build_freeze_from_artifacts(
    research_artifacts: Sequence[str | Path],
):
    if len(research_artifacts) != 2:
        raise ValueError("freeze requires exactly two research artifacts")
    validated = tuple(
        _validated_research_rows(path) for path in research_artifacts
    )
    payloads = tuple(value[0] for value in validated)
    windows = {
        (
            tuple(date.fromisoformat(str(item)) for item in payload["signal_dates"]),
            date.fromisoformat(str(payload["outcome_cutoff"])),
        )
        for payload in payloads
    }
    if windows != set(RESEARCH_WINDOWS):
        raise ValueError("freeze requires the two exact research windows")
    comparable = (
        "formal_rule_version",
        "formal_policy_hash",
        "profile_matrix_hash",
        "evaluator_version",
        "cost_version",
    )
    if any(
        len({str(payload[key]) for payload in payloads}) != 1
        for key in comparable
    ):
        raise ValueError("research artifact versions mismatch")
    identities = tuple(str(payload["artifact_identity"]) for payload in payloads)
    candidate_profile_ids = tuple(
        item for value in validated for item in value[1]
    )
    outcomes = tuple(item for value in validated for item in value[2])
    profiles = build_threshold_profiles(SelectionPolicy())
    return freeze_threshold_profiles(
        profiles=profiles,
        training_identities=identities,
        metrics=aggregate_profile_metrics(candidate_profile_ids, outcomes),
        formal_rule_version=str(payloads[0]["formal_rule_version"]),
        formal_policy_hash=str(payloads[0]["formal_policy_hash"]),
        profile_matrix_hash=str(payloads[0]["profile_matrix_hash"]),
        risk_coverage_complete=all(
            bool(payload["risk_coverage_complete"]) for payload in payloads
        ),
    )


def build_test_review(
    start: date,
    end: date,
    cutoff: date,
    v5_case_path: str | Path,
    freeze_artifact: str | Path,
    *,
    input_loader: Callable[[date, date, date], CaseReviewInputs] = load_mysql_case_inputs,
) -> ThresholdWindowReview:
    expected_dates, expected_cutoff = TEST_WINDOW
    if (start, end, cutoff) != (
        expected_dates[0],
        expected_dates[-1],
        expected_cutoff,
    ):
        raise ValueError("test requires the exact August holdout")
    freeze = load_threshold_freeze_artifact(freeze_artifact)
    policy = SelectionPolicy()
    all_profiles = build_threshold_profiles(policy)
    if (
        freeze.formal_rule_version != policy.rule_version
        or freeze.formal_policy_hash != policy_hash(policy)
        or freeze.profile_matrix_hash != profile_matrix_hash(all_profiles)
    ):
        raise ValueError("freeze does not match the formal policy matrix")
    profile_by_id = {value.profile_id: value for value in all_profiles}
    frozen_ids = tuple(value.profile_id for value in freeze.profiles)
    if any(profile_id not in profile_by_id for profile_id in frozen_ids):
        raise ValueError("freeze contains unsupported profile IDs")
    profiles = tuple(profile_by_id[profile_id] for profile_id in frozen_ids)
    inputs = input_loader(start, end, cutoff)
    signal_dates = tuple(
        value for value in sorted(set(inputs.trading_dates)) if start <= value <= end
    )
    if signal_dates != expected_dates:
        raise ValueError("test input does not contain the exact August signal dates")
    if any(not inputs.holdings_complete_by_date.get(value, False) for value in signal_dates):
        raise ValueError("test window holdings are incomplete")
    future_dates = tuple(
        value
        for value in sorted(set(inputs.trading_dates))
        if signal_dates[-1] < value <= cutoff
    )
    if len(future_dates) != 5:
        raise ValueError("test window must contain exactly five outcome sessions")
    lineage = load_v5_recall_lineage(v5_case_path, signal_dates, cutoff)
    formal_replay = replay_case_signals(
        signal_dates=signal_dates,
        trading_dates=inputs.trading_dates,
        bars_by_code=inputs.bars_by_code,
        memberships=inputs.memberships,
        risk_flags=inputs.risk_flags,
        coverage_by_date=inputs.coverage_by_date,
        market_snapshots=inputs.market_snapshots,
        holding_codes_by_date=inputs.holding_codes_by_date,
        policy=policy,
    )
    shadow_replay = replay_threshold_shadows(
        signal_dates=signal_dates,
        trading_dates=inputs.trading_dates,
        bars_by_code=inputs.bars_by_code,
        memberships=inputs.memberships,
        risk_flags=inputs.risk_flags,
        coverage_by_date=inputs.coverage_by_date,
        market_snapshots=inputs.market_snapshots,
        holding_codes_by_date=inputs.holding_codes_by_date,
        profiles=profiles,
        formal_policy=policy,
    )
    shadow_outcomes = evaluate_threshold_outcomes(
        shadow_replay.candidates,
        inputs.bars_by_code,
        outcome_cutoff=cutoff,
    )
    selected = select_frozen_daily_candidates(shadow_replay.candidates, freeze)
    selected_outcomes = evaluate_threshold_outcomes(
        selected,
        inputs.bars_by_code,
        outcome_cutoff=cutoff,
    )
    formal_candidates = formal_replay.strict_shadow
    formal_outcomes = tuple(
        evaluate_case_plan(
            candidate,
            inputs.bars_by_code.get(candidate.code, ()),
            outcome_cutoff=cutoff,
        )
        for candidate in formal_candidates
    )
    formal_keys = {
        (value.signal_date, normalize_code6(value.code))
        for value in formal_candidates
    }
    risk_complete = all(
        inputs.coverage_by_date.get(value) is not None
        and inputs.coverage_by_date[value].announcement_complete
        for value in signal_dates
    )
    return ThresholdWindowReview(
        "test",
        signal_dates,
        cutoff,
        lineage.case_identity,
        case_input_fingerprint(inputs),
        policy.rule_version,
        policy_hash(policy),
        profile_matrix_hash(all_profiles),
        freeze.freeze_hash,
        profiles,
        shadow_replay,
        shadow_outcomes,
        aggregate_profile_metrics(
            tuple(value.profile_id for value in shadow_replay.candidates),
            shadow_outcomes,
        ),
        formal_candidates,
        formal_outcomes,
        selected,
        selected_outcomes,
        compare_exact_recall(selected, lineage.winner_keys, formal_keys),
        risk_complete and lineage.risk_coverage_complete,
        True,
    )
def _add_window_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--signal-start", type=date.fromisoformat, required=True)
    parser.add_argument("--signal-end", type=date.fromisoformat, required=True)
    parser.add_argument("--outcome-cutoff", type=date.fromisoformat, required=True)
    parser.add_argument("--v5-case", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="买点阈值影子研究（只读）")
    stages = parser.add_subparsers(dest="stage", required=True)
    research = stages.add_parser("research")
    _add_window_arguments(research)
    freeze = stages.add_parser("freeze")
    freeze.add_argument(
        "--research-artifact", action="append", required=True
    )
    freeze.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    test = stages.add_parser("test")
    _add_window_arguments(test)
    test.add_argument("--freeze-artifact", required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    input_loader: Callable[[date, date, date], CaseReviewInputs] = load_mysql_case_inputs,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.stage == "research":
            review = build_research_review(
                args.signal_start,
                args.signal_end,
                args.outcome_cutoff,
                args.v5_case,
                input_loader=input_loader,
            )
            paths = write_threshold_shadow_revision(review, args.output_dir)
        elif args.stage == "freeze":
            freeze = build_freeze_from_artifacts(args.research_artifact)
            paths = write_threshold_freeze(freeze, args.output_dir)
        else:
            review = build_test_review(
                args.signal_start,
                args.signal_end,
                args.outcome_cutoff,
                args.v5_case,
                args.freeze_artifact,
                input_loader=input_loader,
            )
            paths = write_threshold_shadow_revision(review, args.output_dir)
    except Exception as exc:
        print(f"阈值影子研究失败：{exc}", file=sys.stderr)
        return 2
    print("CASE_ANALYSIS_ONLY / NO-TRADE")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
