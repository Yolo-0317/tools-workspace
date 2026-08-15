"""Immutable evidence artifacts for structure-stop case research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from typing import Sequence

from stock_ai.market_codes import normalize_code6

from .structure_stop_evaluation import (
    FrozenStructureStopProfile,
    StructureStopFreeze,
    StructureStopMetrics,
    StructureStopOutcome,
    validate_structure_stop_freeze,
)
from .structure_stop_shadow import (
    StructureStopCandidate,
    StructureStopProfile,
    StructureStopReplay,
    build_structure_stop_profiles,
    structure_stop_profile_hash,
    validate_structure_stop_profiles,
)
from .threshold_shadow_evaluation import ExactRecallComparison


STRUCTURE_STOP_SCHEMA = "buy-point-structure-stop-shadow-v1"


@dataclass(frozen=True)
class StructureStopResearchReview:
    signal_dates: tuple[date, ...]
    outcome_cutoff: date
    v5_case_identity: str
    input_fingerprint: str
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    profiles: tuple[StructureStopProfile, ...]
    replay: StructureStopReplay
    outcomes: tuple[StructureStopOutcome, ...]
    profile_metrics: tuple[StructureStopMetrics, ...]
    exact_recall: ExactRecallComparison
    risk_coverage_complete: bool


@dataclass(frozen=True)
class StructureStopScreenCandidate:
    candidate: StructureStopCandidate
    profile_rank: int


@dataclass(frozen=True)
class StructureStopForwardScreen:
    signal_date: date
    input_fingerprint: str
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    freeze_hash: str
    candidates: tuple[StructureStopScreenCandidate, ...]
    risk_coverage_complete: bool


@dataclass(frozen=True)
class StructureStopForwardSettlement:
    parent_screen_identity: str
    signal_date: date
    outcome_cutoff: date
    outcome_dates: tuple[date, ...]
    freeze_hash: str
    input_fingerprint: str
    candidates: tuple[StructureStopScreenCandidate, ...]
    outcomes: tuple[StructureStopOutcome, ...]
    risk_coverage_complete: bool


def _short_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _profile_payload(value: StructureStopProfile) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "anchor_kind": value.anchor_kind,
        "uses_atr_buffer": value.uses_atr_buffer,
    }


def _hit_payload(value) -> dict[str, object]:
    return {
        "signal_date": value.signal_date.isoformat(),
        "code": normalize_code6(value.code),
        "setup_type": value.setup.setup_type.value,
        "setup_quality": str(value.setup.quality),
        "market_status": value.market_status,
        "sector_code": value.sector_code,
        "baseline_reasons": list(value.baseline_reasons),
        "executable_shares": 0,
    }


def _candidate_payload(value: StructureStopCandidate) -> dict[str, object]:
    return {
        "signal_date": value.hit.signal_date.isoformat(),
        "code": normalize_code6(value.hit.code),
        "profile_id": value.profile.profile_id,
        "anchor_kind": value.profile.anchor_kind,
        "anchor_price": _decimal(value.anchor.anchor_price),
        "invalidation_price": _decimal(value.anchor.invalidation_price),
        "anchor_reasons": list(value.anchor.reasons),
        "setup_type": value.hit.setup.setup_type.value,
        "setup_quality": str(value.hit.setup.quality),
        "structure_start": value.hit.setup.structure_start.isoformat(),
        "structure_high": str(value.hit.setup.structure_high),
        "structure_low": str(value.hit.setup.structure_low),
        "setup_reasons": list(value.hit.setup.reasons),
        "setup_metrics": {
            key: str(item)
            for key, item in sorted(value.hit.setup.metrics.items())
        },
        "market_status": value.hit.market_status,
        "sector_code": value.hit.sector_code,
        "structure_id": value.plan.structure_id,
        "signal_close": str(value.plan.signal_close),
        "trigger_price": str(value.plan.trigger_price),
        "target_2r": str(value.plan.target_2r),
        "risk_distance": str(value.plan.risk_distance),
        "risk_reward_ratio": str(value.plan.risk_reward_ratio),
        "maximum_shares": 0,
        "plan_expiry": value.plan.valid_through_trade_date.isoformat(),
        "average_amount5_qian": str(value.average_amount5_qian),
        "two_r_space_buffer": str(value.two_r_space_buffer),
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "executable_shares": 0,
    }


def _diagnostic_payload(value) -> dict[str, object]:
    return {
        "signal_date": value.signal_date.isoformat(),
        "code": normalize_code6(value.code),
        "gate": value.gate,
        "gate_reason": value.gate_reason,
        "baseline_reason": value.baseline_reason,
        "label": value.label,
        "executable_shares": 0,
    }


def _outcome_payload(value: StructureStopOutcome) -> dict[str, object]:
    outcome = value.outcome
    return {
        "profile_id": value.profile_id,
        "setup_type": value.setup_type,
        "signal_date": value.signal_date.isoformat(),
        "code": normalize_code6(value.code),
        "status": outcome.status,
        "trigger_date": (
            None
            if outcome.trigger_date is None
            else outcome.trigger_date.isoformat()
        ),
        "net_return": _decimal(outcome.net_return),
        "close_return": _decimal(outcome.close_return),
        "mfe": _decimal(outcome.mfe),
        "mae": _decimal(outcome.mae),
        "stop_first": outcome.stop_first,
        "intraday_order_ambiguous": outcome.intraday_order_ambiguous,
        "structure_id": outcome.structure_id,
        "executable_shares": 0,
    }


def _metric_payload(value: StructureStopMetrics) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "setup_type": value.setup_type,
        "candidate_count": value.candidate_count,
        "triggered": value.triggered,
        "resolved": value.resolved,
        "positive_net": value.positive_net,
        "stop_first": value.stop_first,
        "mean_net_return": _decimal(value.mean_net_return),
        "median_net_return": _decimal(value.median_net_return),
        "positive_net_rate": _decimal(value.positive_net_rate),
        "stop_first_rate": _decimal(value.stop_first_rate),
        "mean_mfe": _decimal(value.mean_mfe),
        "mean_mae": _decimal(value.mean_mae),
        "qualifies": value.qualifies,
        "qualification_reasons": list(value.qualification_reasons),
    }


def _exact_recall_payload(value: ExactRecallComparison) -> dict[str, int]:
    return {
        "actionable_winner_pairs": value.actionable_winner_pairs,
        "formal_captured_pairs": value.formal_captured_pairs,
        "shadow_captured_pairs": value.shadow_captured_pairs,
        "incremental_captured_pairs": value.incremental_captured_pairs,
        "selected_non_winner_pairs": value.selected_non_winner_pairs,
    }


def _research_identity(review: StructureStopResearchReview) -> str:
    return _short_hash(
        {
            "schema": STRUCTURE_STOP_SCHEMA,
            "stage": "research",
            "signal_dates": [
                value.isoformat() for value in sorted(review.signal_dates)
            ],
            "outcome_cutoff": review.outcome_cutoff.isoformat(),
            "v5_case_identity": review.v5_case_identity,
            "input_fingerprint": review.input_fingerprint,
            "formal_rule_version": review.formal_rule_version,
            "formal_policy_hash": review.formal_policy_hash,
            "profile_matrix_hash": review.profile_matrix_hash,
            "evaluator_version": "case-evaluator-v1",
            "cost_version": "execution-costs-default-v1",
        }
    )


def _candidate_key(value: StructureStopCandidate) -> tuple[date, str, str]:
    return (
        value.hit.signal_date,
        normalize_code6(value.hit.code),
        value.profile.profile_id,
    )


def _outcome_key(value: StructureStopOutcome) -> tuple[date, str, str]:
    return (
        value.signal_date,
        normalize_code6(value.code),
        value.profile_id,
    )


def structure_stop_research_payload(
    review: StructureStopResearchReview,
) -> dict[str, object]:
    validate_structure_stop_profiles(review.profiles)
    if review.profile_matrix_hash != structure_stop_profile_hash(
        review.profiles
    ):
        raise ValueError("structure stop profile matrix hash mismatch")
    share_values = [
        *(value.executable_shares for value in review.replay.baseline_hits),
        *(value.executable_shares for value in review.replay.candidates),
        *(value.anchor.executable_shares for value in review.replay.candidates),
        *(value.executable_shares for value in review.replay.diagnostics),
        *(value.executable_shares for value in review.outcomes),
    ]
    if any(value != 0 for value in share_values):
        raise ValueError("structure stop artifacts must be zero-share")
    candidate_keys = {_candidate_key(value) for value in review.replay.candidates}
    outcome_keys = {_outcome_key(value) for value in review.outcomes}
    if (
        len(candidate_keys) != len(review.replay.candidates)
        or len(outcome_keys) != len(review.outcomes)
        or candidate_keys != outcome_keys
    ):
        raise ValueError("candidate and outcome membership mismatch")
    diagnostic_keys = {
        (value.signal_date, normalize_code6(value.code))
        for value in review.replay.diagnostics
    }
    candidate_date_codes = {
        (value.hit.signal_date, normalize_code6(value.hit.code))
        for value in review.replay.candidates
    }
    if diagnostic_keys & candidate_date_codes:
        raise ValueError("diagnostic cohort overlaps primary candidates")
    supported = {value.profile_id for value in review.profiles}
    if any(value.profile_id not in supported for value in review.profile_metrics):
        raise ValueError("diagnostic profile cannot enter metrics")
    candidates = tuple(
        sorted(review.replay.candidates, key=_candidate_key)
    )
    outcomes = tuple(sorted(review.outcomes, key=_outcome_key))
    baseline_hits = tuple(
        sorted(
            review.replay.baseline_hits,
            key=lambda value: (value.signal_date, normalize_code6(value.code)),
        )
    )
    diagnostics = tuple(
        sorted(
            review.replay.diagnostics,
            key=lambda value: (
                value.signal_date,
                normalize_code6(value.code),
                value.gate,
                value.gate_reason,
            ),
        )
    )
    rejections = tuple(
        sorted(
            review.replay.rejections,
            key=lambda value: (
                value.signal_date,
                normalize_code6(value.code),
                value.profile_id or "",
                value.stage,
                value.reasons,
            ),
        )
    )
    profile_order = {
        value.profile_id: index for index, value in enumerate(review.profiles)
    }
    profile_metrics = tuple(
        sorted(
            review.profile_metrics,
            key=lambda value: (
                profile_order[value.profile_id],
                value.setup_type != "ALL",
                value.setup_type,
            ),
        )
    )
    return {
        "schema": STRUCTURE_STOP_SCHEMA,
        "stage": "research",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": True,
        "artifact_identity": _research_identity(review),
        "signal_dates": [
            value.isoformat() for value in sorted(review.signal_dates)
        ],
        "outcome_cutoff": review.outcome_cutoff.isoformat(),
        "v5_case_identity": review.v5_case_identity,
        "input_fingerprint": review.input_fingerprint,
        "formal_rule_version": review.formal_rule_version,
        "formal_policy_hash": review.formal_policy_hash,
        "profile_matrix_hash": review.profile_matrix_hash,
        "evaluator_version": "case-evaluator-v1",
        "cost_version": "execution-costs-default-v1",
        "risk_coverage_complete": review.risk_coverage_complete,
        "promotion_eligible": False,
        "profiles": [_profile_payload(value) for value in review.profiles],
        "baseline_hits": [_hit_payload(value) for value in baseline_hits],
        "candidates": [_candidate_payload(value) for value in candidates],
        "diagnostics": [_diagnostic_payload(value) for value in diagnostics],
        "rejections": [
            {
                "signal_date": value.signal_date.isoformat(),
                "code": normalize_code6(value.code),
                "profile_id": value.profile_id,
                "stage": value.stage,
                "reasons": list(value.reasons),
            }
            for value in rejections
        ],
        "outcomes": [_outcome_payload(value) for value in outcomes],
        "profile_metrics": [
            _metric_payload(value) for value in profile_metrics
        ],
        "exact_recall": _exact_recall_payload(review.exact_recall),
        "metrics": {
            "baseline_hits": len(baseline_hits),
            "candidates": len(candidates),
            "diagnostics": len(diagnostics),
            "rejections": len(rejections),
            "outcomes": len(outcomes),
            "profile_metrics": len(profile_metrics),
        },
    }


def structure_stop_freeze_payload(
    value: StructureStopFreeze,
) -> dict[str, object]:
    validate_structure_stop_freeze(value)
    return {
        "schema": value.schema,
        "stage": "freeze",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": value.retrospective,
        "training_identities": list(value.training_identities),
        "formal_rule_version": value.formal_rule_version,
        "formal_policy_hash": value.formal_policy_hash,
        "profile_matrix_hash": value.profile_matrix_hash,
        "profiles": [
            {
                "profile_id": item.profile_id,
                "rank": item.rank,
                "training_metrics": _metric_payload(
                    item.training_metrics
                ),
                "executable_shares": 0,
            }
            for item in value.profiles
        ],
        "empty": value.empty,
        "risk_coverage_complete": value.risk_coverage_complete,
        "promotion_eligible": value.promotion_eligible,
        "freeze_hash": value.freeze_hash,
    }


def _render_markdown(title: str, payload: dict[str, object]) -> str:
    return "\n".join(
        (
            f"# {title}",
            "",
            "状态：`CASE_ANALYSIS_ONLY`",
            "交易权限：`NO-TRADE`",
            "",
            "本产物仅用于案例研究，不生成交易建议；可执行仓位为 0。",
            "",
            f"- 阶段：`{payload['stage']}`",
            f"- 产物标识：`{payload.get('artifact_identity', payload.get('freeze_hash'))}`",
            f"- 风险覆盖完整：{'是' if payload['risk_coverage_complete'] else '否'}",
            "- 正式晋级：禁止",
            "",
        )
    )


def render_structure_stop_research_markdown(
    review: StructureStopResearchReview,
) -> str:
    return _render_markdown(
        "买点结构止损影子研究",
        structure_stop_research_payload(review),
    )


def render_structure_stop_freeze_markdown(
    value: StructureStopFreeze,
) -> str:
    return _render_markdown(
        "买点结构止损影子冻结配置",
        structure_stop_freeze_payload(value),
    )


def _write_exclusive_or_verify(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("immutable artifact content mismatch")


def _write_pair(
    output_dir: str | Path,
    stem: str,
    payload: dict[str, object],
    markdown: str,
) -> tuple[Path, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / f"{stem}.json"
    markdown_path = target / f"{stem}.md"
    json_content = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n"
    _write_exclusive_or_verify(json_path, json_content)
    _write_exclusive_or_verify(markdown_path, markdown)
    return json_path, markdown_path


def write_structure_stop_research_revision(
    review: StructureStopResearchReview,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    dates = tuple(sorted(review.signal_dates))
    if not dates:
        raise ValueError("research requires signal dates")
    identity = _research_identity(review)
    stem = (
        f"research_{dates[0]:%Y%m%d}_{dates[-1]:%Y%m%d}_"
        f"cutoff-{review.outcome_cutoff:%Y%m%d}_{identity}"
    )
    payload = structure_stop_research_payload(review)
    return _write_pair(
        output_dir,
        stem,
        payload,
        _render_markdown("买点结构止损影子研究", payload),
    )


def write_structure_stop_freeze(
    value: StructureStopFreeze,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    payload = structure_stop_freeze_payload(value)
    return _write_pair(
        output_dir,
        f"freeze-{value.freeze_hash}",
        payload,
        _render_markdown("买点结构止损影子冻结配置", payload),
    )


def _metric_from_payload(value: dict[str, object]) -> StructureStopMetrics:
    def decimal(key: str) -> Decimal | None:
        raw = value.get(key)
        return None if raw is None else Decimal(str(raw))

    return StructureStopMetrics(
        str(value["profile_id"]),
        str(value["setup_type"]),
        int(value["candidate_count"]),
        int(value["triggered"]),
        int(value["resolved"]),
        int(value["positive_net"]),
        int(value["stop_first"]),
        decimal("mean_net_return"),
        decimal("median_net_return"),
        decimal("positive_net_rate"),
        decimal("stop_first_rate"),
        decimal("mean_mfe"),
        decimal("mean_mae"),
        bool(value["qualifies"]),
        tuple(str(item) for item in value["qualification_reasons"]),
    )


def load_structure_stop_freeze(path: str | Path) -> StructureStopFreeze:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema") != STRUCTURE_STOP_SCHEMA
        or payload.get("stage") != "freeze"
        or payload.get("status") != "CASE_ANALYSIS_ONLY"
        or payload.get("trade_permission") != "NO-TRADE"
        or payload.get("retrospective") is not True
        or payload.get("promotion_eligible") is not False
    ):
        raise ValueError("expected safely labeled structure stop freeze")
    profiles = tuple(
        FrozenStructureStopProfile(
            str(item["profile_id"]),
            int(item["rank"]),
            _metric_from_payload(item["training_metrics"]),
        )
        for item in payload["profiles"]
    )
    value = StructureStopFreeze(
        str(payload["schema"]),
        tuple(str(item) for item in payload["training_identities"]),
        str(payload["formal_rule_version"]),
        str(payload["formal_policy_hash"]),
        str(payload["profile_matrix_hash"]),
        profiles,
        bool(payload["retrospective"]),
        bool(payload["empty"]),
        bool(payload["risk_coverage_complete"]),
        bool(payload["promotion_eligible"]),
        str(payload["freeze_hash"]),
    )
    validate_structure_stop_freeze(value)
    if any(int(item.get("executable_shares", -1)) != 0 for item in payload["profiles"]):
        raise ValueError("structure stop freeze profiles must be zero-share")
    return value


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_HEX_16 = re.compile(r"^[0-9a-f]{16}$")
_SCREEN_TOP_LEVEL_KEYS = {
    "schema",
    "stage",
    "status",
    "trade_permission",
    "retrospective",
    "artifact_identity",
    "signal_date",
    "input_fingerprint",
    "formal_rule_version",
    "formal_policy_hash",
    "profile_matrix_hash",
    "freeze_hash",
    "planner_version",
    "risk_coverage_complete",
    "promotion_eligible",
    "candidates",
    "metrics",
}
_SCREEN_CANDIDATE_KEYS = {
    "signal_date",
    "code",
    "profile_id",
    "profile_rank",
    "anchor_kind",
    "anchor_price",
    "invalidation_price",
    "anchor_reasons",
    "setup_type",
    "setup_quality",
    "structure_start",
    "structure_high",
    "structure_low",
    "setup_reasons",
    "setup_metrics",
    "market_status",
    "sector_code",
    "structure_id",
    "signal_close",
    "trigger_price",
    "target_2r",
    "risk_distance",
    "risk_reward_ratio",
    "maximum_shares",
    "plan_expiry",
    "average_amount5_qian",
    "two_r_space_buffer",
    "status",
    "trade_permission",
    "executable_shares",
}


def _validate_screen_candidate(
    value: StructureStopScreenCandidate,
    *,
    signal_date: date,
) -> None:
    if not isinstance(value, StructureStopScreenCandidate):
        raise ValueError("structure stop screen candidate required")
    candidate = value.candidate
    supported = build_structure_stop_profiles()
    if (
        not isinstance(candidate, StructureStopCandidate)
        or candidate.profile not in supported
        or candidate.anchor.profile != candidate.profile
        or value.profile_rank <= 0
    ):
        raise ValueError("structure stop screen profile is invalid")
    code = normalize_code6(candidate.hit.code)
    if (
        candidate.hit.signal_date != signal_date
        or candidate.hit.setup.analysis_date != signal_date
        or candidate.anchor.signal_date != signal_date
        or candidate.plan.signal_date != signal_date
        or normalize_code6(candidate.hit.setup.code) != code
        or normalize_code6(candidate.anchor.code) != code
        or normalize_code6(candidate.plan.code) != code
        or candidate.plan.setup_type != candidate.hit.setup.setup_type
    ):
        raise ValueError("structure stop screen signal lineage mismatch")
    if (
        candidate.executable_shares != 0
        or candidate.hit.executable_shares != 0
        or candidate.anchor.executable_shares != 0
        or candidate.status != "CASE_ANALYSIS_ONLY"
        or candidate.trade_permission != "NO-TRADE"
    ):
        raise ValueError("structure stop screen must remain zero-share")


def _screen_candidate_payload(
    value: StructureStopScreenCandidate,
) -> dict[str, object]:
    payload = _candidate_payload(value.candidate)
    payload["profile_rank"] = value.profile_rank
    return payload


def _screen_identity_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema": payload["schema"],
        "stage": payload["stage"],
        "signal_date": payload["signal_date"],
        "input_fingerprint": payload["input_fingerprint"],
        "formal_rule_version": payload["formal_rule_version"],
        "formal_policy_hash": payload["formal_policy_hash"],
        "profile_matrix_hash": payload["profile_matrix_hash"],
        "freeze_hash": payload["freeze_hash"],
        "planner_version": payload["planner_version"],
        "risk_coverage_complete": payload["risk_coverage_complete"],
        "candidates": payload["candidates"],
    }


def structure_stop_screen_identity(
    value: StructureStopForwardScreen,
) -> str:
    payload = structure_stop_screen_payload(value)
    return str(payload["artifact_identity"])


def structure_stop_screen_payload(
    value: StructureStopForwardScreen,
) -> dict[str, object]:
    if not isinstance(value, StructureStopForwardScreen):
        raise ValueError("structure stop screen required")
    expected_profile_hash = structure_stop_profile_hash(
        build_structure_stop_profiles()
    )
    if (
        not value.input_fingerprint
        or not value.formal_rule_version
        or not _HEX_64.fullmatch(value.formal_policy_hash)
        or value.profile_matrix_hash != expected_profile_hash
        or not _HEX_64.fullmatch(value.freeze_hash)
        or not isinstance(value.risk_coverage_complete, bool)
        or len(value.candidates) > 5
    ):
        raise ValueError("structure stop screen lineage is invalid")
    for item in value.candidates:
        _validate_screen_candidate(item, signal_date=value.signal_date)
    keys = tuple(
        (
            item.candidate.hit.signal_date,
            normalize_code6(item.candidate.hit.code),
            item.candidate.profile.profile_id,
        )
        for item in value.candidates
    )
    if len(set(keys)) != len(keys):
        raise ValueError("structure stop screen contains duplicate candidates")
    candidates = [
        _screen_candidate_payload(item)
        for item in sorted(
            value.candidates,
            key=lambda item: (
                item.profile_rank,
                normalize_code6(item.candidate.hit.code),
                item.candidate.profile.profile_id,
            ),
        )
    ]
    payload: dict[str, object] = {
        "schema": STRUCTURE_STOP_SCHEMA,
        "stage": "screen",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": False,
        "signal_date": value.signal_date.isoformat(),
        "input_fingerprint": value.input_fingerprint,
        "formal_rule_version": value.formal_rule_version,
        "formal_policy_hash": value.formal_policy_hash,
        "profile_matrix_hash": value.profile_matrix_hash,
        "freeze_hash": value.freeze_hash,
        "planner_version": "price-plan-v1",
        "risk_coverage_complete": value.risk_coverage_complete,
        "promotion_eligible": False,
        "candidates": candidates,
        "metrics": {"selected": len(candidates)},
    }
    payload["artifact_identity"] = _short_hash(
        _screen_identity_payload(payload)
    )
    return payload


def write_structure_stop_forward_screen(
    value: StructureStopForwardScreen,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    payload = structure_stop_screen_payload(value)
    stem = (
        f"screen_{value.signal_date:%Y%m%d}_"
        f"{payload['artifact_identity']}"
    )
    return _write_pair(
        output_dir,
        stem,
        payload,
        _render_markdown("买点结构止损前向筛选", payload),
    )


def load_structure_stop_forward_screen(
    path: str | Path,
) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        candidates = payload["candidates"]
        if (
            set(payload) != _SCREEN_TOP_LEVEL_KEYS
            or payload["schema"] != STRUCTURE_STOP_SCHEMA
            or payload["stage"] != "screen"
            or payload["status"] != "CASE_ANALYSIS_ONLY"
            or payload["trade_permission"] != "NO-TRADE"
            or payload["retrospective"] is not False
            or payload["promotion_eligible"] is not False
            or payload["planner_version"] != "price-plan-v1"
            or not isinstance(payload["risk_coverage_complete"], bool)
            or not _HEX_64.fullmatch(payload["formal_policy_hash"])
            or payload["profile_matrix_hash"]
            != structure_stop_profile_hash(build_structure_stop_profiles())
            or not _HEX_64.fullmatch(payload["freeze_hash"])
            or not _HEX_16.fullmatch(payload["artifact_identity"])
            or not isinstance(candidates, list)
            or len(candidates) > 5
            or payload["metrics"] != {"selected": len(candidates)}
        ):
            raise ValueError
        signal_date = str(payload["signal_date"])
        supported = {
            item.profile_id for item in build_structure_stop_profiles()
        }
        keys = []
        for item in candidates:
            if (
                not isinstance(item, dict)
                or set(item) != _SCREEN_CANDIDATE_KEYS
                or item["signal_date"] != signal_date
                or item["profile_id"] not in supported
                or int(item["profile_rank"]) <= 0
                or item["status"] != "CASE_ANALYSIS_ONLY"
                or item["trade_permission"] != "NO-TRADE"
                or item["executable_shares"] != 0
                or item["maximum_shares"] != 0
            ):
                raise ValueError
            keys.append(
                (
                    item["signal_date"],
                    normalize_code6(str(item["code"])),
                    item["profile_id"],
                )
            )
        if len(keys) != len(set(keys)):
            raise ValueError
        expected_identity = _short_hash(_screen_identity_payload(payload))
        if payload["artifact_identity"] != expected_identity:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("structure stop screen artifact is invalid") from None
    return payload


_SETTLEMENT_TOP_LEVEL_KEYS = {
    "schema",
    "stage",
    "status",
    "trade_permission",
    "retrospective",
    "artifact_identity",
    "parent_screen_identity",
    "signal_date",
    "outcome_cutoff",
    "outcome_dates",
    "freeze_hash",
    "input_fingerprint",
    "risk_coverage_complete",
    "promotion_eligible",
    "candidates",
    "outcomes",
    "metrics",
}
_OUTCOME_KEYS = {
    "profile_id",
    "setup_type",
    "signal_date",
    "code",
    "status",
    "trigger_date",
    "net_return",
    "close_return",
    "mfe",
    "mae",
    "stop_first",
    "intraday_order_ambiguous",
    "structure_id",
    "executable_shares",
}


def _candidate_membership_key(
    value: StructureStopScreenCandidate,
) -> tuple[date, str, str]:
    return (
        value.candidate.hit.signal_date,
        normalize_code6(value.candidate.hit.code),
        value.candidate.profile.profile_id,
    )


def _outcome_membership_key(
    value: StructureStopOutcome,
) -> tuple[date, str, str]:
    return (
        value.signal_date,
        normalize_code6(value.code),
        value.profile_id,
    )


def _settlement_identity_payload(
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        key: payload[key]
        for key in (
            "schema",
            "stage",
            "parent_screen_identity",
            "signal_date",
            "outcome_cutoff",
            "outcome_dates",
            "freeze_hash",
            "input_fingerprint",
            "risk_coverage_complete",
            "candidates",
            "outcomes",
            "metrics",
        )
    }


def structure_stop_settlement_payload(
    value: StructureStopForwardSettlement,
) -> dict[str, object]:
    if not isinstance(value, StructureStopForwardSettlement):
        raise ValueError("structure stop settlement required")
    outcome_dates = tuple(value.outcome_dates)
    if (
        not _HEX_16.fullmatch(value.parent_screen_identity)
        or not _HEX_64.fullmatch(value.freeze_hash)
        or not value.input_fingerprint
        or not isinstance(value.risk_coverage_complete, bool)
        or len(outcome_dates) != 5
        or tuple(sorted(set(outcome_dates))) != outcome_dates
        or any(item <= value.signal_date for item in outcome_dates)
        or value.outcome_cutoff != outcome_dates[-1]
        or len(value.candidates) > 5
    ):
        raise ValueError("structure stop settlement lineage is invalid")
    try:
        for item in value.candidates:
            _validate_screen_candidate(item, signal_date=value.signal_date)
    except ValueError as exc:
        raise ValueError(
            "structure stop settlement candidate is invalid"
        ) from exc
    candidate_keys = tuple(
        _candidate_membership_key(item) for item in value.candidates
    )
    outcome_keys = tuple(
        _outcome_membership_key(item) for item in value.outcomes
    )
    if (
        len(set(candidate_keys)) != len(candidate_keys)
        or len(set(outcome_keys)) != len(outcome_keys)
        or set(candidate_keys) != set(outcome_keys)
    ):
        raise ValueError(
            "structure stop settlement candidate and outcome membership mismatch"
        )
    candidates_by_key = {
        _candidate_membership_key(item): item for item in value.candidates
    }
    for item in value.outcomes:
        candidate = candidates_by_key[_outcome_membership_key(item)].candidate
        outcome = item.outcome
        if (
            item.executable_shares != 0
            or item.signal_date != value.signal_date
            or normalize_code6(outcome.code)
            != normalize_code6(candidate.hit.code)
            or outcome.signal_date != value.signal_date
            or item.setup_type != candidate.hit.setup.setup_type.value
            or outcome.structure_id != candidate.plan.structure_id
            or (
                outcome.trigger_date is not None
                and outcome.trigger_date not in outcome_dates
            )
        ):
            raise ValueError("structure stop settlement outcome lineage mismatch")
    candidates = [
        _screen_candidate_payload(item)
        for item in sorted(
            value.candidates,
            key=lambda item: (
                item.profile_rank,
                normalize_code6(item.candidate.hit.code),
                item.candidate.profile.profile_id,
            ),
        )
    ]
    outcomes = [
        _outcome_payload(item)
        for item in sorted(value.outcomes, key=_outcome_membership_key)
    ]
    resolved = tuple(
        item for item in value.outcomes if item.outcome.net_return is not None
    )
    payload: dict[str, object] = {
        "schema": STRUCTURE_STOP_SCHEMA,
        "stage": "settlement",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": True,
        "parent_screen_identity": value.parent_screen_identity,
        "signal_date": value.signal_date.isoformat(),
        "outcome_cutoff": value.outcome_cutoff.isoformat(),
        "outcome_dates": [item.isoformat() for item in outcome_dates],
        "freeze_hash": value.freeze_hash,
        "input_fingerprint": value.input_fingerprint,
        "risk_coverage_complete": value.risk_coverage_complete,
        "promotion_eligible": False,
        "candidates": candidates,
        "outcomes": outcomes,
        "metrics": {
            "selected": len(candidates),
            "outcomes": len(outcomes),
            "resolved": len(resolved),
            "positive_net": sum(
                item.outcome.net_return is not None
                and item.outcome.net_return > 0
                for item in resolved
            ),
            "stop_first": sum(item.outcome.stop_first for item in resolved),
        },
    }
    payload["artifact_identity"] = _short_hash(
        _settlement_identity_payload(payload)
    )
    return payload


def write_structure_stop_forward_settlement(
    value: StructureStopForwardSettlement,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    payload = structure_stop_settlement_payload(value)
    stem = (
        f"settlement_{value.signal_date:%Y%m%d}_"
        f"cutoff-{value.outcome_cutoff:%Y%m%d}_"
        f"{payload['artifact_identity']}"
    )
    return _write_pair(
        output_dir,
        stem,
        payload,
        _render_markdown("买点结构止损前向结算", payload),
    )


def _parse_iso_date(raw: object) -> date:
    return date.fromisoformat(str(raw))


def load_structure_stop_forward_settlement(
    path: str | Path,
) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        candidates = payload["candidates"]
        outcomes = payload["outcomes"]
        outcome_dates = tuple(
            _parse_iso_date(item) for item in payload["outcome_dates"]
        )
        signal_date = _parse_iso_date(payload["signal_date"])
        if (
            set(payload) != _SETTLEMENT_TOP_LEVEL_KEYS
            or payload["schema"] != STRUCTURE_STOP_SCHEMA
            or payload["stage"] != "settlement"
            or payload["status"] != "CASE_ANALYSIS_ONLY"
            or payload["trade_permission"] != "NO-TRADE"
            or payload["retrospective"] is not True
            or payload["promotion_eligible"] is not False
            or not isinstance(payload["risk_coverage_complete"], bool)
            or not _HEX_16.fullmatch(payload["parent_screen_identity"])
            or not _HEX_64.fullmatch(payload["freeze_hash"])
            or not _HEX_16.fullmatch(payload["artifact_identity"])
            or not payload["input_fingerprint"]
            or len(outcome_dates) != 5
            or tuple(sorted(set(outcome_dates))) != outcome_dates
            or any(item <= signal_date for item in outcome_dates)
            or _parse_iso_date(payload["outcome_cutoff"])
            != outcome_dates[-1]
            or not isinstance(candidates, list)
            or not isinstance(outcomes, list)
            or len(candidates) > 5
        ):
            raise ValueError
        supported = {
            item.profile_id for item in build_structure_stop_profiles()
        }
        candidate_keys = []
        structures: dict[tuple[str, str, str], str] = {}
        for item in candidates:
            if (
                not isinstance(item, dict)
                or set(item) != _SCREEN_CANDIDATE_KEYS
                or item["signal_date"] != payload["signal_date"]
                or item["profile_id"] not in supported
                or int(item["profile_rank"]) <= 0
                or item["status"] != "CASE_ANALYSIS_ONLY"
                or item["trade_permission"] != "NO-TRADE"
                or item["executable_shares"] != 0
                or item["maximum_shares"] != 0
            ):
                raise ValueError
            key = (
                item["signal_date"],
                normalize_code6(str(item["code"])),
                item["profile_id"],
            )
            candidate_keys.append(key)
            structures[key] = str(item["structure_id"])
        outcome_keys = []
        for item in outcomes:
            if (
                not isinstance(item, dict)
                or set(item) != _OUTCOME_KEYS
                or item["signal_date"] != payload["signal_date"]
                or item["profile_id"] not in supported
                or item["executable_shares"] != 0
                or (
                    item["trigger_date"] is not None
                    and _parse_iso_date(item["trigger_date"])
                    not in outcome_dates
                )
            ):
                raise ValueError
            key = (
                item["signal_date"],
                normalize_code6(str(item["code"])),
                item["profile_id"],
            )
            if structures.get(key) != item["structure_id"]:
                raise ValueError
            outcome_keys.append(key)
        if (
            len(candidate_keys) != len(set(candidate_keys))
            or len(outcome_keys) != len(set(outcome_keys))
            or set(candidate_keys) != set(outcome_keys)
        ):
            raise ValueError
        resolved = [item for item in outcomes if item["net_return"] is not None]
        expected_metrics = {
            "selected": len(candidates),
            "outcomes": len(outcomes),
            "resolved": len(resolved),
            "positive_net": sum(
                Decimal(str(item["net_return"])) > 0 for item in resolved
            ),
            "stop_first": sum(bool(item["stop_first"]) for item in resolved),
        }
        if payload["metrics"] != expected_metrics:
            raise ValueError
        if payload["artifact_identity"] != _short_hash(
            _settlement_identity_payload(payload)
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("structure stop settlement artifact is invalid") from None
    return payload
