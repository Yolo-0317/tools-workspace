from __future__ import annotations

from datetime import date, timedelta
import json

import pytest

from stock_ai.selection_validation import (
    BacktestMetrics,
    GENE_WATCH_CRITERIA,
    load_gene_watch_promotion,
    ValidationArtifact,
    ValidationError,
    choose_validation_profile,
    chronological_splits,
    evaluate_promotion,
    load_promoted_policy,
    wilson_lower_bound,
    write_validation_artifact,
)
from stock_ai.short_term_selection import BASELINE_POLICY, STRICT_B


def _metrics(
    trades: int,
    wins: int,
    *,
    expectancy: float = 0.1,
    breakout: int | None = None,
    pullback: int | None = None,
    max_drawdown_pct: float = 0.0,
    profit_loss_ratio: float = 0.0,
) -> BacktestMetrics:
    return BacktestMetrics(
        trade_count=trades,
        wins=wins,
        expectancy=expectancy,
        shape_counts={
            "BREAKOUT": breakout if breakout is not None else trades // 2,
            "PULLBACK": pullback if pullback is not None else trades - trades // 2,
        },
        max_drawdown_pct=max_drawdown_pct,
        profit_loss_ratio=profit_loss_ratio,
    )


def test_chronological_split_is_ordered_60_20_20() -> None:
    dates = tuple(date(2024, 1, 1) + timedelta(days=index) for index in range(600))

    split = chronological_splits(dates)

    assert tuple(map(len, (split.train, split.validation, split.test))) == (360, 120, 120)
    assert split.train[-1] < split.validation[0] < split.validation[-1] < split.test[0]


def test_each_chronological_segment_requires_120_sessions() -> None:
    dates = tuple(date(2024, 1, 1) + timedelta(days=index) for index in range(596))

    with pytest.raises(ValidationError, match="120"):
        chronological_splits(dates)


def test_duplicate_or_unordered_dates_are_rejected() -> None:
    dates = [date(2024, 1, 1) + timedelta(days=index) for index in range(600)]
    dates[-1] = dates[-2]

    with pytest.raises(ValidationError, match="strictly increasing"):
        chronological_splits(dates)


def test_profile_choice_uses_only_validation_metrics() -> None:
    chosen = choose_validation_profile(
        validation={
            "STRICT_A": _metrics(80, 44, breakout=40, pullback=40),
            "STRICT_B": _metrics(80, 48, breakout=40, pullback=40),
        }
    )

    assert chosen == "STRICT_B"


@pytest.mark.parametrize(
    "metrics",
    (
        _metrics(74, 50, breakout=37, pullback=37),
        _metrics(80, 50, breakout=24, pullback=56),
        _metrics(80, 50, expectancy=-0.001, breakout=40, pullback=40),
    ),
)
def test_ineligible_validation_profile_is_not_selected(metrics: BacktestMetrics) -> None:
    assert choose_validation_profile(validation={"STRICT_A": metrics}) is None


def test_profile_tie_prefers_more_trades_then_stable_name() -> None:
    chosen = choose_validation_profile(
        validation={
            "STRICT_C": _metrics(80, 40, breakout=40, pullback=40),
            "STRICT_B": _metrics(100, 50, breakout=50, pullback=50),
            "STRICT_A": _metrics(100, 50, breakout=50, pullback=50),
        }
    )

    assert chosen == "STRICT_A"


def test_wilson_lower_bound_matches_a_literal_reference() -> None:
    assert wilson_lower_bound(60, 100) == pytest.approx(0.5020007846)
    assert wilson_lower_bound(0, 0) == 0.0


def test_negative_expectancy_prevents_promotion_despite_high_win_rate() -> None:
    decision = evaluate_promotion(
        baseline=_metrics(200, 80, expectancy=-0.4, breakout=100, pullback=100),
        candidate=_metrics(120, 66, expectancy=-0.01, breakout=60, pullback=60),
    )

    assert decision.promoted is False
    assert "NEGATIVE_EXPECTANCY" in decision.reasons


def test_exactly_five_percentage_points_improvement_passes() -> None:
    decision = evaluate_promotion(
        baseline=_metrics(200, 80, breakout=100, pullback=100),
        candidate=_metrics(120, 54, breakout=60, pullback=60),
    )

    assert decision.promoted is True
    assert decision.reasons == ()


@pytest.mark.parametrize(
    ("candidate", "reason"),
    (
        (_metrics(99, 60, breakout=50, pullback=49), "INSUFFICIENT_TEST_TRADES"),
        (_metrics(120, 53, breakout=60, pullback=60), "WIN_RATE_IMPROVEMENT_TOO_SMALL"),
        (_metrics(120, 66, breakout=0, pullback=120), "SHAPE_SAMPLE_MISSING"),
    ),
)
def test_each_test_promotion_gate_fails_closed(
    candidate: BacktestMetrics, reason: str
) -> None:
    decision = evaluate_promotion(
        baseline=_metrics(200, 80, breakout=100, pullback=100),
        candidate=candidate,
    )

    assert decision.promoted is False
    assert reason in decision.reasons


