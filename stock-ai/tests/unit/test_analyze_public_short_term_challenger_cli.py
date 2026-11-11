from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import importlib.util
import json
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.models import BuyPointBar
from stock_ai.buy_point_selection.public_challenger_report import (
    load_challenger_research,
    write_challenger_research,
)
from stock_ai.buy_point_selection.public_challenger_runtime import (
    PublicChallengerRuntimeInputs,
)
from stock_ai.buy_point_selection.public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    RESIDUAL_TRACK,
)
from stock_ai.buy_point_selection.public_challenger_validation import (
    ChallengerAssessment,
    ChallengerPortfolioMetrics,
    ChallengerSegmentMetrics,
    PairedComparison,
    PublicChallengerResearchReview,
)
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    SectorMembership,
)
from stock_ai.buy_point_selection.validation import ChronologicalSplit


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/analysis/analyze_public_short_term_challenger.py"
SPEC = importlib.util.spec_from_file_location(
    "analyze_public_short_term_challenger",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _weekday_dates(count: int) -> tuple[date, ...]:
    result: list[date] = []
    current = date(2023, 1, 3)
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return tuple(result)


def _segment() -> ChallengerSegmentMetrics:
    return ChallengerSegmentMetrics(
        segment="VALIDATION",
        triggered_resolved=40,
        net_expectancy=Decimal("0.01"),
        profit_factor=Decimal("1.50"),
        profitable_wilson_lower=Decimal("0.50"),
        stop_rate=Decimal("0.20"),
        positive_window_ratio=Decimal("0.70"),
        maximum_drawdown=Decimal("0.05"),
        qualifies=True,
        reasons=(),
    )


def _assessment() -> ChallengerAssessment:
    return ChallengerAssessment(
        execution_metrics=_segment(),
        portfolio_metrics=ChallengerPortfolioMetrics(
            accepted_trades=40,
            maximum_drawdown=Decimal("0.05"),
            maximum_stock_trade_share=Decimal("0.05"),
            maximum_stock_profit_share=Decimal("0.10"),
            maximum_sector_trade_share=Decimal("0.20"),
            maximum_sector_profit_share=Decimal("0.25"),
            top5_profit_share=Decimal("0.20"),
            qualifies=True,
            reasons=(),
        ),
        paired=PairedComparison(
            paired_dates=40,
            mean_difference=Decimal("0.002"),
            confidence_interval=(Decimal("-0.001"), Decimal("0.005")),
            jaccard=Decimal("0.30"),
            incremental_resolved=30,
            incremental_expectancy=Decimal("0.01"),
            incremental_profit_factor=Decimal("1.30"),
        ),
        verdict="COMPLEMENTARY",
        reasons=(),
    )


def _eligible_research_review() -> PublicChallengerResearchReview:
    dates = _weekday_dates(66 + 630)[66:]
    metrics = _segment()
    return PublicChallengerResearchReview(
        split=ChronologicalSplit(dates[:378], dates[378:504], dates[504:]),
        input_fingerprint="a" * 64,
        track_metrics={
            CONTRARIAN_TRACK: metrics,
            RESIDUAL_TRACK: metrics,
            EXECUTION_TRACK: metrics,
        },
        validation_assessment=_assessment(),
        funnel_counts={},
        point_in_time_complete=True,
    )


def _runtime_inputs() -> PublicChallengerRuntimeInputs:
    calendar = _weekday_dates(66 + 630)
    signals = calendar[66:]
    codes = tuple(f"60000{value}" for value in range(1, 6))
    bars = {
        code: tuple(
            BuyPointBar(
                trade_date=trade_date,
                open=Decimal("10") + Decimal(offset),
                high=Decimal("10.1") + Decimal(offset),
                low=Decimal("9.9") + Decimal(offset),
                close=Decimal("10") + Decimal(offset),
                pct_chg=Decimal("0"),
                amount_qian=Decimal("1000000"),
            )
            for trade_date in calendar
        )
        for offset, code in enumerate(codes)
    }
    memberships = tuple(
        SectorMembership(
            code=code,
            sector_code="TEST",
            sector_name="测试行业",
            valid_from=calendar[0],
            valid_to=None,
            source="TEST",
        )
        for code in codes
    )
    return PublicChallengerRuntimeInputs(
        signal_dates=signals,
        trading_dates=calendar,
        bars_by_code=bars,
        memberships=memberships,
        risk_flags=(),
        coverage_by_date={
            value: ReferenceCoverage(value, True, True, True)
            for value in signals
        },
        market_status_by_date={value: "FREEZE" for value in signals},
        index_closes={
            index_id: {
                value: Decimal("100") + Decimal(position) / Decimal("10")
                for position, value in enumerate(calendar)
            }
            for index_id in ("sh.000001", "sz.399001", "sh.000688")
        },
        held_codes=frozenset(),
        input_fingerprint="a" * 64,
    )


def _forbidden_loader(*_args):
    raise AssertionError("loader must not be called")


def test_parser_exposes_only_three_manual_stages() -> None:
    parser = module.build_parser()

    assert set(parser._subparsers._group_actions[0].choices) == {
        "research",
        "freeze",
        "test",
    }


def test_research_cli_writes_no_trade_artifact(tmp_path) -> None:
    args = module.build_parser().parse_args(
        [
            "research",
            "--signal-start",
            "2023-04-05",
            "--signal-end",
            "2025-09-02",
            "--output-dir",
            str(tmp_path),
        ]
    )

    paths = module.dispatch_stage(
        args,
        research_input_loader=lambda *_: _runtime_inputs(),
        test_input_loader=_forbidden_loader,
    )

    artifact = load_challenger_research(paths[0])
    assert paths[0].name.startswith("public-short-term-challenger-research-")
    assert artifact.review.trade_permission == "NO-TRADE"
    assert artifact.review.test_outcomes_read is False


def test_freeze_stage_writes_validation_then_freeze(tmp_path) -> None:
    research_path = write_challenger_research(
        _eligible_research_review(),
        tmp_path,
    )
    args = module.build_parser().parse_args(
        [
            "freeze",
            "--research-artifact",
            str(research_path),
            "--output-dir",
            str(tmp_path),
        ]
    )

    paths = module.dispatch_stage(args, _forbidden_loader, _forbidden_loader)

    assert paths[0].name.startswith("public-short-term-challenger-validation-")
    assert paths[1].name.startswith("public-short-term-challenger-freeze-")


def test_main_sanitizes_failure(capsys) -> None:
    assert module.main(["research", "--signal-start", "bad"]) == 2
    assert capsys.readouterr().err == "公开短线策略挑战者执行失败\n"


def _parent_chain(tmp_path):
    research_path = write_challenger_research(
        _eligible_research_review(),
        tmp_path,
    )
    freeze_args = module.build_parser().parse_args(
        [
            "freeze",
            "--research-artifact",
            str(research_path),
            "--output-dir",
            str(tmp_path),
        ]
    )
    _, freeze_path = module.dispatch_stage(
        freeze_args,
        _forbidden_loader,
        _forbidden_loader,
    )
    return research_path, freeze_path


def _test_args(tmp_path, research_path: Path, freeze_path: Path):
    return module.build_parser().parse_args(
        [
            "test",
            "--research-artifact",
            str(research_path),
            "--freeze-artifact",
            str(freeze_path),
            "--output-dir",
            str(tmp_path),
        ]
    )


class _RecordingLoader:
    def __init__(self) -> None:
        self.calls: list[tuple[date, date, date]] = []

    def __call__(self, start: date, end: date, cutoff: date):
        self.calls.append((start, end, cutoff))
        return _runtime_inputs()


def test_test_stage_loads_freeze_before_market_data(tmp_path) -> None:
    loader = _RecordingLoader()
    args = _test_args(
        tmp_path,
        tmp_path / "missing-research.json",
        tmp_path / "missing-freeze.json",
    )

    with pytest.raises(ValueError, match="artifact"):
        module.dispatch_stage(args, _forbidden_loader, loader)

    assert loader.calls == []


def test_test_stage_reuses_existing_bytes_but_rejects_conflict(tmp_path) -> None:
    research_path, freeze_path = _parent_chain(tmp_path)
    args = _test_args(tmp_path, research_path, freeze_path)
    loader = _RecordingLoader()

    first = module.dispatch_stage(args, _forbidden_loader, loader)
    initial = first[0].read_bytes()
    second = module.dispatch_stage(args, _forbidden_loader, _forbidden_loader)

    assert first == second
    assert first[0].read_bytes() == initial
    assert len(loader.calls) == 1

    first[0].write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact"):
        module.dispatch_stage(args, _forbidden_loader, _forbidden_loader)


def test_missing_v3_comparable_artifact_forces_inconclusive(tmp_path) -> None:
    research_path, freeze_path = _parent_chain(tmp_path)
    args = _test_args(tmp_path, research_path, freeze_path)

    path = module.dispatch_stage(
        args,
        _forbidden_loader,
        lambda *_: _runtime_inputs(),
    )[0]
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["assessment"]["verdict"] == "INCONCLUSIVE"
    assert payload["trade_permission"] == "NO-TRADE"


def test_invalid_v3_artifact_fails_before_market_data(tmp_path) -> None:
    research_path, freeze_path = _parent_chain(tmp_path)
    invalid_v3 = tmp_path / "v3.json"
    invalid_v3.write_text("{}\n", encoding="utf-8")
    args = module.build_parser().parse_args(
        [
            "test",
            "--research-artifact",
            str(research_path),
            "--freeze-artifact",
            str(freeze_path),
            "--v3-test-artifact",
            str(invalid_v3),
            "--output-dir",
            str(tmp_path),
        ]
    )
    loader = _RecordingLoader()

    with pytest.raises(ValueError, match="V3 comparable artifact invalid"):
        module.dispatch_stage(args, _forbidden_loader, loader)

    assert loader.calls == []


def test_ineligible_freeze_never_loads_market_data(tmp_path) -> None:
    research_path = write_challenger_research(
        replace(_eligible_research_review(), point_in_time_complete=False),
        tmp_path,
    )
    freeze_args = module.build_parser().parse_args(
        [
            "freeze",
            "--research-artifact",
            str(research_path),
            "--output-dir",
            str(tmp_path),
        ]
    )
    _, freeze_path = module.dispatch_stage(
        freeze_args,
        _forbidden_loader,
        _forbidden_loader,
    )
    loader = _RecordingLoader()

    with pytest.raises(ValueError, match="freeze is not test eligible"):
        module.dispatch_stage(
            _test_args(tmp_path, research_path, freeze_path),
            _forbidden_loader,
            loader,
        )

    assert loader.calls == []
