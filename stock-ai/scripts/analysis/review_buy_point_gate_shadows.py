#!/usr/bin/env python3
"""Run manual, read-only gate-shadow research and forward observation."""

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

from scripts.analysis.review_buy_point_case import (
    CaseReviewInputs,
    _load_benchmark_index_bars,
    _load_holdings_by_date,
    load_mysql_case_inputs,
)
from scripts.analysis.review_buy_point_threshold_shadows import (
    case_input_fingerprint,
    load_v5_recall_lineage,
)
from stock_ai.buy_point_selection.case_review import (
    CaseOutcome,
    evaluate_case_plan,
    replay_case_signals,
)
from stock_ai.buy_point_selection.gate_shadow_evaluation import (
    GateProfileMetrics,
    GateShadowOutcome,
    aggregate_gate_profile_metrics,
    evaluate_gate_shadow_outcomes,
    freeze_sector_gate_profiles,
    select_frozen_gate_candidates,
)
from stock_ai.buy_point_selection.gate_shadow_report import (
    GateForwardScreen,
    GateForwardSettlement,
    GateResearchReview,
    GateScreenCandidate,
    gate_screen_identity,
    load_gate_forward_screen,
    load_gate_profile_freeze,
    load_gate_research_artifact,
    write_gate_forward_screen,
    write_gate_forward_settlement,
    write_gate_profile_freeze,
    write_gate_research_revision,
)
from stock_ai.buy_point_selection.gate_shadow_research import (
    GateShadowCandidate,
    GateShadowHit,
    GateShadowProfile,
    build_gate_shadow_profiles,
    gate_profile_matrix_hash,
    replay_gate_shadows,
)
from stock_ai.buy_point_selection.historical_replay_runtime import (
    _load_daily_bars,
    _load_market_aggregates,
    _trade_dates,
    build_historical_market_snapshots,
)
from stock_ai.buy_point_selection.models import (
    DetectedSetup,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.reference_data import SQLReferenceRepository
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ExactRecallComparison,
)
from stock_ai.buy_point_selection.validation import policy_hash
from stock_ai.market_codes import normalize_code6
from stock_ai.trading_calendar import trading_day_status


DEFAULT_OUTPUT_DIR = "output/research/buy_point_gate_shadows"
RESEARCH_WINDOWS = (
    (tuple(date(2026, 7, day) for day in range(20, 25)), date(2026, 7, 31)),
    (tuple(date(2026, 7, day) for day in range(27, 32)), date(2026, 8, 7)),
    (tuple(date(2026, 8, day) for day in range(3, 8)), date(2026, 8, 14)),
)


def _approved_window(start: date, end: date, cutoff: date) -> tuple[date, ...]:
    for signal_dates, expected_cutoff in RESEARCH_WINDOWS:
        if (start, end, cutoff) == (
            signal_dates[0], signal_dates[-1], expected_cutoff
        ):
            return signal_dates
    raise ValueError("research requires an approved retrospective window")


def _exact_recall(
    candidates: Sequence[GateShadowCandidate],
    winner_keys: frozenset[tuple[date, str]],
    formal_keys: set[tuple[date, str]],
) -> ExactRecallComparison:
    winners = {
        (signal_date, normalize_code6(code)) for signal_date, code in winner_keys
    }
    formal = {
        (signal_date, normalize_code6(code)) for signal_date, code in formal_keys
    }
    shadow = {
        (value.hit.signal_date, normalize_code6(value.hit.code))
        for value in candidates
    }
    return ExactRecallComparison(
        len(winners),
        len(winners & formal),
        len(winners & shadow),
        len((winners & shadow) - formal),
        len(shadow - winners),
    )


