#!/usr/bin/env python3
"""Run manual, read-only structure-stop shadow research."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_OUTPUT_DIR = "output/research/buy_point_structure_stops"
RESEARCH_TERMINAL_CUTOFF = date(2026, 8, 14)


from scripts.analysis.review_buy_point_case import (  # noqa: E402
    CaseReviewInputs,
    load_mysql_case_inputs,
)
from scripts.analysis.review_buy_point_threshold_shadows import (  # noqa: E402
    case_input_fingerprint,
    load_v5_recall_lineage,
)
from stock_ai.buy_point_selection.case_review import (  # noqa: E402
    CaseOutcome,
    replay_case_signals,
)
from stock_ai.buy_point_selection.models import SelectionPolicy  # noqa: E402
from stock_ai.buy_point_selection.structure_stop_evaluation import (  # noqa: E402
    StructureStopMetrics,
    StructureStopOutcome,
    aggregate_structure_stop_metrics,
    evaluate_structure_stop_outcomes,
    freeze_structure_stop_profiles,
)
from stock_ai.buy_point_selection.structure_stop_report import (  # noqa: E402
    StructureStopResearchReview,
    write_structure_stop_freeze,
    write_structure_stop_research_revision,
)
from stock_ai.buy_point_selection.structure_stop_shadow import (  # noqa: E402
    StructureStopCandidate,
    build_structure_stop_profiles,
    replay_structure_stop_shadows,
    structure_stop_profile_hash,
)
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (  # noqa: E402
    ExactRecallComparison,
)
from stock_ai.buy_point_selection.validation import policy_hash  # noqa: E402
from stock_ai.market_codes import normalize_code6  # noqa: E402


def derive_structure_stop_windows(
    confirmed_dates: Sequence[date],
) -> tuple[tuple[tuple[date, ...], date], ...]:
    dates = tuple(confirmed_dates)
    if len(dates) != 80 or len(set(dates)) != 80:
        raise ValueError("research requires exactly 80 confirmed trading sessions")
    if dates != tuple(sorted(dates)):
        raise ValueError("confirmed trading sessions must be strictly ordered")
    return tuple(
        (dates[index : index + 5], dates[index + 9])
        for index in range(0, 80, 10)
    )


def _exact_recall(
    candidates: Sequence[StructureStopCandidate],
    winner_keys: frozenset[tuple[date, str]],
    formal_keys: set[tuple[date, str]],
) -> ExactRecallComparison:
    winners = {
        (signal_date, normalize_code6(code))
        for signal_date, code in winner_keys
    }
    formal = {
        (signal_date, normalize_code6(code))
        for signal_date, code in formal_keys
    }
    shadow = {
        (
            value.hit.signal_date,
            normalize_code6(value.hit.code),
        )
        for value in candidates
    }
    return ExactRecallComparison(
        len(winners),
        len(winners & formal),
        len(winners & shadow),
        len((winners & shadow) - formal),
        len(shadow - winners),
    )


def build_structure_stop_research_review(
    start: date,
    end: date,
    cutoff: date,
    v5_case_path: str | Path,
    *,
    input_loader: Callable[
        [date, date, date], CaseReviewInputs
    ] = load_mysql_case_inputs,
    confirmed_dates: Sequence[date] | None = None,
) -> StructureStopResearchReview:
    inputs = input_loader(start, end, cutoff)
    calendar_dates = (
        tuple(confirmed_dates)
        if confirmed_dates is not None
        else tuple(
            value
            for value in sorted(set(inputs.trading_dates))
            if value <= cutoff
        )[-80:]
    )
    windows = derive_structure_stop_windows(calendar_dates)
    signal_dates = tuple(
        value
        for value in sorted(set(inputs.trading_dates))
        if start <= value <= end
    )
    if (signal_dates, cutoff) not in windows:
        raise ValueError("research requires a derived research window")
    if any(
        not inputs.holdings_complete_by_date.get(value, False)
        for value in signal_dates
    ):
        raise ValueError("research holdings are incomplete")
    outcome_dates = tuple(
        value
        for value in sorted(set(inputs.trading_dates))
        if signal_dates[-1] < value <= cutoff
    )
    if len(outcome_dates) != 5 or outcome_dates[-1] != cutoff:
        raise ValueError("research requires exactly five outcome sessions")

    lineage = load_v5_recall_lineage(v5_case_path, signal_dates, cutoff)
    policy = SelectionPolicy()
    profiles = build_structure_stop_profiles()
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
    replay = replay_structure_stop_shadows(
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
    outcomes = evaluate_structure_stop_outcomes(
        replay.candidates,
        inputs.bars_by_code,
        outcome_cutoff=cutoff,
    )
    metrics = aggregate_structure_stop_metrics(
        tuple(
            (
                value.profile.profile_id,
                value.hit.setup.setup_type.value,
            )
            for value in replay.candidates
        ),
        outcomes,
    )
    formal_keys = {
        (value.signal_date, normalize_code6(value.code))
        for value in formal_replay.strict_shadow
    }
    announcements_complete = all(
        inputs.coverage_by_date.get(value) is not None
        and inputs.coverage_by_date[value].announcement_complete
        for value in signal_dates
    )
    return StructureStopResearchReview(
        signal_dates=signal_dates,
        outcome_cutoff=cutoff,
        v5_case_identity=lineage.case_identity,
        input_fingerprint=case_input_fingerprint(inputs),
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=structure_stop_profile_hash(profiles),
        profiles=profiles,
        replay=replay,
        outcomes=outcomes,
        profile_metrics=metrics,
        exact_recall=_exact_recall(
            replay.candidates,
            lineage.winner_keys,
            formal_keys,
        ),
        risk_coverage_complete=(
            announcements_complete and lineage.risk_coverage_complete
        ),
    )


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _outcome_from_payload(value: dict[str, object]) -> StructureStopOutcome:
    signal_date = date.fromisoformat(str(value["signal_date"]))
    code = normalize_code6(str(value["code"]))
    return StructureStopOutcome(
        str(value["profile_id"]),
        str(value["setup_type"]),
        code,
        signal_date,
        CaseOutcome(
            code=code,
            signal_date=signal_date,
            tier="STRUCTURE_STOP_SHADOW",
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
            intraday_order_ambiguous=bool(
                value["intraday_order_ambiguous"]
            ),
            structure_id=str(value["structure_id"]),
        ),
    )


def _metric_from_payload(value: dict[str, object]) -> StructureStopMetrics:
    return StructureStopMetrics(
        str(value["profile_id"]),
        str(value["setup_type"]),
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


def _research_identity(payload: dict[str, object]) -> str:
    identity = {
        key: payload[key]
        for key in (
            "schema",
            "stage",
            "signal_dates",
            "outcome_cutoff",
            "v5_case_identity",
            "input_fingerprint",
            "formal_rule_version",
            "formal_policy_hash",
            "profile_matrix_hash",
            "evaluator_version",
            "cost_version",
        )
    }
    encoded = json.dumps(
        identity, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _all_share_values(value: object) -> tuple[object, ...]:
    found = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            found.extend(
                child
                for key, child in item.items()
                if "shares" in str(key)
            )
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return tuple(found)


def _validated_research_rows(
    path: str | Path,
) -> tuple[
    dict[str, object],
    tuple[tuple[str, str], ...],
    tuple[StructureStopOutcome, ...],
]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    profiles = build_structure_stop_profiles()
    expected_profiles = [
        {
            "profile_id": value.profile_id,
            "anchor_kind": value.anchor_kind,
            "uses_atr_buffer": value.uses_atr_buffer,
        }
        for value in profiles
    ]
    policy = SelectionPolicy()
    if (
        payload.get("schema") != "buy-point-structure-stop-shadow-v1"
        or payload.get("stage") != "research"
        or payload.get("status") != "CASE_ANALYSIS_ONLY"
        or payload.get("trade_permission") != "NO-TRADE"
        or payload.get("retrospective") is not True
        or payload.get("promotion_eligible") is not False
        or payload.get("artifact_identity") != _research_identity(payload)
        or payload.get("formal_rule_version") != policy.rule_version
        or payload.get("formal_policy_hash") != policy_hash(policy)
        or payload.get("profile_matrix_hash")
        != structure_stop_profile_hash(profiles)
        or payload.get("evaluator_version") != "case-evaluator-v1"
        or payload.get("cost_version") != "execution-costs-default-v1"
        or payload.get("profiles") != expected_profiles
    ):
        raise ValueError("structure stop research lineage mismatch")
    row_names = (
        "baseline_hits",
        "candidates",
        "diagnostics",
        "rejections",
        "outcomes",
        "profile_metrics",
    )
    if any(not isinstance(payload.get(name), list) for name in row_names):
        raise ValueError("structure stop research rows are missing")
    if any(value != 0 for value in _all_share_values(payload)):
        raise ValueError("structure stop research rows must be zero-share")
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict) or any(
        int(metrics.get(name, -1)) != len(payload[name])
        for name in row_names
    ):
        raise ValueError("structure stop research counts do not reconcile")

    candidate_rows = tuple(payload["candidates"])
    diagnostic_rows = tuple(payload["diagnostics"])
    if any(
        value.get("label") == "DIAGNOSTIC_ONLY_COMBINED_FAILURE"
        for value in candidate_rows
    ):
        raise ValueError("structure stop research diagnostic entered candidates")
    if any(
        value.get("label") != "DIAGNOSTIC_ONLY_COMBINED_FAILURE"
        for value in diagnostic_rows
    ):
        raise ValueError("structure stop research diagnostic label mismatch")
    supported = {value.profile_id for value in profiles}
    try:
        candidate_ids = tuple(
            (str(value["profile_id"]), str(value["setup_type"]))
            for value in candidate_rows
        )
        candidate_keys = sorted(
            (
                str(value["signal_date"]),
                normalize_code6(str(value["code"])),
                str(value["profile_id"]),
            )
            for value in candidate_rows
        )
        outcomes = tuple(
            _outcome_from_payload(value) for value in payload["outcomes"]
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError("structure stop research raw row is invalid") from None
    outcome_keys = sorted(
        (
            value.signal_date.isoformat(),
            value.code,
            value.profile_id,
        )
        for value in outcomes
    )
    if (
        any(profile_id not in supported for profile_id, _ in candidate_ids)
        or len(candidate_keys) != len(set(candidate_keys))
        or len(outcome_keys) != len(set(outcome_keys))
        or candidate_keys != outcome_keys
    ):
        raise ValueError(
            "structure stop research candidate and outcome membership mismatch"
        )
    diagnostic_keys = {
        (
            str(value.get("signal_date")),
            normalize_code6(str(value.get("code"))),
        )
        for value in diagnostic_rows
    }
    candidate_date_codes = {
        (signal_date, code) for signal_date, code, _ in candidate_keys
    }
    if diagnostic_keys & candidate_date_codes:
        raise ValueError("structure stop research diagnostic overlap")
    expected_metrics = aggregate_structure_stop_metrics(
        candidate_ids,
        outcomes,
    )
    try:
        reported_metrics = tuple(
            _metric_from_payload(value) for value in payload["profile_metrics"]
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError("structure stop research metric is invalid") from None
    if reported_metrics != expected_metrics:
        raise ValueError("structure stop research metrics do not reconcile")
    return payload, candidate_ids, outcomes


def build_structure_stop_freeze_from_artifacts(
    research_artifacts: Sequence[str | Path],
    *,
    confirmed_dates: Sequence[date],
):
    if len(research_artifacts) != 8:
        raise ValueError("freeze requires exactly eight research artifacts")
    validated = tuple(
        _validated_research_rows(path) for path in research_artifacts
    )
    payloads = tuple(value[0] for value in validated)
    identities = tuple(str(value["artifact_identity"]) for value in payloads)
    if len(set(identities)) != 8:
        raise ValueError("freeze requires eight distinct research identities")
    windows = {
        (
            tuple(
                date.fromisoformat(str(item))
                for item in payload["signal_dates"]
            ),
            date.fromisoformat(str(payload["outcome_cutoff"])),
        )
        for payload in payloads
    }
    if windows != set(derive_structure_stop_windows(confirmed_dates)):
        raise ValueError("freeze requires the eight exact research windows")
    comparable = (
        "formal_rule_version",
        "formal_policy_hash",
        "profile_matrix_hash",
        "evaluator_version",
        "cost_version",
    )
    if any(
        len({str(value[key]) for value in payloads}) != 1
        for key in comparable
    ):
        raise ValueError("structure stop research artifact versions mismatch")
    candidate_ids = tuple(
        item for value in validated for item in value[1]
    )
    outcomes = tuple(item for value in validated for item in value[2])
    profiles = build_structure_stop_profiles()
    return freeze_structure_stop_profiles(
        profiles=profiles,
        training_identities=identities,
        metrics=aggregate_structure_stop_metrics(candidate_ids, outcomes),
        formal_rule_version=str(payloads[0]["formal_rule_version"]),
        formal_policy_hash=str(payloads[0]["formal_policy_hash"]),
        profile_matrix_hash=str(payloads[0]["profile_matrix_hash"]),
        risk_coverage_complete=all(
            bool(value["risk_coverage_complete"]) for value in payloads
        ),
    )


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="买点结构止损影子研究（手动、只读、零仓位）"
    )
    stages = parser.add_subparsers(dest="stage", required=True)

    research = stages.add_parser("research")
    research.add_argument("--signal-start", type=date.fromisoformat, required=True)
    research.add_argument("--signal-end", type=date.fromisoformat, required=True)
    research.add_argument("--outcome-cutoff", type=date.fromisoformat, required=True)
    research.add_argument("--v5-case", required=True)
    _add_output(research)

    freeze = stages.add_parser("freeze")
    freeze.add_argument("--research-artifact", action="append", required=True)
    _add_output(freeze)

    screen = stages.add_parser("screen")
    screen.add_argument("--signal-date", type=date.fromisoformat, required=True)
    screen.add_argument("--freeze-artifact", required=True)
    _add_output(screen)

    settle = stages.add_parser("settle")
    settle.add_argument("--screen-artifact", required=True)
    settle.add_argument("--outcome-cutoff", type=date.fromisoformat, required=True)
    _add_output(settle)
    return parser


def load_confirmed_structure_stop_dates() -> tuple[date, ...]:
    """Read the fixed 80-session research calendar without writing state."""
    import os

    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    from stock_ai.buy_point_selection.historical_replay_runtime import (
        _trade_dates,
    )

    load_dotenv(ROOT / ".env", override=False)
    mysql_url = os.environ.get("MYSQL_URL", "")
    if not mysql_url:
        raise RuntimeError("未配置 MYSQL_URL")
    engine = create_engine(mysql_url, pool_pre_ping=True)
    observed = _trade_dates(
        engine,
        RESEARCH_TERMINAL_CUTOFF - timedelta(days=180),
        RESEARCH_TERMINAL_CUTOFF,
    )
    dates = tuple(
        value for value in observed if value <= RESEARCH_TERMINAL_CUTOFF
    )[-80:]
    derive_structure_stop_windows(dates)
    if dates[-1] != RESEARCH_TERMINAL_CUTOFF:
        raise ValueError("研究日历未截止到 2026-08-14")
    return dates


def main(
    argv: Sequence[str] | None = None,
    *,
    input_loader: Callable[
        [date, date, date], CaseReviewInputs
    ] = load_mysql_case_inputs,
    confirmed_dates_loader: Callable[[], Sequence[date]] | None = None,
    research_writer: Callable[..., tuple[Path, Path]] | None = None,
    freeze_writer: Callable[..., tuple[Path, Path]] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    calendar_loader = (
        confirmed_dates_loader or load_confirmed_structure_stop_dates
    )
    research_output = research_writer or write_structure_stop_research_revision
    freeze_output = freeze_writer or write_structure_stop_freeze
    try:
        if args.stage == "research":
            confirmed_dates = tuple(calendar_loader())
            value = build_structure_stop_research_review(
                args.signal_start,
                args.signal_end,
                args.outcome_cutoff,
                args.v5_case,
                input_loader=input_loader,
                confirmed_dates=confirmed_dates,
            )
            paths = research_output(value, args.output_dir)
        elif args.stage == "freeze":
            confirmed_dates = tuple(calendar_loader())
            value = build_structure_stop_freeze_from_artifacts(
                args.research_artifact,
                confirmed_dates=confirmed_dates,
            )
            paths = freeze_output(value, args.output_dir)
        else:
            raise ValueError("screen/settle 将在 Task 6 实现")
    except Exception as exc:
        print(f"结构止损影子研究失败：{exc}", file=sys.stderr)
        return 2
    print("CASE_ANALYSIS_ONLY / NO-TRADE")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
