"""Deterministic artifacts for short-window buy-point case reviews."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Mapping

from .case_review import CaseCandidate, CaseOutcome, CaseReview, summarize_case_outcomes


CASE_REPORT_SCHEMA = "buy-point-case-review-v2"


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _mean_decimal(values: list[Decimal]) -> str | None:
    if not values:
        return None
    return str(sum(values, Decimal("0")) / Decimal(len(values)))


def case_identity(
    review: CaseReview,
    *,
    schema: str = CASE_REPORT_SCHEMA,
) -> str:
    identity = {
        "schema": schema,
        "signal_dates": [value.isoformat() for value in sorted(review.signal_dates)],
        "outcome_cutoff": review.outcome_cutoff.isoformat(),
        "rule_version": review.rule_version,
        "policy_hash": review.policy_hash,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _candidate_payload(value: CaseCandidate) -> dict[str, object]:
    return {
        "signal_date": value.signal_date.isoformat(),
        "code": value.code,
        "tier": value.tier,
        "setup_type": value.setup.setup_type.value,
        "setup_quality": str(value.setup.quality),
        "soft_reason": value.soft_reason,
        "executable_shares": 0,
        "plan": {
            "structure_id": value.plan.structure_id,
            "trigger_price": str(value.plan.trigger_price),
            "invalidation_price": str(value.plan.invalidation_price),
            "target_2r": str(value.plan.target_2r),
            "valid_through_trade_date": value.plan.valid_through_trade_date.isoformat(),
        },
    }


def _outcome_payload(value: CaseOutcome) -> dict[str, object]:
    return {
        "signal_date": value.signal_date.isoformat(),
        "code": value.code,
        "tier": value.tier,
        "status": value.status,
        "success": value.success,
        "trigger_date": None if value.trigger_date is None else value.trigger_date.isoformat(),
        "entry_price": _decimal(value.entry_price),
        "close_return": _decimal(value.close_return),
        "net_return": _decimal(value.net_return),
        "mfe": _decimal(value.mfe),
        "mae": _decimal(value.mae),
        "stop_first": value.stop_first,
        "intraday_order_ambiguous": value.intraday_order_ambiguous,
        "structure_id": value.structure_id,
    }


def case_payload(review: CaseReview) -> dict[str, object]:
    summary = summarize_case_outcomes(review.outcomes)
    traces = review.replay.traces
    rejection_counts = Counter(
        trace.first_rejection
        for trace in traces.values()
        if trace.first_rejection is not None
    )
    candidates = tuple(
        sorted(
            (*review.replay.strict_shadow, *review.replay.near_misses),
            key=lambda value: (value.signal_date, value.tier, value.code),
        )
    )
    outcomes = tuple(
        sorted(
            review.outcomes,
            key=lambda value: (value.signal_date, value.code, value.tier),
        )
    )
    winners = tuple(sorted(review.winners, key=lambda value: value.code))
    outcome_by_identity = {
        (
            value.code,
            value.signal_date,
            value.tier,
            value.structure_id,
        ): value
        for value in outcomes
    }
    episodes = []
    episode_outcomes: list[CaseOutcome] = []
    episode_outcome_by_id: dict[str, CaseOutcome] = {}
    for episode in sorted(review.episodes, key=lambda value: value.episode_id):
        representative = episode.representative
        outcome = outcome_by_identity.get(
            (
                representative.code,
                representative.signal_date,
                representative.tier,
                representative.plan.structure_id,
            )
        )
        if outcome is not None:
            episode_outcomes.append(outcome)
            episode_outcome_by_id[episode.episode_id] = outcome
        episodes.append(
            {
                "episode_id": episode.episode_id,
                "representative": {
                    "code": representative.code,
                    "signal_date": representative.signal_date.isoformat(),
                    "tier": representative.tier,
                    "structure_id": representative.plan.structure_id,
                },
                "member_signal_dates": [
                    value.isoformat() for value in episode.member_signal_dates
                ],
                "member_tiers": list(episode.member_tiers),
                "outcome": None if outcome is None else _outcome_payload(outcome),
            }
        )
    conditional = [
        {
            "episode_id": value.episode_id,
            "code": value.candidate.code,
            "signal_date": value.candidate.signal_date.isoformat(),
            "tier": "TWO_R_CONDITIONAL_SHADOW",
            "effective_resistance_r": str(value.effective_resistance_r),
            "executable_shares": 0,
        }
        for value in sorted(
            review.conditional_two_r_shadow,
            key=lambda item: item.episode_id,
        )
    ]
    episode_summary = summarize_case_outcomes(tuple(episode_outcomes))
    conditional_outcomes = tuple(
        episode_outcome_by_id[value.episode_id]
        for value in review.conditional_two_r_shadow
        if value.episode_id in episode_outcome_by_id
    )
    conditional_summary = summarize_case_outcomes(conditional_outcomes)
    return {
        "schema": CASE_REPORT_SCHEMA,
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "case_identity": case_identity(review),
        "signal_dates": [value.isoformat() for value in sorted(review.signal_dates)],
        "outcome_cutoff": review.outcome_cutoff.isoformat(),
        "rule_version": review.rule_version,
        "policy_hash": review.policy_hash,
        "risk_coverage_complete": review.risk_coverage_complete,
        "incomplete_dates": [
            value.isoformat() for value in review.replay.incomplete_dates
        ],
        "candidates": [_candidate_payload(value) for value in candidates],
        "outcomes": [_outcome_payload(value) for value in outcomes],
        "opportunity_episodes": episodes,
        "conditional_two_r_shadow": conditional,
        "winners": [
            {
                "code": value.code,
                "signal_date": value.signal_date.isoformat(),
                "maximum_gain": str(value.maximum_gain),
                "first_buyable_date": value.first_buyable_date.isoformat(),
                "captured_tiers": list(value.captured_tiers),
                "first_rejection": value.first_rejection,
            }
            for value in winners
        ],
        "metrics": {
            "outcome_total": summary.total,
            "outcome_pending": summary.pending,
            "outcome_resolved": summary.resolved,
            "outcome_successes": summary.successes,
            "outcome_failures": summary.failures,
            "raw_candidates": len(candidates),
            "opportunity_episodes": len(episodes),
            "raw_outcome_successes": summary.successes,
            "episode_outcome_resolved": episode_summary.resolved,
            "episode_outcome_successes": episode_summary.successes,
            "episode_triggered": sum(
                value.trigger_date is not None for value in episode_outcomes
            ),
            "episode_expired": sum(
                value.status == "EXPIRED" for value in episode_outcomes
            ),
            "episode_stop_first": sum(
                value.stop_first for value in episode_outcomes
            ),
            "episode_mean_net_return": _mean_decimal(
                [
                    value.net_return
                    for value in episode_outcomes
                    if value.net_return is not None
                ]
            ),
            "episode_mean_mfe": _mean_decimal(
                [value.mfe for value in episode_outcomes if value.mfe is not None]
            ),
            "episode_mean_mae": _mean_decimal(
                [value.mae for value in episode_outcomes if value.mae is not None]
            ),
            "conditional_episodes": len(review.conditional_two_r_shadow),
            "conditional_outcome_resolved": conditional_summary.resolved,
            "conditional_outcome_successes": conditional_summary.successes,
            "strict_candidates": len(review.replay.strict_shadow),
            "near_misses": len(review.replay.near_misses),
            "buyable_winners": len(winners),
            "captured_winners": sum(bool(value.captured_tiers) for value in winners),
            "recall_complete": not review.replay.incomplete_dates,
        },
        "rejection_counts": dict(sorted(rejection_counts.items())),
    }


def render_case_markdown(review: CaseReview) -> str:
    payload = case_payload(review)
    metrics = payload["metrics"]
    assert isinstance(metrics, Mapping)
    winners = payload["winners"]
    assert isinstance(winners, list)
    lines = [
        "# 短窗口买点案例复盘",
        "",
        "状态：`CASE_ANALYSIS_ONLY`",
        "交易权限：`NO-TRADE`",
        "",
        "本报告只能用于发现策略问题，不能用于规则晋级或交易。",
        "",
        "## 范围",
        "",
        f"- 信号日：{', '.join(payload['signal_dates'])}",
        f"- 结果截止：{payload['outcome_cutoff']}",
        f"- 规则版本：{payload['rule_version']}",
        f"- 风险覆盖完整：{'是' if payload['risk_coverage_complete'] else '否（NO-TRADE）'}",
        "",
        "## 原始信号（可能重复）",
        "",
        f"- 原始候选：{metrics['raw_candidates']}只",
        f"- 严格影子：{metrics['strict_candidates']}只",
        f"- 单软门近失：{metrics['near_misses']}只",
        f"- 已解决成功：{metrics['outcome_successes']}/{metrics['outcome_resolved']}",
        f"- 待观察：{metrics['outcome_pending']}/{metrics['outcome_total']}",
        (
            f"- 可买上涨股召回：{metrics['captured_winners']}/{metrics['buyable_winners']}"
            if metrics["recall_complete"]
            else "- 可买上涨股召回：不可计算（信号日数据不完整）"
        ),
        "",
        "## 去重交易机会",
        "",
        f"- 机会数：{metrics['opportunity_episodes']}个",
        (
            f"- 已解决成功：{metrics['episode_outcome_successes']}"
            f"/{metrics['episode_outcome_resolved']}"
        ),
        f"- 已触发：{metrics['episode_triggered']}个",
        f"- 未触发过期：{metrics['episode_expired']}个",
        f"- 止损优先：{metrics['episode_stop_first']}个",
        f"- 平均净收益：{metrics['episode_mean_net_return']}",
        f"- 平均 MFE：{metrics['episode_mean_mfe']}",
        f"- 平均 MAE：{metrics['episode_mean_mae']}",
        "",
        "## 1.5R—2R 条件影子组",
        "",
        f"- 影子机会：{metrics['conditional_episodes']}个",
        (
            f"- 已解决成功：{metrics['conditional_outcome_successes']}"
            f"/{metrics['conditional_outcome_resolved']}"
        ),
        "- 可执行仓位：0（研究专用）",
        "",
        "## 漏选可买上涨股",
        "",
    ]
    missed = [value for value in winners if not value["captured_tiers"]]
    if not metrics["recall_complete"]:
        lines.append("信号日数据不完整，不能进行漏选归因。")
    elif not missed:
        lines.append("无。")
    else:
        lines.extend(
            f"- {value['code']}：最大涨幅 {value['maximum_gain']}，首个淘汰原因 {value['first_rejection']}"
            for value in missed
        )
    lines.extend(
        (
            "",
            "## 解释边界",
            "",
            "短样本百分比仅作描述，不证明盈利能力，也不授权修改正式阈值。",
            "",
        )
    )
    return "\n".join(lines)


def _write_exclusive_or_verify(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise


def write_case_revision(
    review: CaseReview,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    signal_dates = tuple(sorted(review.signal_dates))
    stem = (
        f"{signal_dates[0]:%Y%m%d}_{signal_dates[-1]:%Y%m%d}_"
        f"cutoff-{review.outcome_cutoff:%Y%m%d}_{case_identity(review)}"
    )
    json_path = target / f"{stem}.json"
    markdown_path = target / f"{stem}.md"
    json_content = json.dumps(
        case_payload(review),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    _write_exclusive_or_verify(json_path, json_content)
    _write_exclusive_or_verify(markdown_path, render_case_markdown(review))
    return json_path, markdown_path