def build_gate_research_review(
    start: date,
    end: date,
    cutoff: date,
    v5_case_path: str | Path,
    *,
    input_loader: Callable[[date, date, date], CaseReviewInputs] = load_mysql_case_inputs,
) -> GateResearchReview:
    expected_dates = _approved_window(start, end, cutoff)
    inputs = input_loader(start, end, cutoff)
    signal_dates = tuple(
        value for value in sorted(set(inputs.trading_dates)) if start <= value <= end
    )
    if signal_dates != expected_dates:
        raise ValueError("research input does not contain the exact signal dates")
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
    profiles = build_gate_shadow_profiles()
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
    replay = replay_gate_shadows(
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
    outcomes = evaluate_gate_shadow_outcomes(
        replay.candidates, inputs.bars_by_code, outcome_cutoff=cutoff
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
    announcements_complete = all(
        inputs.coverage_by_date.get(value) is not None
        and inputs.coverage_by_date[value].announcement_complete
        for value in signal_dates
    )
    return GateResearchReview(
        signal_dates,
        cutoff,
        lineage.case_identity,
        case_input_fingerprint(inputs),
        policy.rule_version,
        policy_hash(policy),
        gate_profile_matrix_hash(profiles),
        profiles,
        replay,
        outcomes,
        aggregate_gate_profile_metrics(
            tuple(value.hit.profile.profile_id for value in replay.candidates),
            outcomes,
        ),
        formal_candidates,
        formal_outcomes,
        _exact_recall(replay.candidates, lineage.winner_keys, formal_keys),
        announcements_complete and lineage.risk_coverage_complete,
    )


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _gate_outcome_from_payload(value: dict[str, object]) -> GateShadowOutcome:
    signal_date = date.fromisoformat(str(value["signal_date"]))
    code = normalize_code6(str(value["code"]))
    return GateShadowOutcome(
        str(value["profile_id"]),
        code,
        signal_date,
        CaseOutcome(
            code=code,
            signal_date=signal_date,
            tier="GATE_SHADOW",
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
        ),
    )


def _metric_from_payload(value: dict[str, object]) -> GateProfileMetrics:
    return GateProfileMetrics(
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
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _validated_research_rows(
    path: str | Path,
) -> tuple[dict[str, object], tuple[str, ...], tuple[GateShadowOutcome, ...]]:
    payload = load_gate_research_artifact(path)
    policy = SelectionPolicy()
    profiles = build_gate_shadow_profiles()
    expected_profile_payloads = [
        {
            "profile_id": value.profile_id,
            "gate": value.gate,
            "failure_reason": value.failure_reason,
            "mode": value.mode,
            "freeze_eligible": value.freeze_eligible,
        }
        for value in profiles
    ]
    if (
        payload.get("artifact_identity") != _research_identity(payload)
        or payload.get("formal_rule_version") != policy.rule_version
        or payload.get("formal_policy_hash") != policy_hash(policy)
        or payload.get("profile_matrix_hash") != gate_profile_matrix_hash(profiles)
        or payload.get("evaluator_version") != "case-evaluator-v1"
        or payload.get("cost_version") != "execution-costs-default-v1"
        or payload.get("profiles") != expected_profile_payloads
    ):
        raise ValueError("research artifact lineage mismatch")
    candidate_rows = tuple(payload.get("candidates", ()))
    outcome_rows = tuple(payload.get("outcomes", ()))
    raw_hits = tuple(payload.get("raw_hits", ()))
    if any(int(value.get("executable_shares", -1)) != 0 for value in (*raw_hits, *candidate_rows, *outcome_rows)):
        raise ValueError("research rows must be zero-share")
    profile_ids = tuple(str(value["profile_id"]) for value in candidate_rows)
    outcomes = tuple(_gate_outcome_from_payload(value) for value in outcome_rows)
    candidate_keys = sorted(
        (str(value["profile_id"]), str(value["signal_date"]), normalize_code6(str(value["code"])))
        for value in candidate_rows
    )
    outcome_keys = sorted(
        (value.profile_id, value.signal_date.isoformat(), value.code)
        for value in outcomes
    )
    metrics = payload.get("metrics")
    if (
        not isinstance(metrics, dict)
        or int(metrics.get("raw_hits", -1)) != len(raw_hits)
        or int(metrics.get("candidates", -1)) != len(candidate_rows)
        or int(metrics.get("outcomes", -1)) != len(outcomes)
        or candidate_keys != outcome_keys
    ):
        raise ValueError("research raw rows do not reconcile")
    expected_metrics = aggregate_gate_profile_metrics(profile_ids, outcomes)
    reported_metrics = tuple(
        _metric_from_payload(value) for value in payload.get("profile_metrics", ())
    )
    if reported_metrics != expected_metrics:
        raise ValueError("research profile metrics do not reconcile")
    return payload, profile_ids, outcomes


def build_gate_freeze_from_artifacts(
    research_artifacts: Sequence[str | Path],
):
    if len(research_artifacts) != 3:
        raise ValueError("freeze requires exactly three research artifacts")
    validated = tuple(_validated_research_rows(path) for path in research_artifacts)
    payloads = tuple(value[0] for value in validated)
    windows = {
        (
            tuple(date.fromisoformat(str(item)) for item in payload["signal_dates"]),
            date.fromisoformat(str(payload["outcome_cutoff"])),
        )
        for payload in payloads
    }
    if windows != set(RESEARCH_WINDOWS):
        raise ValueError("freeze requires the three exact research windows")
    identities = tuple(str(value["artifact_identity"]) for value in payloads)
    if len(set(identities)) != 3:
        raise ValueError("freeze requires three distinct research identities")
    comparable = (
        "formal_rule_version",
        "formal_policy_hash",
        "profile_matrix_hash",
        "evaluator_version",
        "cost_version",
    )
    if any(len({str(value[key]) for value in payloads}) != 1 for key in comparable):
        raise ValueError("research artifact versions mismatch")
    profile_ids = tuple(item for value in validated for item in value[1])
    outcomes = tuple(item for value in validated for item in value[2])
    profiles = build_gate_shadow_profiles()
    return freeze_sector_gate_profiles(
        profiles=profiles,
        training_identities=identities,
        metrics=aggregate_gate_profile_metrics(profile_ids, outcomes),
        formal_rule_version=str(payloads[0]["formal_rule_version"]),
        formal_policy_hash=str(payloads[0]["formal_policy_hash"]),
        profile_matrix_hash=str(payloads[0]["profile_matrix_hash"]),
        risk_coverage_complete=all(
            bool(value["risk_coverage_complete"]) for value in payloads
        ),
    )


def _confirmed_plan_dates(
    signal_date: date,
    calendar_status: Callable[[date], bool | None],
) -> tuple[date, date]:
    if calendar_status(signal_date) is not True:
        raise ValueError("signal date is not confirmed by the local trading calendar")
    result = []
    current = signal_date
    for _ in range(15):
        current += timedelta(days=1)
        status = calendar_status(current)
        if status is None:
            raise ValueError("future trading date is not confirmed locally")
        if status:
            result.append(current)
            if len(result) == 2:
                return result[0], result[1]
    raise ValueError("two future trading dates are not confirmed locally")


def load_mysql_gate_screen_inputs(
    signal_date: date, confirmed_plan_dates: tuple[date, date]
) -> CaseReviewInputs:
    import os

    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    load_dotenv(ROOT / ".env", override=False)
    mysql_url = os.environ.get("MYSQL_URL", "").replace(
        "host.docker.internal", "127.0.0.1"
    )
    if not mysql_url:
        raise RuntimeError("未配置 MYSQL_URL")
    engine = create_engine(mysql_url, pool_pre_ping=True)
    history_start = signal_date - timedelta(days=180)
    actual_dates = _trade_dates(engine, history_start, signal_date)
    if signal_date not in actual_dates:
        raise RuntimeError("信号日没有完整日线")
    bars_by_code = _load_daily_bars(engine, history_start, signal_date)
    repository = SQLReferenceRepository(engine)
    coverage = repository.coverage_between((signal_date,))
    memberships = repository.memberships_between(history_start, signal_date)
    risk_flags = repository.risk_flags_between(signal_date, signal_date)
    aggregates = _load_market_aggregates(engine, history_start, signal_date)
    indexes = _load_benchmark_index_bars(history_start, signal_date)
    snapshots = build_historical_market_snapshots(
        actual_dates,
        bars_by_code,
        indexes,
        market_aggregates_by_date=aggregates,
    )
    holdings, holdings_complete = _load_holdings_by_date(engine, (signal_date,))
    return CaseReviewInputs(
        (*actual_dates, *confirmed_plan_dates),
        bars_by_code,
        memberships,
        risk_flags,
        coverage,
        snapshots,
        holdings,
        holdings_complete,
    )


def build_gate_forward_screen(
    signal_date: date,
    freeze,
    *,
    input_loader: Callable[[date, tuple[date, date]], CaseReviewInputs] = load_mysql_gate_screen_inputs,
    calendar_status: Callable[[date], bool | None] = lambda value: trading_day_status(value, refresh=False),
) -> GateForwardScreen:
    if signal_date <= date(2026, 8, 7):
        raise ValueError("forward screen signal date must be after retrospective windows")
    policy = SelectionPolicy()
    profiles = build_gate_shadow_profiles()
    if (
        freeze.formal_rule_version != policy.rule_version
        or freeze.formal_policy_hash != policy_hash(policy)
        or freeze.profile_matrix_hash != gate_profile_matrix_hash(profiles)
        or any(value.profile_id.startswith("MARKET:") for value in freeze.profiles)
    ):
        raise ValueError("freeze does not match the formal gate matrix")
    plan_dates = _confirmed_plan_dates(signal_date, calendar_status)
    inputs = input_loader(signal_date, plan_dates)
    if signal_date not in inputs.trading_dates:
        raise ValueError("screen input is missing the signal session")
    if any(
        bar.trade_date > signal_date
        for bars in inputs.bars_by_code.values()
        for bar in bars
    ):
        raise ValueError("screen input contains future price bars")
    if not inputs.holdings_complete_by_date.get(signal_date, False):
        raise ValueError("screen holdings are incomplete")
    replay = replay_gate_shadows(
        signal_dates=(signal_date,),
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
    if replay.incomplete_dates:
        raise ValueError("screen reference or market facts are incomplete")
    selected = select_frozen_gate_candidates(replay.candidates, freeze)
    rank_by_profile = {value.profile_id: value.rank for value in freeze.profiles}
    candidates = tuple(
        GateScreenCandidate(value, rank_by_profile[value.hit.profile.profile_id])
        for value in selected
    )
    coverage = inputs.coverage_by_date.get(signal_date)
    return GateForwardScreen(
        signal_date,
        case_input_fingerprint(inputs),
        policy.rule_version,
        policy_hash(policy),
        gate_profile_matrix_hash(profiles),
        freeze.freeze_hash,
        candidates,
        bool(coverage and coverage.announcement_complete),
    )


def load_mysql_gate_settlement_inputs(
    signal_date: date, outcome_cutoff: date
) -> CaseReviewInputs:
    return load_mysql_case_inputs(signal_date, signal_date, outcome_cutoff)


def _candidate_from_payload(
    value: dict[str, object], profiles: dict[str, GateShadowProfile]
) -> GateScreenCandidate:
    profile_id = str(value["profile_id"])
    if profile_id not in profiles:
        raise ValueError("screen contains unsupported profile")
    signal_date = date.fromisoformat(str(value["signal_date"]))
    code = normalize_code6(str(value["code"]))
    setup = DetectedSetup(
        code,
        SetupType(str(value["setup_type"])),
        signal_date,
        date.fromisoformat(str(value["structure_start"])),
        Decimal(str(value["structure_high"])),
        Decimal(str(value["structure_low"])),
        Decimal(str(value["setup_quality"])),
        tuple(str(item) for item in value["setup_reasons"]),
        {key: Decimal(str(item)) for key, item in value["setup_metrics"].items()},
    )
    hit = GateShadowHit(
        code,
        signal_date,
        profiles[profile_id],
        setup,
        str(value["market_status"]),
        str(value["sector_code"]),
    )
    plan = PricePlan(
        str(value["structure_id"]),
        code,
        setup.setup_type,
        signal_date,
        Decimal(str(value["signal_close"])),
        Decimal(str(value["trigger_price"])),
        Decimal(str(value["invalidation_price"])),
        Decimal(str(value["target_2r"])),
        Decimal(str(value["risk_distance"])),
        Decimal(str(value["risk_reward_ratio"])),
        0,
        date.fromisoformat(str(value["plan_expiry"])),
    )
    candidate = GateShadowCandidate(
        hit,
        plan,
        Decimal(str(value["average_amount5_qian"])),
        Decimal(str(value["two_r_space_buffer"])),
    )
    return GateScreenCandidate(candidate, int(value["profile_rank"]))


def build_gate_forward_settlement(
    screen_artifact: str | Path,
    outcome_cutoff: date,
    *,
    input_loader: Callable[[date, date], CaseReviewInputs] = load_mysql_gate_settlement_inputs,
) -> GateForwardSettlement:
    payload = load_gate_forward_screen(screen_artifact)
    signal_date = date.fromisoformat(str(payload["signal_date"]))
    inputs = input_loader(signal_date, outcome_cutoff)
    outcome_dates = tuple(
        value
        for value in sorted(set(inputs.trading_dates))
        if signal_date < value <= outcome_cutoff
    )
    if len(outcome_dates) != 5 or outcome_dates[-1] != outcome_cutoff:
        raise ValueError("settlement requires exactly five completed outcome sessions")
    profiles = {value.profile_id: value for value in build_gate_shadow_profiles()}
    candidates = tuple(
        _candidate_from_payload(value, profiles)
        for value in payload.get("candidates", ())
    )
    outcomes = evaluate_gate_shadow_outcomes(
        tuple(value.candidate for value in candidates),
        inputs.bars_by_code,
        outcome_cutoff=outcome_cutoff,
    )
    return GateForwardSettlement(
        str(payload["artifact_identity"]),
        signal_date,
        outcome_cutoff,
        outcome_dates,
        str(payload["freeze_hash"]),
        case_input_fingerprint(inputs),
        candidates,
        outcomes,
        bool(payload["risk_coverage_complete"]),
    )


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="买点门禁影子研究（只读、零仓位）")
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.stage == "research":
            value = build_gate_research_review(
                args.signal_start,
                args.signal_end,
                args.outcome_cutoff,
                args.v5_case,
            )
            paths = write_gate_research_revision(value, args.output_dir)
        elif args.stage == "freeze":
            value = build_gate_freeze_from_artifacts(args.research_artifact)
            paths = write_gate_profile_freeze(value, args.output_dir)
        elif args.stage == "screen":
            freeze = load_gate_profile_freeze(args.freeze_artifact)
            value = build_gate_forward_screen(args.signal_date, freeze)
            paths = write_gate_forward_screen(value, args.output_dir)
        else:
            value = build_gate_forward_settlement(
                args.screen_artifact, args.outcome_cutoff
            )
            paths = write_gate_forward_settlement(value, args.output_dir)
    except Exception as exc:
        print(f"门禁影子研究失败：{exc}", file=sys.stderr)
        return 2
    print("CASE_ANALYSIS_ONLY / NO-TRADE")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
