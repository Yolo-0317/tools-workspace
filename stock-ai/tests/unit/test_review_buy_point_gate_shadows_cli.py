from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from scripts.analysis.review_buy_point_case import CaseReviewInputs
from scripts.analysis.review_buy_point_gate_shadows import (
    RESEARCH_WINDOWS,
    build_gate_forward_screen,
    build_gate_forward_settlement,
    build_gate_freeze_from_artifacts,
    build_gate_research_review,
    build_parser,
)
from stock_ai.buy_point_selection.gate_shadow_evaluation import (
    freeze_sector_gate_profiles,
)
from stock_ai.buy_point_selection.gate_shadow_report import (
    GateForwardScreen,
    GateResearchReview,
    gate_screen_payload,
    write_gate_forward_screen,
    write_gate_research_revision,
)
from stock_ai.buy_point_selection.gate_shadow_research import (
    GateShadowReplay,
    build_gate_shadow_profiles,
    gate_profile_matrix_hash,
)
from stock_ai.buy_point_selection.models import MarketSnapshot, SelectionPolicy
from stock_ai.buy_point_selection.reference_data import ReferenceCoverage
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ExactRecallComparison,
)
from stock_ai.buy_point_selection.validation import policy_hash


def _empty_inputs(signal_dates: tuple[date, ...], cutoff: date) -> CaseReviewInputs:
    future = []
    current = signal_dates[-1]
    while len(future) < 5:
        current += timedelta(days=1)
        if current.weekday() < 5 and current <= cutoff:
            future.append(current)
    return CaseReviewInputs(
        trading_dates=(*signal_dates, *future),
        bars_by_code={},
        memberships=(),
        risk_flags=(),
        coverage_by_date={},
        market_snapshots={},
        holding_codes_by_date={value: frozenset() for value in signal_dates},
        holdings_complete_by_date={value: True for value in signal_dates},
    )


