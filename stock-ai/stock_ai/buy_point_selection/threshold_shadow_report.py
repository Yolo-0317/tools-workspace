"""Immutable artifacts for threshold-shadow case research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from .case_review import CaseCandidate, CaseOutcome
from .threshold_shadow_evaluation import (
    ExactRecallComparison,
    FrozenThresholdProfile,
    ThresholdProfileFreeze,
    ThresholdProfileMetrics,
    ThresholdShadowOutcome,
    validate_threshold_freeze,
)
from .threshold_shadow_research import (
    ThresholdProfile,
    ThresholdShadowCandidate,
    ThresholdShadowReplay,
    ThresholdShadowSetup,
)


THRESHOLD_SHADOW_SCHEMA = "buy-point-threshold-shadow-v1"


@dataclass(frozen=True)
class ThresholdWindowReview:
    stage: str
    signal_dates: tuple[date, ...]
    outcome_cutoff: date
    v5_case_identity: str
    input_fingerprint: str
    formal_rule_version: str
    formal_policy_hash: str
    profile_matrix_hash: str
    freeze_hash: str | None
    profiles: tuple[ThresholdProfile, ...]
    replay: ThresholdShadowReplay
    shadow_outcomes: tuple[ThresholdShadowOutcome, ...]
    profile_metrics: tuple[ThresholdProfileMetrics, ...]
    formal_candidates: tuple[CaseCandidate, ...]
    formal_outcomes: tuple[CaseOutcome, ...]
    selected_candidates: tuple[ThresholdShadowCandidate, ...]
    selected_outcomes: tuple[ThresholdShadowOutcome, ...]
    exact_recall: ExactRecallComparison
    risk_coverage_complete: bool
    test_consumed: bool


def _profile_payload(value: ThresholdProfile) -> dict[str, object]:
    return {
        "profile_id": value.profile_id,
        "setup_type": value.setup_type.value,
        "policy_field": value.policy_field,
        "direction": value.direction,
        "relaxation_rate": str(value.relaxation_rate),
        "formal_value": str(value.formal_value),
        "shadow_value": str(value.shadow_value),
        "failure_reason": value.failure_reason,
        "metric_name": value.metric_name,
    }


def _setup_payload(value: ThresholdShadowSetup) -> dict[str, object]:
    return {
        "signal_date": value.signal_date.isoformat(),
        "code": value.code,
        "profile_id": value.profile.profile_id,
        "setup_type": value.setup.setup_type.value,
        "setup_quality": str(value.setup.quality),
        "actual_deviation": str(value.actual_deviation),
        "executable_shares": 0,
    }


def _candidate_payload(value: ThresholdShadowCandidate) -> dict[str, object]:
    return {
        **_setup_payload(value.shadow_setup),
        "structure_id": value.plan.structure_id,
        "trigger_price": str(value.plan.trigger_price),
        "invalidation_price": str(value.plan.invalidation_price),
        "target_2r": str(value.plan.target_2r),
        "average_amount5_qian": str(value.average_amount5_qian),
        "two_r_space_buffer": str(value.two_r_space_buffer),
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
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
        "net_return": None if value.net_return is None else str(value.net_return),
        "close_return": None if value.close_return is None else str(value.close_return),
        "mfe": None if value.mfe is None else str(value.mfe),
        "mae": None if value.mae is None else str(value.mae),
        "stop_first": value.stop_first,
        "intraday_order_ambiguous": value.intraday_order_ambiguous,
        "structure_id": value.structure_id,
        "executable_shares": 0,
    }


def _metric_payload(value: ThresholdProfileMetrics) -> dict[str, object]:
    def decimal(item: object) -> str | None:
        return None if item is None else str(item)

    return {
        "profile_id": value.profile_id,
        "candidate_count": value.candidate_count,
        "triggered": value.triggered,
        "resolved": value.resolved,
        "positive_net": value.positive_net,
        "stop_first": value.stop_first,
        "mean_net_return": decimal(value.mean_net_return),
        "median_net_return": decimal(value.median_net_return),
        "positive_net_rate": decimal(value.positive_net_rate),
        "stop_first_rate": decimal(value.stop_first_rate),
        "mean_mfe": decimal(value.mean_mfe),
        "mean_mae": decimal(value.mean_mae),
        "qualifies": value.qualifies,
        "qualification_reasons": list(value.qualification_reasons),
    }


def _outcome_payload(value: ThresholdShadowOutcome) -> dict[str, object]:
    outcome = value.outcome
    return {
        "profile_id": value.profile_id,
        "signal_date": value.signal_date.isoformat(),
        "code": value.code,
        "status": outcome.status,
        "trigger_date": (
            None if outcome.trigger_date is None else outcome.trigger_date.isoformat()
        ),
        "net_return": None if outcome.net_return is None else str(outcome.net_return),
        "close_return": None if outcome.close_return is None else str(outcome.close_return),
        "mfe": None if outcome.mfe is None else str(outcome.mfe),
        "mae": None if outcome.mae is None else str(outcome.mae),
        "stop_first": outcome.stop_first,
        "intraday_order_ambiguous": outcome.intraday_order_ambiguous,
        "structure_id": outcome.structure_id,
        "executable_shares": 0,
    }


def threshold_shadow_identity(review: ThresholdWindowReview) -> str:
    identity = {
        "schema": THRESHOLD_SHADOW_SCHEMA,
        "stage": review.stage,
        "signal_dates": [value.isoformat() for value in sorted(review.signal_dates)],
        "outcome_cutoff": review.outcome_cutoff.isoformat(),
        "v5_case_identity": review.v5_case_identity,
        "input_fingerprint": review.input_fingerprint,
        "formal_rule_version": review.formal_rule_version,
        "formal_policy_hash": review.formal_policy_hash,
        "profile_matrix_hash": review.profile_matrix_hash,
        "freeze_hash": review.freeze_hash,
        "evaluator_version": "case-evaluator-v1",
        "cost_version": "execution-costs-default-v1",
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def threshold_shadow_payload(review: ThresholdWindowReview) -> dict[str, object]:
    if review.stage not in {"research", "test"}:
        raise ValueError("unsupported threshold shadow stage")
    if review.stage == "test" and (
        review.freeze_hash is None or not review.test_consumed
    ):
        raise ValueError("test stage requires consumed freeze")
    share_values = [
        *(value.executable_shares for value in review.replay.raw_setups),
        *(value.executable_shares for value in review.replay.candidates),
        *(value.executable_shares for value in review.shadow_outcomes),
        *(value.executable_shares for value in review.selected_candidates),
        *(value.executable_shares for value in review.selected_outcomes),
    ]
    if any(value != 0 for value in share_values):
        raise ValueError("threshold shadow artifacts must be zero-share")
    profiles = tuple(sorted(review.profiles, key=lambda value: value.profile_id))
    raw_setups = tuple(
        sorted(
            review.replay.raw_setups,
            key=lambda value: (
                value.signal_date,
                value.code,
                value.profile.profile_id,
            ),
        )
    )
    candidates = tuple(
        sorted(
            review.replay.candidates,
            key=lambda value: (
                value.signal_date,
                value.code,
                value.profile_id,
            ),
        )
    )
    return {
        "schema": THRESHOLD_SHADOW_SCHEMA,
        "stage": review.stage,
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "artifact_identity": threshold_shadow_identity(review),
        "signal_dates": [value.isoformat() for value in sorted(review.signal_dates)],
        "outcome_cutoff": review.outcome_cutoff.isoformat(),
        "v5_case_identity": review.v5_case_identity,
        "input_fingerprint": review.input_fingerprint,
        "formal_rule_version": review.formal_rule_version,
        "formal_policy_hash": review.formal_policy_hash,
        "profile_matrix_hash": review.profile_matrix_hash,
        "freeze_hash": review.freeze_hash,
        "risk_coverage_complete": review.risk_coverage_complete,
        "promotion_eligible": False,
        "test_consumed": review.test_consumed,
        "profiles": [_profile_payload(value) for value in profiles],
        "raw_setups": [_setup_payload(value) for value in raw_setups],
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
        "shadow_outcomes": [
            _outcome_payload(value)
            for value in sorted(
                review.shadow_outcomes,
                key=lambda item: (item.signal_date, item.code, item.profile_id),
            )
        ],
        "selected_candidates": [
            _candidate_payload(value)
            for value in review.selected_candidates
        ],
        "selected_outcomes": [
            _outcome_payload(value)
            for value in review.selected_outcomes
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
        "profile_metrics": [
            _metric_payload(value)
            for value in sorted(
                review.profile_metrics, key=lambda item: item.profile_id
            )
        ],
        "metrics": {
            "raw_setups": len(raw_setups),
            "candidates": len(candidates),
            "selected_candidates": len(review.selected_candidates),
            "shadow_outcomes": len(review.shadow_outcomes),
            "formal_candidates": len(review.formal_candidates),
            "formal_outcomes": len(review.formal_outcomes),
        },
        "exact_recall": {
            "actionable_winner_pairs": review.exact_recall.actionable_winner_pairs,
            "formal_captured_pairs": review.exact_recall.formal_captured_pairs,
            "shadow_captured_pairs": review.exact_recall.shadow_captured_pairs,
            "incremental_captured_pairs": review.exact_recall.incremental_captured_pairs,
            "selected_non_winner_pairs": review.exact_recall.selected_non_winner_pairs,
        },
    }


def render_threshold_shadow_markdown(review: ThresholdWindowReview) -> str:
    payload = threshold_shadow_payload(review)
    metrics = payload["metrics"]
    recall = payload["exact_recall"]
    assert isinstance(metrics, dict)
    assert isinstance(recall, dict)
    return "\n".join(
        (
            "# 买点阈值影子研究",
            "",
            f"阶段：`{review.stage}`",
            "状态：`CASE_ANALYSIS_ONLY`",
            "交易权限：`NO-TRADE`",
            "",
            "本报告仅用于案例研究，不生成交易建议；可执行仓位为 0。",
            "",
            "## 范围",
            "",
            f"- 信号日：{', '.join(payload['signal_dates'])}",
            f"- 结果截止：{payload['outcome_cutoff']}",
            f"- profile 数：{len(payload['profiles'])}",
            f"- 原始影子形态：{metrics['raw_setups']}",
            f"- 下游门禁后候选：{metrics['candidates']}",
            f"- 最终选择：{metrics['selected_candidates']}",
            "",
            "## 精确日期召回",
            "",
            "股票-日期样本存在重叠，不能视为相互独立。",
            f"- 可买上涨样本：{recall['actionable_winner_pairs']}",
            f"- 正式捕获：{recall['formal_captured_pairs']}",
            f"- 影子捕获：{recall['shadow_captured_pairs']}",
            f"- 增量捕获：{recall['incremental_captured_pairs']}",
            "",
            "## 解释边界",
            "",
            "短窗口通过只能进入扩大历史验证，不能晋级正式规则。",
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


def write_threshold_shadow_revision(
    review: ThresholdWindowReview,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    dates = tuple(sorted(review.signal_dates))
    stem = (
        f"{review.stage}_{dates[0]:%Y%m%d}_{dates[-1]:%Y%m%d}_"
        f"cutoff-{review.outcome_cutoff:%Y%m%d}_{threshold_shadow_identity(review)}"
    )
    json_path = target / f"{stem}.json"
    markdown_path = target / f"{stem}.md"
    json_content = json.dumps(
        threshold_shadow_payload(review),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    _write_exclusive_or_verify(json_path, json_content)
    _write_exclusive_or_verify(
        markdown_path,
        render_threshold_shadow_markdown(review),
    )
    return json_path, markdown_path


def freeze_payload(value: ThresholdProfileFreeze) -> dict[str, object]:
    validate_threshold_freeze(value)
    return {
        "schema": value.schema,
        "stage": "freeze",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
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


def _render_freeze_markdown(value: ThresholdProfileFreeze) -> str:
    lines = [
        "# 买点阈值影子冻结配置",
        "",
        "状态：`CASE_ANALYSIS_ONLY`",
        "交易权限：`NO-TRADE`",
        "",
        "本配置仅用于案例研究，不生成交易建议；可执行仓位为 0。",
        "",
        f"- 冻结哈希：`{value.freeze_hash}`",
        f"- 合格 profile：{len(value.profiles)}个",
        f"- 空冻结集：{'是' if value.empty else '否'}",
        f"- 风险覆盖完整：{'是' if value.risk_coverage_complete else '否'}",
        "- 正式晋级：禁止",
        "",
    ]
    lines.extend(
        f"- 第 {item.rank} 名：{item.profile_id}"
        for item in value.profiles
    )
    return "\n".join(lines)


def write_threshold_freeze(
    value: ThresholdProfileFreeze,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / f"freeze-{value.freeze_hash}.json"
    markdown_path = target / f"freeze-{value.freeze_hash}.md"
    json_content = json.dumps(
        freeze_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    _write_exclusive_or_verify(json_path, json_content)
    _write_exclusive_or_verify(markdown_path, _render_freeze_markdown(value))
    return json_path, markdown_path


def _metric_from_payload(value: dict[str, object]) -> ThresholdProfileMetrics:
    def decimal(key: str) -> Decimal | None:
        raw = value.get(key)
        return None if raw is None else Decimal(str(raw))

    return ThresholdProfileMetrics(
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


def load_threshold_freeze_artifact(path: str | Path) -> ThresholdProfileFreeze:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != THRESHOLD_SHADOW_SCHEMA or payload.get("stage") != "freeze":
        raise ValueError("expected threshold freeze artifact")
    profiles = tuple(
        FrozenThresholdProfile(
            str(item["profile_id"]),
            int(item["rank"]),
            _metric_from_payload(item["training_metrics"]),
        )
        for item in payload["profiles"]
    )
    identities = tuple(str(item) for item in payload["training_identities"])
    if len(identities) != 2:
        raise ValueError("freeze requires two training identities")
    value = ThresholdProfileFreeze(
        str(payload["schema"]),
        (identities[0], identities[1]),
        str(payload["formal_rule_version"]),
        str(payload["formal_policy_hash"]),
        str(payload["profile_matrix_hash"]),
        profiles,
        bool(payload["empty"]),
        bool(payload["risk_coverage_complete"]),
        bool(payload["promotion_eligible"]),
        str(payload["freeze_hash"]),
    )
    validate_threshold_freeze(value)
    return value


def _load_stage_artifact(path: str | Path, expected_stage: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != THRESHOLD_SHADOW_SCHEMA:
        raise ValueError("expected threshold shadow v1 artifact")
    if payload.get("stage") != expected_stage:
        raise ValueError(f"expected {expected_stage} artifact")
    if payload.get("status") != "CASE_ANALYSIS_ONLY" or payload.get("trade_permission") != "NO-TRADE":
        raise ValueError("threshold shadow artifact is not safely labeled")
    return payload


def load_threshold_research_artifact(path: str | Path) -> dict[str, object]:
    return _load_stage_artifact(path, "research")


def load_threshold_test_artifact(path: str | Path) -> dict[str, object]:
    payload = _load_stage_artifact(path, "test")
    if not payload.get("test_consumed") or not payload.get("freeze_hash"):
        raise ValueError("test artifact has no consumed freeze")
    return payload
