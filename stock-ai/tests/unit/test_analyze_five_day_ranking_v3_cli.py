from __future__ import annotations

import argparse
from dataclasses import replace
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    FiveDayV3PolicyFingerprint,
    V3MonotonicityAssessment,
    V3RankBandMetrics,
    assess_five_day_v3_policy,
    build_five_day_ranking_v3_train_review,
    build_five_day_ranking_v3_validation_review,
    finalize_five_day_ranking_v3_train,
    five_day_v3_selection_fingerprint,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_report import (
    FiveDayRankingV3TrainArtifact,
    load_five_day_ranking_v3_train,
    write_five_day_ranking_v3_train,
    write_five_day_ranking_v3_validation,
)
from stock_ai.buy_point_selection.five_day_return_report import (
    _recompute_review,
    five_day_research_payload,
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

from five_day_ranking_v3_fixtures import (
    make_v3_observation,
    make_v3_plan,
    make_v3_research_review,
    weekday_dates,
)


SCRIPT = (
    Path(__file__).parents[2]
    / "scripts"
    / "analysis"
    / "analyze_five_day_ranking_v3.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "analyze_five_day_ranking_v3",
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
    return _recompute_review(make_v3_research_review(()))


def _winner_research() -> FiveDayResearchReview:
    sessions = weekday_dates(630)
    observations = tuple(
        make_v3_observation(
            make_v3_plan(
                sessions[index],
                code=f"{600000 + index:06d}",
            ),
            resolution_date=sessions[index + 1],
        )
        for index in range(60)
    )
    return _recompute_review(make_v3_research_review(observations))


def _segment(*, samples: int, edge: str) -> FiveDaySelectedSegment:
    metrics = FiveDaySegmentMetrics(
        profile_id="V3",
        segment="TRAIN",
        triggered_resolved=samples,
        net_expectancy=Decimal(edge),
        profit_factor=Decimal("1.1001"),
        profitable_wilson_lower=Decimal("0.50"),
        stop_rate=Decimal("0.20"),
        positive_window_ratio=Decimal("0.60"),
        maximum_drawdown=Decimal("0.05"),
        qualifies=True,
        reasons=(),
    )
    return FiveDaySelectedSegment(
        metric_version="selected-portfolio-v2",
        metrics=metrics,
        portfolio=FiveDayPortfolioMetrics(
            accepted_trades=samples,
            maximum_drawdown=Decimal("0.05"),
            maximum_stock_trade_share=Decimal("0.10"),
            maximum_stock_profit_share=Decimal("0.10"),
            maximum_sector_trade_share=Decimal("0.20"),
            maximum_sector_profit_share=Decimal("0.20"),
            top5_profit_share=Decimal("0.30"),
            qualifies=True,
            reasons=(),
        ),
        selection=FiveDaySelection(
            ranking=FiveDayRanking(plans=(), rejection_counts={}),
            selected_observations=(),
            admitted=(),
            funnel_counts={},
            incomplete=False,
        ),
    )


def _qualifying_assessment(policy):
    monotonicity = V3MonotonicityAssessment(
        bands=(
            V3RankBandMetrics("RANK_1", 15, Decimal("0.006")),
            V3RankBandMetrics("RANK_2_3", 15, Decimal("0.005")),
            V3RankBandMetrics("RANK_4_5", 15, Decimal("0.004")),
            V3RankBandMetrics("RANK_6_PLUS", 15, Decimal("0.002")),
        ),
        qualifies=True,
        reasons=(),
    )
    return assess_five_day_v3_policy(
        policy=policy,
        fold1=_segment(samples=20, edge="0.002"),
        fold2=_segment(samples=20, edge="0.003"),
        combined=_segment(samples=40, edge="0.003"),
        monotonicity=monotonicity,
    )


def _write_no_winner_train(
    tmp_path: Path,
) -> FiveDayRankingV3TrainArtifact:
    research = _research_review()
    parent_identity = str(
        five_day_research_payload(research)["artifact_identity"]
    )
    review = build_five_day_ranking_v3_train_review(
        research,
        parent_research_identity=parent_identity,
    )
    path = write_five_day_ranking_v3_train(review, tmp_path)
    return load_five_day_ranking_v3_train(
        path,
        expected_parent_research_identity=parent_identity,
    )


def _write_winner_train(
    tmp_path: Path,
) -> tuple[
    FiveDayResearchReview,
    Path,
    FiveDayRankingV3TrainArtifact,
    Path,
]:
    research = _winner_research()
    parent_path = write_five_day_research(research, tmp_path)
    parent_identity = str(
        five_day_research_payload(research)["artifact_identity"]
    )
    review = build_five_day_ranking_v3_train_review(
        research,
        parent_research_identity=parent_identity,
    )
    segments = {
        "train-fold-1": _segment(samples=20, edge="0.002"),
        "train-fold-2": _segment(samples=20, edge="0.003"),
        "train-combined": _segment(samples=40, edge="0.003"),
    }
    fingerprint_names = ("a", "a", "b", "b", "c", "c", "d", "d")
    review = finalize_five_day_ranking_v3_train(
        replace(
            review,
            variants=tuple(
                replace(value, segment=segments[value.fold_id])
                if value.selection_mode == "FORMAL"
                else value
                for value in review.variants
            ),
            assessments=tuple(
                _qualifying_assessment(policy) for policy in review.policies
            ),
            policy_fingerprints=tuple(
                FiveDayV3PolicyFingerprint(
                    policy_id=policy.policy_id,
                    selected_structure_keys=(name,),
                    fingerprint=five_day_v3_selection_fingerprint((name,)),
                )
                for policy, name in zip(
                    review.policies,
                    fingerprint_names,
                    strict=True,
                )
            ),
        )
    )
    train_path = write_five_day_ranking_v3_train(review, tmp_path)
    train = load_five_day_ranking_v3_train(
        train_path,
        expected_parent_research_identity=parent_identity,
    )
    return research, parent_path, train, train_path


def _write_existing_validation(
    train: FiveDayRankingV3TrainArtifact,
    research: FiveDayResearchReview,
    tmp_path: Path,
) -> Path:
    review = build_five_day_ranking_v3_validation_review(
        research,
        train,
        parent_research_identity=train.parent_research_identity,
    )
    return write_five_day_ranking_v3_validation(review, tmp_path)


def _diagnose_argv(tmp_path: Path) -> tuple[str, ...]:
    return (
        "diagnose-train",
        "--research-artifact",
        str(tmp_path / "research.json"),
        "--output-dir",
        str(tmp_path),
    )


def _validate_argv(tmp_path: Path) -> tuple[str, ...]:
    train_path = tmp_path / "train-input.json"
    research_path = tmp_path / "research.json"
    train_path.write_text("{}\n", encoding="utf-8")
    research_path.write_text("{}\n", encoding="utf-8")
    return (
        "validate-ranking",
        "--train-artifact",
        str(train_path),
        "--research-artifact",
        str(research_path),
        "--output-dir",
        str(tmp_path),
    )


def test_v3_parser_exposes_only_two_manual_stages() -> None:
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
        "--signal-start",
        "--signal-end",
        "--freeze",
        "--test",
        "--forward",
        "--notify",
        "--settle",
    }.isdisjoint(_option_strings(parser))


def test_v3_parser_converts_required_paths() -> None:
    module = _load_module()

    args = module.build_parser().parse_args(
        (
            "validate-ranking",
            "--train-artifact",
            "train.json",
            "--research-artifact",
            "research.json",
            "--output-dir",
            "output",
        )
    )

    assert args.train_artifact == Path("train.json")
    assert args.research_artifact == Path("research.json")
    assert args.output_dir == Path("output")


def test_v3_diagnose_train_writes_no_later_artifact(
    tmp_path: Path,
) -> None:
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
    assert len(tuple(tmp_path.glob("ranking-v3-train-*.json"))) == 1
    assert tuple(tmp_path.glob("ranking-v3-validation-*.json")) == ()


def test_v3_no_winner_stops_before_loading_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    train = _write_no_winner_train(tmp_path)
    monkeypatch.setattr(
        module,
        "load_five_day_ranking_v3_train",
        lambda _: train,
    )
    monkeypatch.setattr(
        module,
        "load_five_day_research",
        lambda _: pytest.fail("parent outcomes must not be read"),
    )

    assert module.main(_validate_argv(tmp_path)) == 2


def test_v3_existing_validation_reuses_before_loading_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    research, _, train, _ = _write_winner_train(tmp_path)
    existing = _write_existing_validation(train, research, tmp_path)
    monkeypatch.setattr(
        module,
        "load_five_day_ranking_v3_train",
        lambda _: train,
    )
    monkeypatch.setattr(
        module,
        "load_five_day_research",
        lambda _: pytest.fail("parent outcomes must not be reread"),
    )

    assert module.main(_validate_argv(tmp_path)) == 0
    assert existing.is_file()


def test_v3_conflicting_existing_validation_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    research, _, train, _ = _write_winner_train(tmp_path)
    existing = _write_existing_validation(train, research, tmp_path)
    existing.write_text("{}\n", encoding="utf-8")
    before = existing.read_bytes()
    monkeypatch.setattr(
        module,
        "load_five_day_ranking_v3_train",
        lambda _: train,
    )
    monkeypatch.setattr(
        module,
        "load_five_day_research",
        lambda _: pytest.fail("parent outcomes must not be read"),
    )

    assert module.main(_validate_argv(tmp_path)) == 2
    assert existing.read_bytes() == before


def test_v3_validate_ranking_writes_one_locked_validation(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _, parent_path, _, train_path = _write_winner_train(tmp_path)

    result = module.main(
        (
            "validate-ranking",
            "--train-artifact",
            str(train_path),
            "--research-artifact",
            str(parent_path),
            "--output-dir",
            str(tmp_path),
        )
    )

    assert result == 0
    assert len(tuple(tmp_path.glob("ranking-v3-validation-*.json"))) == 1


def test_v3_cli_sanitizes_dependency_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "dispatch_command",
        lambda _: (_ for _ in ()).throw(
            ValueError("mysql://user:secret@host/raw-observation")
        ),
    )

    result = module.main(_diagnose_argv(tmp_path))
    captured = capsys.readouterr()

    assert result == 2
    assert captured.out == ""
    assert captured.err == "五日排名V3诊断失败\n"
