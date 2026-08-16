from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import importlib.util
from pathlib import Path

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
    / "analyze_five_day_ranking.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "analyze_five_day_ranking",
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
    review = FiveDayResearchReview(
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
    return _recompute_review(review)


def test_parser_exposes_only_the_two_manual_diagnostic_stages() -> None:
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


def test_diagnose_train_writes_no_validation_artifact(tmp_path) -> None:
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
    assert len(tuple(tmp_path.glob("ranking-train-*.json"))) == 1
    assert tuple(tmp_path.glob("ranking-validation-*.json")) == ()


def test_validate_ranking_writes_the_preregistered_validation_artifact(
    tmp_path,
) -> None:
    module = _load_module()
    parent = write_five_day_research(_research_review(), tmp_path)
    assert module.main(
        (
            "diagnose-train",
            "--research-artifact",
            str(parent),
            "--output-dir",
            str(tmp_path),
        )
    ) == 0
    train = next(tmp_path.glob("ranking-train-*.json"))

    result = module.main(
        (
            "validate-ranking",
            "--train-artifact",
            str(train),
            "--research-artifact",
            str(parent),
            "--output-dir",
            str(tmp_path),
        )
    )

    assert result == 0
    assert len(tuple(tmp_path.glob("ranking-validation-*.json"))) == 1


def test_existing_validation_is_reused_before_loading_research(
    tmp_path,
    monkeypatch,
) -> None:
    module = _load_module()
    parent = write_five_day_research(_research_review(), tmp_path)
    diagnose_args = (
        "diagnose-train",
        "--research-artifact",
        str(parent),
        "--output-dir",
        str(tmp_path),
    )
    assert module.main(diagnose_args) == 0
    train = next(tmp_path.glob("ranking-train-*.json"))
    validate_args = (
        "validate-ranking",
        "--train-artifact",
        str(train),
        "--research-artifact",
        str(parent),
        "--output-dir",
        str(tmp_path),
    )
    assert module.main(validate_args) == 0
    validation = next(tmp_path.glob("ranking-validation-*.json"))
    before = validation.read_bytes()

    def fail_if_research_is_loaded(_path):
        raise RuntimeError("research must not be loaded")

    monkeypatch.setattr(
        module,
        "load_five_day_research",
        fail_if_research_is_loaded,
    )

    assert module.main(validate_args) == 0
    assert validation.read_bytes() == before


def test_validation_rejects_a_mismatched_parent_without_output(
    tmp_path,
    monkeypatch,
) -> None:
    module = _load_module()
    parent = write_five_day_research(_research_review(), tmp_path)
    assert module.main(
        (
            "diagnose-train",
            "--research-artifact",
            str(parent),
            "--output-dir",
            str(tmp_path),
        )
    ) == 0
    train = next(tmp_path.glob("ranking-train-*.json"))
    other_parent = write_five_day_research(
        replace(_research_review(), input_fingerprint="e" * 64),
        tmp_path,
    )

    def fail_if_calculation_starts(*_args):
        raise AssertionError("validation calculation must not start")

    monkeypatch.setattr(
        module,
        "build_five_day_ranking_validation_review",
        fail_if_calculation_starts,
    )

    result = module.main(
        (
            "validate-ranking",
            "--train-artifact",
            str(train),
            "--research-artifact",
            str(other_parent),
            "--output-dir",
            str(tmp_path),
        )
    )

    assert result == 2
    assert tuple(tmp_path.glob("ranking-validation-*.json")) == ()


def test_conflicting_existing_validation_is_rejected_without_overwrite(
    tmp_path,
) -> None:
    module = _load_module()
    parent = write_five_day_research(_research_review(), tmp_path)
    assert module.main(
        (
            "diagnose-train",
            "--research-artifact",
            str(parent),
            "--output-dir",
            str(tmp_path),
        )
    ) == 0
    train = next(tmp_path.glob("ranking-train-*.json"))
    args = (
        "validate-ranking",
        "--train-artifact",
        str(train),
        "--research-artifact",
        str(parent),
        "--output-dir",
        str(tmp_path),
    )
    assert module.main(args) == 0
    validation = next(tmp_path.glob("ranking-validation-*.json"))
    validation.write_text("{}\n", encoding="utf-8")
    before = validation.read_bytes()

    assert module.main(args) == 2
    assert validation.read_bytes() == before


def test_errors_do_not_expose_observations_or_credentials(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    parent = tmp_path / "research.json"
    parent.write_text("{}\n", encoding="utf-8")

    def fail_with_sensitive_details(_path):
        raise ValueError(
            "mysql://advisor:top-secret@db/stock observations=[raw-return]"
        )

    monkeypatch.setattr(
        module,
        "load_five_day_research",
        fail_with_sensitive_details,
    )

    result = module.main(
        (
            "diagnose-train",
            "--research-artifact",
            str(parent),
            "--output-dir",
            str(tmp_path),
        )
    )
    captured = capsys.readouterr()

    assert result == 2
    assert captured.out == ""
    assert captured.err == "五日排名诊断失败\n"
