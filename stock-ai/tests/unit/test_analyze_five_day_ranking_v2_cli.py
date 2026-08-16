from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v2 import (
    FiveDayRankingV2ValidationReview,
    build_five_day_v2_policies,
    five_day_v2_policy_hash,
    five_day_v2_policy_set_hash,
    v2_validation_trial_identity,
)
from stock_ai.buy_point_selection.five_day_ranking_v2_report import (
    FiveDayRankingV2TrainArtifact,
    write_five_day_ranking_v2_validation,
)

from stock_ai.buy_point_selection.five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    SIZING_VERSION,
    build_five_day_return_profiles,
    five_day_profile_hash,
)
from stock_ai.buy_point_selection.five_day_return_report import (
    _recompute_review,
    write_five_day_research,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayResearchReview,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayPortfolioMetrics,
    FiveDayRanking,
    FiveDaySegmentMetrics,
    FiveDaySelectedSegment,
    FiveDaySelection,
)
from stock_ai.buy_point_selection.models import SelectionPolicy
from stock_ai.buy_point_selection.validation import (
    ChronologicalSplit,
    policy_hash,
)


SCRIPT = (
    Path(__file__).parents[2]
    / "scripts"
    / "analysis"
    / "analyze_five_day_ranking_v2.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "analyze_five_day_ranking_v2",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _option_strings(parser: argparse.ArgumentParser) -> set[str]:
    found: set[str] = set()
    stack = [parser]
    while stack:
        current = stack.pop()
        for action in current._actions:
            found.update(action.option_strings)
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                stack.extend(choices.values())
    return found


def _research_review() -> FiveDayResearchReview:
    sessions = tuple(
        date(2023, 1, 2) + timedelta(days=index) for index in range(630)
    )
    split = ChronologicalSplit(
        train=sessions[:378],
        validation=sessions[378:504],
        test=sessions[504:630],
    )
    portfolio = FiveDayPortfolioMetrics(
        accepted_trades=0,
        maximum_drawdown=Decimal("0"),
        maximum_stock_trade_share=Decimal("0"),
        maximum_stock_profit_share=Decimal("0"),
        maximum_sector_trade_share=Decimal("0"),
        maximum_sector_profit_share=Decimal("0"),
        top5_profit_share=Decimal("0"),
        qualifies=False,
        reasons=("NO_ACCEPTED_TRADES",),
    )
    policy = SelectionPolicy()
    return _recompute_review(
        FiveDayResearchReview(
            split=split,
            input_fingerprint="f" * 64,
            formal_rule_version=policy.rule_version,
            formal_policy_hash=policy_hash(policy),
            profile_matrix_hash=five_day_profile_hash(
                build_five_day_return_profiles()
            ),
            sizing_version=SIZING_VERSION,
            evaluator_version=EVALUATOR_VERSION,
            cost_version=COST_VERSION,
            observations=(),
            train_calibrations={},
            validation_metrics=(),
            validation_portfolio=portfolio,
            point_in_time_complete=True,
            test_outcomes_read=False,
        )
    )


def _train_artifact(*, winner: bool) -> FiveDayRankingV2TrainArtifact:
    policy = build_five_day_v2_policies()[0]
    return FiveDayRankingV2TrainArtifact(
        artifact_identity="c" * 64,
        parent_research_identity="a" * 64,
        parent_input_fingerprint="f" * 64,
        policy_set_hash=five_day_v2_policy_set_hash(),
        winner_policy_id=policy.policy_id if winner else None,
        winner_policy_hash=(
            five_day_v2_policy_hash(policy) if winner else None
        ),
        winner_train_samples=48 if winner else 0,
        validation_eligible=winner,
        payload={},
    )


def _validation_review(
    train: FiveDayRankingV2TrainArtifact,
) -> FiveDayRankingV2ValidationReview:
    assert train.winner_policy_id is not None
    assert train.winner_policy_hash is not None
    metrics = FiveDaySegmentMetrics(
        profile_id="GLOBAL",
        segment="validation",
        triggered_resolved=0,
        net_expectancy=Decimal("0"),
        profit_factor=None,
        profitable_wilson_lower=Decimal("0"),
        stop_rate=Decimal("0"),
        positive_window_ratio=Decimal("0"),
        maximum_drawdown=Decimal("0"),
        qualifies=False,
        reasons=("SEGMENT_SAMPLES_TOO_LOW",),
    )
    segment = FiveDaySelectedSegment(
        metric_version="selected-portfolio-v2",
        metrics=metrics,
        portfolio=_research_review().validation_portfolio,
        selection=FiveDaySelection(
            ranking=FiveDayRanking(plans=(), rejection_counts={}),
            selected_observations=(),
            admitted=(),
            funnel_counts={},
            incomplete=False,
        ),
    )
    return FiveDayRankingV2ValidationReview(
        schema="five-day-ranking-v2-validation-v1",
        trial_identity=v2_validation_trial_identity(
            train.artifact_identity,
            train.winner_policy_hash,
        ),
        parent_train_identity=train.artifact_identity,
        parent_research_identity=train.parent_research_identity,
        parent_input_fingerprint=train.parent_input_fingerprint,
        winner_policy_id=train.winner_policy_id,
        winner_policy_hash=train.winner_policy_hash,
        validation_dates=_research_review().split.validation,
        segment=segment,
        qualifies_for_test_design=False,
        reasons=("SEGMENT_SAMPLES_TOO_LOW", "NO_ACCEPTED_TRADES"),
        validation_outcomes_read=True,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )


def _validate_argv(tmp_path: Path) -> tuple[str, ...]:
    train_path = tmp_path / "train.json"
    train_path.write_text("{}\n", encoding="utf-8")
    return (
        "validate-ranking",
        "--train-artifact",
        str(train_path),
        "--research-artifact",
        str(tmp_path / "research.json"),
        "--output-dir",
        str(tmp_path),
    )


def test_v2_parser_exposes_only_two_manual_stages() -> None:
    module = _load_module()
    parser = module.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert tuple(subparsers.choices) == (
        "diagnose-train",
        "validate-ranking",
    )
    assert {
        "--database-url",
        "--freeze",
        "--test",
        "--forward",
        "--notify",
    }.isdisjoint(_option_strings(parser))


def test_v2_diagnose_train_writes_no_later_stage_artifact(tmp_path) -> None:
    module = _load_module()
    parent = write_five_day_research(_research_review(), tmp_path)

    result = module.main(
        (
            "diagnose-train",
            "--research-artifact",
            str(parent),
            "--output-dir",
            str(tmp_path),
        )
    )

    assert result == 0
    assert len(tuple(tmp_path.glob("ranking-v2-train-*.json"))) == 1
    assert tuple(tmp_path.glob("ranking-v2-validation-*.json")) == ()


def test_v2_no_winner_stops_before_loading_research(
    tmp_path,
    monkeypatch,
) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "load_five_day_ranking_v2_train",
        lambda _: _train_artifact(winner=False),
    )
    monkeypatch.setattr(
        module,
        "load_five_day_research",
        lambda _: pytest.fail("research outcomes must not be read"),
    )

    assert module.main(_validate_argv(tmp_path)) == 2