def _v5(path: Path, signal_dates: tuple[date, ...], cutoff: date) -> Path:
    payload = {
        "schema": "buy-point-case-review-v5",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "case_identity": f"v5-{signal_dates[0]}",
        "signal_dates": [value.isoformat() for value in signal_dates],
        "outcome_cutoff": cutoff.isoformat(),
        "risk_coverage_complete": False,
        "daily_recall_winners": [],
        "daily_recall_metrics": {
            "winner_pairs": 0,
            "by_date": [
                {"signal_date": value.isoformat(), "winner_pairs": 0}
                for value in signal_dates
            ],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _empty_review(
    signal_dates: tuple[date, ...], cutoff: date, suffix: str
) -> GateResearchReview:
    policy = SelectionPolicy()
    profiles = build_gate_shadow_profiles()
    return GateResearchReview(
        signal_dates,
        cutoff,
        f"v5-{suffix}",
        f"input-{suffix}",
        policy.rule_version,
        policy_hash(policy),
        gate_profile_matrix_hash(profiles),
        profiles,
        GateShadowReplay(signal_dates, signal_dates, (), (), ()),
        (),
        (),
        (),
        (),
        ExactRecallComparison(0, 0, 0, 0, 0),
        False,
    )


def test_parser_exposes_four_manual_stages() -> None:
    parser = build_parser()
    research = parser.parse_args(
        [
            "research", "--signal-start", "2026-07-20",
            "--signal-end", "2026-07-24", "--outcome-cutoff", "2026-07-31",
            "--v5-case", "case.json",
        ]
    )
    freeze = parser.parse_args(
        [
            "freeze", "--research-artifact", "a.json",
            "--research-artifact", "b.json", "--research-artifact", "c.json",
        ]
    )
    screen = parser.parse_args(
        ["screen", "--signal-date", "2026-08-17", "--freeze-artifact", "f.json"]
    )
    settle = parser.parse_args(
        ["settle", "--screen-artifact", "s.json", "--outcome-cutoff", "2026-08-24"]
    )

    assert research.stage == "research"
    assert len(freeze.research_artifact) == 3
    assert screen.signal_date == date(2026, 8, 17)
    assert settle.stage == "settle"


def test_research_requires_an_approved_window_and_loads_inputs_once(
    tmp_path: Path,
) -> None:
    signal_dates, cutoff = RESEARCH_WINDOWS[0]
    v5_path = _v5(tmp_path / "case.json", signal_dates, cutoff)
    inputs = _empty_inputs(signal_dates, cutoff)
    calls = []

    def loader(start: date, end: date, observed_cutoff: date) -> CaseReviewInputs:
        calls.append((start, end, observed_cutoff))
        return inputs

    review = build_gate_research_review(
        signal_dates[0], signal_dates[-1], cutoff, v5_path, input_loader=loader
    )

    assert calls == [(signal_dates[0], signal_dates[-1], cutoff)]
    assert len(review.profiles) == 6
    assert review.replay.signal_dates == signal_dates
    assert not review.risk_coverage_complete
    with pytest.raises(ValueError, match="approved retrospective window"):
        build_gate_research_review(
            signal_dates[0], signal_dates[-2], cutoff, v5_path, input_loader=loader
        )


def test_freeze_requires_the_three_exact_research_artifacts(tmp_path: Path) -> None:
    paths = []
    for index, (signal_dates, cutoff) in enumerate(RESEARCH_WINDOWS):
        paths.append(
            write_gate_research_revision(
                _empty_review(signal_dates, cutoff, str(index)), tmp_path
            )[0]
        )

    freeze = build_gate_freeze_from_artifacts(paths)

    assert freeze.empty
    assert len(freeze.training_identities) == 3
    with pytest.raises(ValueError, match="exact research windows|distinct"):
        build_gate_freeze_from_artifacts((paths[0], paths[1], paths[1]))


def test_empty_forward_screen_uses_confirmed_calendar_without_outcomes(
    tmp_path: Path,
) -> None:
    signal_date = date(2026, 8, 17)
    profiles = build_gate_shadow_profiles()
    policy = SelectionPolicy()
    freeze = freeze_sector_gate_profiles(
        profiles=profiles,
        training_identities=("a", "b", "c"),
        metrics=(),
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=gate_profile_matrix_hash(profiles),
        risk_coverage_complete=False,
    )
    observed_plan_dates = []

    def loader(day: date, plan_dates: tuple[date, ...]) -> CaseReviewInputs:
        observed_plan_dates.append(plan_dates)
        return CaseReviewInputs(
            (day, *plan_dates),
            {},
            (),
            (),
            {day: ReferenceCoverage(day, True, True, False)},
            {day: MarketSnapshot(3, 60.0, 1.0, True)},
            {day: frozenset()},
            {day: True},
        )

    statuses = {
        signal_date: True,
        date(2026, 8, 18): True,
        date(2026, 8, 19): True,
    }
    screen = build_gate_forward_screen(
        signal_date,
        freeze,
        input_loader=loader,
        calendar_status=lambda day: statuses.get(day, False),
    )

    assert observed_plan_dates == [(date(2026, 8, 18), date(2026, 8, 19))]
    assert screen.candidates == ()
    assert "outcomes" not in gate_screen_payload(screen)

    with pytest.raises(ValueError, match="not confirmed"):
        build_gate_forward_screen(
            signal_date,
            freeze,
            input_loader=loader,
            calendar_status=lambda day: None,
        )


def test_settlement_keeps_empty_screen_immutable(tmp_path: Path) -> None:
    signal_date = date(2026, 8, 17)
    policy = SelectionPolicy()
    profiles = build_gate_shadow_profiles()
    screen = GateForwardScreen(
        signal_date,
        "screen-input",
        policy.rule_version,
        policy_hash(policy),
        gate_profile_matrix_hash(profiles),
        "freeze-hash",
        (),
        False,
    )
    screen_path = write_gate_forward_screen(screen, tmp_path)[0]
    before = screen_path.read_bytes()
    outcome_dates = tuple(date(2026, 8, value) for value in (18, 19, 20, 21, 24))
    inputs = CaseReviewInputs(
        (signal_date, *outcome_dates), {}, (), (), {}, {}, {}, {}
    )

    settlement = build_gate_forward_settlement(
        screen_path,
        date(2026, 8, 24),
        input_loader=lambda start, cutoff: inputs,
    )

    assert settlement.outcome_dates == outcome_dates
    assert settlement.candidates == ()
    assert settlement.outcomes == ()
    assert screen_path.read_bytes() == before
