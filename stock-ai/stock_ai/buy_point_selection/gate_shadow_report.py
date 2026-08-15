"""Immutable artifacts for gate-shadow research and forward observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Sequence

from .case_review import CaseCandidate, CaseOutcome
from .gate_shadow_evaluation import (
    FrozenGateProfile,
    GateProfileFreeze,
    GateProfileMetrics,
    GateShadowOutcome,
    validate_gate_profile_freeze,
)
from .gate_shadow_research import (
    GateShadowCandidate,
    GateShadowProfile,
    GateShadowReplay,
)
from .threshold_shadow_evaluation import ExactRecallComparison


GATE_SHADOW_SCHEMA = "buy-point-gate-shadow-v1"


@dataclass(frozen=True)
class GateResearchReview:
    signal_dates: tuple[date, ...]
    outcome_cutoff: date
    v5_case_identity: str
    input_fingerprint: str
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    profiles: tuple[GateShadowProfile, ...]
    replay: GateShadowReplay
    outcomes: tuple[GateShadowOutcome, ...]
    profile_metrics: tuple[GateProfileMetrics, ...]
    formal_candidates: tuple[CaseCandidate, ...]
    formal_outcomes: tuple[CaseOutcome, ...]
    exact_recall: ExactRecallComparison
    risk_coverage_complete: bool


@dataclass(frozen=True)
class GateScreenCandidate:
    candidate: GateShadowCandidate
    profile_rank: int


@dataclass(frozen=True)
class GateForwardScreen:
    signal_date: date
    input_fingerprint: str
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    freeze_hash: str
    candidates: tuple[GateScreenCandidate, ...]
    risk_coverage_complete: bool


@dataclass(frozen=True)
class GateForwardSettlement:
    parent_screen_identity: str
    signal_date: date
    outcome_cutoff: date
    outcome_dates: tuple[date, ...]
    freeze_hash: str
    input_fingerprint: str
    candidates: tuple[GateScreenCandidate, ...]
    outcomes: tuple[GateShadowOutcome, ...]
    risk_coverage_complete: bool


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _profile_payload(value: GateShadowProfile) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "gate": value.gate,
        "failure_reason": value.failure_reason,
        "mode": value.mode,
        "freeze_eligible": value.freeze_eligible,
    }


def _candidate_payload(value: GateShadowCandidate) -> dict[str, object]:
    return {
        "signal_date": value.hit.signal_date.isoformat(),
        "code": value.hit.code,
        "profile_id": value.hit.profile.profile_id,
        "gate": value.hit.profile.gate,
        "failure_reason": value.hit.profile.failure_reason,
        "setup_type": value.hit.setup.setup_type.value,
        "setup_quality": str(value.hit.setup.quality),
        "structure_start": value.hit.setup.structure_start.isoformat(),
        "structure_high": str(value.hit.setup.structure_high),
        "structure_low": str(value.hit.setup.structure_low),
        "setup_reasons": list(value.hit.setup.reasons),
        "setup_metrics": {
            key: str(item) for key, item in sorted(value.hit.setup.metrics.items())
        },
        "market_status": value.hit.market_status,
        "sector_code": value.hit.sector_code,
        "structure_id": value.plan.structure_id,
        "trigger_price": str(value.plan.trigger_price),
        "invalidation_price": str(value.plan.invalidation_price),
        "target_2r": str(value.plan.target_2r),
        "signal_close": str(value.plan.signal_close),
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


def _outcome_payload(value: GateShadowOutcome) -> dict[str, object]:
    outcome = value.outcome
    return {
        "profile_id": value.profile_id,
        "signal_date": value.signal_date.isoformat(),
        "code": value.code,
        "status": outcome.status,
        "trigger_date": (
            None if outcome.trigger_date is None else outcome.trigger_date.isoformat()
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


def _formal_candidate_payload(value: CaseCandidate) -> dict[str, object]:
    return {
        "signal_date": value.signal_date.isoformat(),
        "code": value.code,
        "tier": value.tier,
        "setup_type": value.setup.setup_type.value,
        "setup_quality": str(value.setup.quality),
        "structure_id": value.plan.structure_id,
        "trigger_price": str(value.plan.trigger_price),
        "invalidation_price": str(value.plan.invalidation_price),
        "target_2r": str(value.plan.target_2r),
        "executable_shares": 0,
    }


def _formal_outcome_payload(value: CaseOutcome) -> dict[str, object]:
    return {
        "signal_date": value.signal_date.isoformat(),
        "code": value.code,
        "tier": value.tier,
        "status": value.status,
        "trigger_date": (
            None if value.trigger_date is None else value.trigger_date.isoformat()
        ),
        "net_return": _decimal(value.net_return),
        "close_return": _decimal(value.close_return),
        "mfe": _decimal(value.mfe),
        "mae": _decimal(value.mae),
        "stop_first": value.stop_first,
        "intraday_order_ambiguous": value.intraday_order_ambiguous,
        "structure_id": value.structure_id,
        "executable_shares": 0,
    }


def _metric_payload(value: GateProfileMetrics) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
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


def _research_identity(review: GateResearchReview) -> str:
    identity = {
        "schema": GATE_SHADOW_SCHEMA,
        "stage": "research",
        "signal_dates": [value.isoformat() for value in sorted(review.signal_dates)],
        "outcome_cutoff": review.outcome_cutoff.isoformat(),
        "v5_case_identity": review.v5_case_identity,
        "input_fingerprint": review.input_fingerprint,
        "formal_rule_version": review.formal_rule_version,
        "formal_policy_hash": review.formal_policy_hash,
        "profile_matrix_hash": review.profile_matrix_hash,
        "evaluator_version": "case-evaluator-v1",
        "cost_version": "execution-costs-default-v1",
    }
    return _short_hash(identity)


def _short_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _exact_recall_payload(value: ExactRecallComparison) -> dict[str, int]:
    return {
        "actionable_winner_pairs": value.actionable_winner_pairs,
        "formal_captured_pairs": value.formal_captured_pairs,
        "shadow_captured_pairs": value.shadow_captured_pairs,
        "incremental_captured_pairs": value.incremental_captured_pairs,
        "selected_non_winner_pairs": value.selected_non_winner_pairs,
    }


def gate_research_payload(review: GateResearchReview) -> dict[str, object]:
    zero_share_values = [
        *(value.executable_shares for value in review.replay.raw_hits),
        *(value.executable_shares for value in review.replay.candidates),
        *(value.executable_shares for value in review.outcomes),
    ]
    if any(value != 0 for value in zero_share_values):
        raise ValueError("gate shadow artifacts must be zero-share")
    raw_hits = sorted(
        review.replay.raw_hits,
        key=lambda value: (value.signal_date, value.code, value.profile.profile_id),
    )
    candidates = sorted(
        review.replay.candidates,
        key=lambda value: (
            value.hit.signal_date,
            value.hit.code,
            value.hit.profile.profile_id,
        ),
    )
    outcomes = sorted(
        review.outcomes,
        key=lambda value: (value.signal_date, value.code, value.profile_id),
    )
    return {
        "schema": GATE_SHADOW_SCHEMA,
        "stage": "research",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": True,
        "artifact_identity": _research_identity(review),
        "signal_dates": [value.isoformat() for value in sorted(review.signal_dates)],
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
        "raw_hits": [
            {
                "signal_date": value.signal_date.isoformat(),
                "code": value.code,
                "profile_id": value.profile.profile_id,
                "setup_type": value.setup.setup_type.value,
                "setup_quality": str(value.setup.quality),
                "market_status": value.market_status,
                "sector_code": value.sector_code,
                "executable_shares": 0,
            }
            for value in raw_hits
        ],
        "candidates": [_candidate_payload(value) for value in candidates],
        "rejections": [
            {
                "signal_date": value.signal_date.isoformat(),
                "code": value.code,
                "profile_id": value.profile_id,
                "stage": value.stage,
                "reasons": list(value.reasons),
            }
            for value in review.replay.rejections
        ],
        "outcomes": [_outcome_payload(value) for value in outcomes],
        "profile_metrics": [
            _metric_payload(value)
            for value in sorted(review.profile_metrics, key=lambda item: item.profile_id)
        ],
        "formal_candidates": [
            _formal_candidate_payload(value)
            for value in sorted(
                review.formal_candidates,
                key=lambda item: (item.signal_date, item.code, item.tier),
            )
        ],
        "formal_outcomes": [
            _formal_outcome_payload(value)
            for value in sorted(
                review.formal_outcomes,
                key=lambda item: (item.signal_date, item.code, item.tier),
            )
        ],
        "exact_recall": _exact_recall_payload(review.exact_recall),
        "metrics": {
            "raw_hits": len(raw_hits),
            "candidates": len(candidates),
            "outcomes": len(outcomes),
            "formal_candidates": len(review.formal_candidates),
            "formal_outcomes": len(review.formal_outcomes),
        },
    }


def _freeze_payload(value: GateProfileFreeze) -> dict[str, object]:
    validate_gate_profile_freeze(value)
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
                "training_metrics": _metric_payload(item.training_metrics),
                "executable_shares": 0,
            }
            for item in value.profiles
        ],
        "empty": value.empty,
        "risk_coverage_complete": value.risk_coverage_complete,
        "promotion_eligible": value.promotion_eligible,
        "freeze_hash": value.freeze_hash,
    }


def gate_screen_identity(screen: GateForwardScreen) -> str:
    return _short_hash(
        {
            "schema": GATE_SHADOW_SCHEMA,
            "stage": "screen",
            "signal_date": screen.signal_date.isoformat(),
            "input_fingerprint": screen.input_fingerprint,
            "formal_rule_version": screen.formal_rule_version,
            "formal_policy_hash": screen.formal_policy_hash,
            "profile_matrix_hash": screen.profile_matrix_hash,
            "freeze_hash": screen.freeze_hash,
            "planner_version": "price-plan-v1",
        }
    )


def _validate_screen(screen: GateForwardScreen) -> None:
    if len(screen.candidates) > 5:
        raise ValueError("screen may contain at most five candidates")
    keys: set[tuple[date, str]] = set()
    for selected in screen.candidates:
        candidate = selected.candidate
        if (
            candidate.hit.profile.gate != "SECTOR"
            or not candidate.hit.profile.freeze_eligible
        ):
            raise ValueError("forward screens allow only frozen sector profiles")
        if candidate.hit.signal_date != screen.signal_date:
            raise ValueError("screen candidate signal date mismatch")
        if (
            selected.profile_rank < 1
            or candidate.executable_shares != 0
            or candidate.hit.executable_shares != 0
        ):
            raise ValueError("screen candidates must be ranked and zero-share")
        key = (candidate.hit.signal_date, candidate.hit.code)
        if key in keys:
            raise ValueError("duplicate screen candidate")
        keys.add(key)


def gate_screen_payload(screen: GateForwardScreen) -> dict[str, object]:
    _validate_screen(screen)
    return {
        "schema": GATE_SHADOW_SCHEMA,
        "stage": "screen",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": False,
        "artifact_identity": gate_screen_identity(screen),
        "signal_date": screen.signal_date.isoformat(),
        "input_fingerprint": screen.input_fingerprint,
        "formal_rule_version": screen.formal_rule_version,
        "formal_policy_hash": screen.formal_policy_hash,
        "profile_matrix_hash": screen.profile_matrix_hash,
        "freeze_hash": screen.freeze_hash,
        "planner_version": "price-plan-v1",
        "risk_coverage_complete": screen.risk_coverage_complete,
        "promotion_eligible": False,
        "candidates": [
            {**_candidate_payload(value.candidate), "profile_rank": value.profile_rank}
            for value in screen.candidates
        ],
        "metrics": {"selected_candidates": len(screen.candidates)},
    }


def _settlement_identity(value: GateForwardSettlement) -> str:
    return _short_hash(
        {
            "schema": GATE_SHADOW_SCHEMA,
            "stage": "settlement",
            "parent_screen_identity": value.parent_screen_identity,
            "signal_date": value.signal_date.isoformat(),
            "outcome_cutoff": value.outcome_cutoff.isoformat(),
            "outcome_dates": [item.isoformat() for item in value.outcome_dates],
            "freeze_hash": value.freeze_hash,
            "input_fingerprint": value.input_fingerprint,
        }
    )


def gate_settlement_payload(value: GateForwardSettlement) -> dict[str, object]:
    screen = GateForwardScreen(
        value.signal_date,
        value.input_fingerprint,
        "settlement",
        "settlement",
        "settlement",
        value.freeze_hash,
        value.candidates,
        value.risk_coverage_complete,
    )
    _validate_screen(screen)
    if (
        len(value.outcome_dates) != 5
        or tuple(sorted(set(value.outcome_dates))) != value.outcome_dates
        or any(item <= value.signal_date for item in value.outcome_dates)
        or value.outcome_dates[-1] > value.outcome_cutoff
    ):
        raise ValueError("settlement requires exactly five ordered future sessions")
    candidate_keys = {
        (
            item.candidate.hit.signal_date,
            item.candidate.hit.code,
            item.candidate.hit.profile.profile_id,
        )
        for item in value.candidates
    }
    outcome_keys = {
        (item.signal_date, item.code, item.profile_id) for item in value.outcomes
    }
    if candidate_keys != outcome_keys:
        raise ValueError("settlement membership differs from parent screen")
    if any(item.executable_shares != 0 for item in value.outcomes):
        raise ValueError("settlement outcomes must be zero-share")
    return {
        "schema": GATE_SHADOW_SCHEMA,
        "stage": "settlement",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "retrospective": False,
        "artifact_identity": _settlement_identity(value),
        "parent_screen_identity": value.parent_screen_identity,
        "signal_date": value.signal_date.isoformat(),
        "outcome_cutoff": value.outcome_cutoff.isoformat(),
        "outcome_dates": [item.isoformat() for item in value.outcome_dates],
        "freeze_hash": value.freeze_hash,
        "input_fingerprint": value.input_fingerprint,
        "risk_coverage_complete": value.risk_coverage_complete,
        "promotion_eligible": False,
        "candidates": [
            {**_candidate_payload(item.candidate), "profile_rank": item.profile_rank}
            for item in value.candidates
        ],
        "outcomes": [_outcome_payload(item) for item in value.outcomes],
        "metrics": {
            "selected_candidates": len(value.candidates),
            "outcomes": len(value.outcomes),
        },
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
    title: str,
) -> tuple[Path, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / f"{stem}.json"
    markdown_path = target / f"{stem}.md"
    json_content = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n"
    _write_exclusive_or_verify(json_path, json_content)
    _write_exclusive_or_verify(markdown_path, _render_markdown(title, payload))
    return json_path, markdown_path


def write_gate_research_revision(
    review: GateResearchReview, output_dir: str | Path
) -> tuple[Path, Path]:
    dates = tuple(sorted(review.signal_dates))
    identity = _research_identity(review)
    stem = (
        f"research_{dates[0]:%Y%m%d}_{dates[-1]:%Y%m%d}_"
        f"cutoff-{review.outcome_cutoff:%Y%m%d}_{identity}"
    )
    return _write_pair(output_dir, stem, gate_research_payload(review), "买点门禁影子研究")


def write_gate_profile_freeze(
    value: GateProfileFreeze, output_dir: str | Path
) -> tuple[Path, Path]:
    return _write_pair(
        output_dir,
        f"freeze-{value.freeze_hash}",
        _freeze_payload(value),
        "买点门禁影子冻结配置",
    )


def write_gate_forward_screen(
    value: GateForwardScreen, output_dir: str | Path
) -> tuple[Path, Path]:
    identity = gate_screen_identity(value)
    return _write_pair(
        output_dir,
        f"screen_{value.signal_date:%Y%m%d}_{identity}",
        gate_screen_payload(value),
        "买点门禁影子前向筛选",
    )


def write_gate_forward_settlement(
    value: GateForwardSettlement, output_dir: str | Path
) -> tuple[Path, Path]:
    identity = _settlement_identity(value)
    return _write_pair(
        output_dir,
        f"settlement_{value.signal_date:%Y%m%d}_{identity}",
        gate_settlement_payload(value),
        "买点门禁影子前向结算",
    )


def _metric_from_payload(value: dict[str, object]) -> GateProfileMetrics:
    def decimal(key: str) -> Decimal | None:
        raw = value.get(key)
        return None if raw is None else Decimal(str(raw))

    return GateProfileMetrics(
        str(value["profile_id"]),
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


def load_gate_profile_freeze(path: str | Path) -> GateProfileFreeze:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != GATE_SHADOW_SCHEMA or payload.get("stage") != "freeze":
        raise ValueError("expected gate profile freeze artifact")
    identities = tuple(str(item) for item in payload["training_identities"])
    if len(identities) != 3:
        raise ValueError("freeze requires three training identities")
    profiles = tuple(
        FrozenGateProfile(
            str(item["profile_id"]),
            int(item["rank"]),
            _metric_from_payload(item["training_metrics"]),
        )
        for item in payload["profiles"]
    )
    value = GateProfileFreeze(
        str(payload["schema"]),
        (identities[0], identities[1], identities[2]),
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
    validate_gate_profile_freeze(value)
    return value


def load_gate_forward_screen(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema") != GATE_SHADOW_SCHEMA
        or payload.get("stage") != "screen"
        or payload.get("status") != "CASE_ANALYSIS_ONLY"
        or payload.get("trade_permission") != "NO-TRADE"
    ):
        raise ValueError("expected safely labeled gate forward screen")
    forbidden = {"outcomes", "net_return", "mfe", "mae"}
    encoded_keys = set()
    stack: list[object] = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            encoded_keys.update(item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    if forbidden & encoded_keys:
        raise ValueError("screen artifact contains outcome data")
    return payload


def load_gate_research_artifact(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema") != GATE_SHADOW_SCHEMA
        or payload.get("stage") != "research"
        or payload.get("status") != "CASE_ANALYSIS_ONLY"
        or payload.get("trade_permission") != "NO-TRADE"
        or payload.get("retrospective") is not True
        or payload.get("promotion_eligible") is not False
    ):
        raise ValueError("expected safely labeled gate research artifact")
    return payload