def test_v2_existing_validation_reuses_before_loading_research(
    tmp_path,
    monkeypatch,
) -> None:
    module = _load_module()
    train = _train_artifact(winner=True)
    path = write_five_day_ranking_v2_validation(
        _validation_review(train),
        tmp_path,
    )
    monkeypatch.setattr(
        module,
        "load_five_day_ranking_v2_train",
        lambda _: train,
    )
    monkeypatch.setattr(
        module,
        "load_five_day_research",
        lambda _: pytest.fail("research outcomes must not be reread"),
    )

    assert module.main(_validate_argv(tmp_path)) == 0
    assert path.is_file()


def test_v2_conflicting_existing_validation_is_not_overwritten(
    tmp_path,
    monkeypatch,
) -> None:
    module = _load_module()
    train = _train_artifact(winner=True)
    path = write_five_day_ranking_v2_validation(
        _validation_review(train),
        tmp_path,
    )
    path.write_text("{}\n", encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(
        module,
        "load_five_day_ranking_v2_train",
        lambda _: train,
    )
    monkeypatch.setattr(
        module,
        "load_five_day_research",
        lambda _: pytest.fail("research outcomes must not be read"),
    )

    assert module.main(_validate_argv(tmp_path)) == 2
    assert path.read_bytes() == before


def test_v2_cli_sanitizes_dependency_details(monkeypatch, capsys) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "dispatch_command",
        lambda _: (_ for _ in ()).throw(
            ValueError("mysql://user:password@host/raw-observation")
        ),
    )

    result = module.main(
        (
            "diagnose-train",
            "--research-artifact",
            "x",
            "--output-dir",
            "y",
        )
    )
    captured = capsys.readouterr()

    assert result == 2
    assert captured.out == ""
    assert captured.err == "五日排名V2诊断失败\n"