def test_gene_watch_rejects_excessive_drawdown() -> None:
    decision = evaluate_promotion(
        baseline=_metrics(200, 80),
        candidate=_metrics(
            120,
            72,
            expectancy=0.8,
            max_drawdown_pct=15.1,
            profit_loss_ratio=1.8,
        ),
        criteria=GENE_WATCH_CRITERIA,
    )

    assert "MAX_DRAWDOWN_TOO_HIGH" in decision.reasons


def test_gene_watch_rejects_weak_profit_loss_ratio() -> None:
    decision = evaluate_promotion(
        baseline=_metrics(200, 80),
        candidate=_metrics(
            120,
            72,
            expectancy=0.8,
            max_drawdown_pct=10.0,
            profit_loss_ratio=1.49,
        ),
        criteria=GENE_WATCH_CRITERIA,
    )

    assert "PROFIT_LOSS_RATIO_TOO_LOW" in decision.reasons


def test_gene_watch_metrics_round_trip() -> None:
    metrics = _metrics(
        120,
        72,
        max_drawdown_pct=9.5,
        profit_loss_ratio=1.7,
    )

    restored = BacktestMetrics.from_dict(metrics.to_dict())

    assert restored.max_drawdown_pct == 9.5
    assert restored.profit_loss_ratio == 1.7


def _gene_artifact_payload(*, end: str = "2026-08-12") -> dict:
    return {
        "schema_version": "limit-up-gene-watch-validation-v1",
        "rule_version": "limit-up-gene-watch-1.0.0",
        "generated_at": "2026-08-13T01:00:00+00:00",
        "data_bounds": {"start": "2023-01-03", "end": end},
        "split_bounds": {
            "train": {"start": "2023-01-03", "end": "2024-08-01"},
            "validation": {"start": "2024-08-02", "end": "2025-06-01"},
            "test": {"start": "2025-06-02", "end": end},
        },
        "costs": {"commission_rate": 0.0008, "slippage_rate": 0.001},
        "hold_days": 5,
        "selected_profile": "limit_up_gene_watch",
        "metrics": {
            "baseline_test": _metrics(200, 80).to_dict(),
            "candidate_test": _metrics(
                120,
                72,
                expectancy=0.8,
                max_drawdown_pct=10,
                profit_loss_ratio=1.8,
            ).to_dict(),
        },
        "promoted": True,
        "reasons": [],
    }


def test_gene_watch_promotion_fails_closed_for_missing_or_stale_artifact(tmp_path) -> None:
    assert load_gene_watch_promotion(
        tmp_path / "missing.json", expected_data_end=date(2026, 8, 12)
    ) is False
    path = tmp_path / "gene.json"
    path.write_text(json.dumps(_gene_artifact_payload(end="2026-08-11")), encoding="utf-8")
    assert load_gene_watch_promotion(path, expected_data_end=date(2026, 8, 12)) is False


def test_gene_watch_promotion_accepts_current_passing_artifact(tmp_path) -> None:
    path = tmp_path / "gene.json"
    path.write_text(json.dumps(_gene_artifact_payload()), encoding="utf-8")

    assert load_gene_watch_promotion(path, expected_data_end=date(2026, 8, 12)) is True


def _artifact(*, promoted: bool = True, profile: str = "STRICT_B") -> ValidationArtifact:
    return ValidationArtifact(
        schema_version="short-term-selection-validation-v1",
        rule_version="short-term-selection-2.1.0",
        generated_at="2026-08-11T12:00:00+08:00",
        data_bounds={"start": "2024-01-02", "end": "2026-08-10"},
        split_bounds={
            "train": {"start": "2024-01-02", "end": "2025-03-01"},
            "validation": {"start": "2025-03-02", "end": "2025-10-01"},
            "test": {"start": "2025-10-02", "end": "2026-08-10"},
        },
        costs={"commission_rate": 0.001, "slippage_rate": 0.001},
        selected_profile=profile,
        metrics={
            "baseline_test": _metrics(200, 80).to_dict(),
            "candidate_test": _metrics(120, 60).to_dict(),
        },
        promoted=promoted,
        reasons=() if promoted else ("NEGATIVE_EXPECTANCY",),
    )


def test_valid_promoted_artifact_resolves_its_exact_policy(tmp_path) -> None:
    path = tmp_path / "validation.json"
    write_validation_artifact(path, _artifact())

    assert load_promoted_policy(path, expected_data_end=date(2026, 8, 10)) == STRICT_B


@pytest.mark.parametrize("payload", ({}, {"schema_version": "wrong"}, {"promoted": True}))
def test_malformed_artifact_falls_back_to_baseline(tmp_path, payload: dict) -> None:
    path = tmp_path / "validation.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_promoted_policy(path) == BASELINE_POLICY


def test_unknown_profile_failed_or_stale_artifact_falls_back(tmp_path) -> None:
    path = tmp_path / "validation.json"
    write_validation_artifact(path, _artifact(profile="STRICT_UNKNOWN"))
    assert load_promoted_policy(path) == BASELINE_POLICY

    write_validation_artifact(path, _artifact(promoted=False))
    assert load_promoted_policy(path) == BASELINE_POLICY

    write_validation_artifact(path, _artifact())
    assert load_promoted_policy(path, expected_data_end=date(2026, 8, 11)) == BASELINE_POLICY
