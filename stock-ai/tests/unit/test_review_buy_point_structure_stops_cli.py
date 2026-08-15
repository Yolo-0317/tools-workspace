from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path

import pytest

from scripts.analysis.review_buy_point_structure_stops import (
    build_structure_stop_forward_settlement,
    build_structure_stop_forward_screen,
    build_structure_stop_freeze_from_artifacts,
    build_structure_stop_research_review,
    build_parser,
    derive_structure_stop_windows,
    main,
)
from scripts.analysis.review_buy_point_case import CaseReviewInputs
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    MarketSnapshot,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.reference_data import ReferenceCoverage
from stock_ai.buy_point_selection.structure_stop_shadow import (
    StructureStopAnchor,
    StructureStopBaselineHit,
    StructureStopCandidate,
    StructureStopDiagnostic,
    StructureStopReplay,
    build_structure_stop_profiles,
    structure_stop_profile_hash,
)
from stock_ai.buy_point_selection.structure_stop_report import (
    StructureStopForwardScreen,
    StructureStopResearchReview,
    StructureStopScreenCandidate,
    structure_stop_screen_identity,
    structure_stop_screen_payload,
    structure_stop_settlement_payload,
    write_structure_stop_forward_screen,
    write_structure_stop_forward_settlement,
    write_structure_stop_freeze,
    write_structure_stop_research_revision,
)
from stock_ai.buy_point_selection.structure_stop_evaluation import (
    StructureStopMetrics,
    freeze_structure_stop_profiles,
)
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ExactRecallComparison,
)
from stock_ai.buy_point_selection.validation import policy_hash


def _confirmed_sessions() -> tuple[date, ...]:
    sessions = []
    current = date(2026, 8, 14)
    while len(sessions) < 80:
        if current.weekday() < 5:
            sessions.append(current)
        current -= timedelta(days=1)
    return tuple(reversed(sessions))


def test_parser_exposes_four_manual_zero_share_stages() -> None:
    """Catches a missing stage or freeze accepting an implicit artifact set."""
    parser = build_parser()
    research = parser.parse_args(
        [
            "research",
            "--signal-start",
            "2026-07-20",
            "--signal-end",
            "2026-07-24",
            "--outcome-cutoff",
            "2026-07-31",
            "--v5-case",
            "case.json",
        ]
    )
    freeze_args = ["freeze"]
    for index in range(8):
        freeze_args.extend(
            ("--research-artifact", f"research-{index}.json")
        )
    freeze = parser.parse_args(freeze_args)
    screen = parser.parse_args(
        [
            "screen",
            "--signal-date",
            "2026-08-17",
            "--freeze-artifact",
            "freeze.json",
        ]
    )
    settle = parser.parse_args(
        [
            "settle",
            "--screen-artifact",
            "screen.json",
            "--outcome-cutoff",
            "2026-08-24",
        ]
    )

    assert research.signal_start == date(2026, 7, 20)
    assert research.output_dir.endswith("buy_point_structure_stops")
    assert len(freeze.research_artifact) == 8
    assert screen.signal_date == date(2026, 8, 17)
    assert settle.outcome_cutoff == date(2026, 8, 24)


def test_calendar_derives_eight_exact_five_plus_five_blocks() -> None:
    """Catches calendar-week inference or overlapping signal/result windows."""
    sessions = _confirmed_sessions()

    windows = derive_structure_stop_windows(sessions)

    assert len(windows) == 8
    assert all(len(signal_dates) == 5 for signal_dates, _ in windows)
    assert windows[-1] == (
        (
            date(2026, 8, 3),
            date(2026, 8, 4),
            date(2026, 8, 5),
            date(2026, 8, 6),
            date(2026, 8, 7),
        ),
        date(2026, 8, 14),
    )
    for index, (signal_dates, cutoff) in enumerate(windows):
        block = sessions[index * 10 : (index + 1) * 10]
        assert signal_dates == block[:5]
        assert cutoff == block[-1]


def test_calendar_rejects_missing_or_unordered_sessions() -> None:
    """Catches silently filling a missing confirmed date with a weekday guess."""
    sessions = _confirmed_sessions()

    with pytest.raises(ValueError, match="80 confirmed trading sessions"):
        derive_structure_stop_windows(sessions[:31] + sessions[32:])
    with pytest.raises(ValueError, match="strictly ordered"):
        derive_structure_stop_windows(tuple(reversed(sessions)))


def _v5_case(
    path: Path,
    signal_dates: tuple[date, ...],
    cutoff: date,
) -> Path:
    payload = {
        "schema": "buy-point-case-review-v5",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "case_identity": "v5-final-window",
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


def _empty_inputs(
    sessions: tuple[date, ...],
    signal_dates: tuple[date, ...],
) -> CaseReviewInputs:
    return CaseReviewInputs(
        trading_dates=sessions,
        bars_by_code={},
        memberships=(),
        risk_flags=(),
        coverage_by_date={
            value: ReferenceCoverage(value, True, True, False)
            for value in signal_dates
        },
        market_snapshots={
            value: MarketSnapshot(3, 60.0, 1.0, True)
            for value in signal_dates
        },
        holding_codes_by_date={
            value: frozenset() for value in signal_dates
        },
        holdings_complete_by_date={value: True for value in signal_dates},
    )


def test_research_builder_loads_once_and_keeps_diagnostics_out_of_metrics(
    tmp_path: Path,
) -> None:
    """Catches repeated reads or diagnostic rows entering primary metrics."""
    sessions = _confirmed_sessions()
    signal_dates = sessions[-10:-5]
    cutoff = sessions[-1]
    inputs = _empty_inputs(sessions, signal_dates)
    v5_path = _v5_case(tmp_path / "v5.json", signal_dates, cutoff)
    calls = []

    def loader(start: date, end: date, observed_cutoff: date) -> CaseReviewInputs:
        calls.append((start, end, observed_cutoff))
        return inputs

    review = build_structure_stop_research_review(
        signal_dates[0],
        signal_dates[-1],
        cutoff,
        v5_path,
        input_loader=loader,
        confirmed_dates=sessions,
    )

    policy = SelectionPolicy()
    assert calls == [(signal_dates[0], signal_dates[-1], cutoff)]
    assert review.signal_dates == signal_dates
    assert review.outcome_cutoff == cutoff
    assert review.formal_rule_version == policy.rule_version
    assert review.formal_policy_hash == policy_hash(policy)
    assert review.profile_matrix_hash == structure_stop_profile_hash(
        review.profiles
    )
    assert len(review.profiles) == 3
    assert review.replay.signal_dates == signal_dates
    assert review.replay.diagnostics == ()
    assert review.profile_metrics == ()
    assert review.risk_coverage_complete is False


def test_research_builder_fails_closed_on_window_or_holdings_drift(
    tmp_path: Path,
) -> None:
    """Catches unconfirmed blocks and incomplete point-in-time holdings."""
    sessions = _confirmed_sessions()
    signal_dates = sessions[-10:-5]
    cutoff = sessions[-1]
    v5_path = _v5_case(tmp_path / "v5.json", signal_dates, cutoff)
    inputs = _empty_inputs(sessions, signal_dates)

    with pytest.raises(ValueError, match="derived research window"):
        build_structure_stop_research_review(
            signal_dates[0] + timedelta(days=1),
            signal_dates[-1],
            cutoff,
            v5_path,
            input_loader=lambda *_: inputs,
            confirmed_dates=sessions,
        )

    incomplete = CaseReviewInputs(
        inputs.trading_dates,
        inputs.bars_by_code,
        inputs.memberships,
        inputs.risk_flags,
        inputs.coverage_by_date,
        inputs.market_snapshots,
        inputs.holding_codes_by_date,
        {**inputs.holdings_complete_by_date, signal_dates[0]: False},
    )
    with pytest.raises(ValueError, match="holdings are incomplete"):
        build_structure_stop_research_review(
            signal_dates[0],
            signal_dates[-1],
            cutoff,
            v5_path,
            input_loader=lambda *_: incomplete,
            confirmed_dates=sessions,
        )


def _empty_review(
    signal_dates: tuple[date, ...],
    cutoff: date,
    suffix: str,
) -> StructureStopResearchReview:
    policy = SelectionPolicy()
    profiles = build_structure_stop_profiles()
    return StructureStopResearchReview(
        signal_dates=signal_dates,
        outcome_cutoff=cutoff,
        v5_case_identity=f"v5-{suffix}",
        input_fingerprint=f"input-{suffix}",
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=structure_stop_profile_hash(profiles),
        profiles=profiles,
        replay=StructureStopReplay(signal_dates, (), (), (), (), ()),
        outcomes=(),
        profile_metrics=(),
        exact_recall=ExactRecallComparison(0, 0, 0, 0, 0),
        risk_coverage_complete=False,
    )


def _research_paths(tmp_path: Path) -> list[Path]:
    paths = []
    for index, (signal_dates, cutoff) in enumerate(
        derive_structure_stop_windows(_confirmed_sessions())
    ):
        paths.append(
            write_structure_stop_research_revision(
                _empty_review(signal_dates, cutoff, str(index)),
                tmp_path,
            )[0]
        )
    return paths


def test_freeze_reconstructs_the_eight_exact_windows_and_allows_empty(
    tmp_path: Path,
) -> None:
    """Catches window padding while preserving a valid empty freeze result."""
    sessions = _confirmed_sessions()
    paths = _research_paths(tmp_path)

    freeze = build_structure_stop_freeze_from_artifacts(
        paths, confirmed_dates=sessions
    )

    assert freeze.empty
    assert freeze.profiles == ()
    assert len(freeze.training_identities) == 8
    assert freeze.promotion_eligible is False

    with pytest.raises(ValueError, match="distinct research identities"):
        build_structure_stop_freeze_from_artifacts(
            (*paths[:7], paths[0]), confirmed_dates=sessions
        )

    wrong = write_structure_stop_research_revision(
        _empty_review(
            (date(2026, 1, 5),) * 5,
            date(2026, 1, 12),
            "wrong-window",
        ),
        tmp_path,
    )[0]
    with pytest.raises(ValueError, match="eight exact research windows"):
        build_structure_stop_freeze_from_artifacts(
            (*paths[:7], wrong), confirmed_dates=sessions
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "version",
        "shares",
        "membership",
        "diagnostic_candidate",
        "metrics",
    ),
)
def test_freeze_rejects_tampered_raw_or_summary_rows(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Catches trusting edited rows, diagnostics, or reported qualifiers."""
    sessions = _confirmed_sessions()
    paths = _research_paths(tmp_path)
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    if mutation == "version":
        payload["formal_rule_version"] = "edited-rule"
    elif mutation == "shares":
        payload["diagnostics"] = [
            {
                "signal_date": payload["signal_dates"][0],
                "code": "600001",
                "label": "DIAGNOSTIC_ONLY_COMBINED_FAILURE",
                "executable_shares": 100,
            }
        ]
        payload["metrics"]["diagnostics"] = 1
    elif mutation in ("membership", "diagnostic_candidate"):
        candidate = {
            "signal_date": payload["signal_dates"][0],
            "code": "600001",
            "profile_id": "STRUCTURE_STOP:RECENT_SETUP_LOW",
            "setup_type": "PRE_BREAKOUT",
            "executable_shares": 0,
        }
        if mutation == "diagnostic_candidate":
            candidate["label"] = "DIAGNOSTIC_ONLY_COMBINED_FAILURE"
        payload["candidates"] = [candidate]
        payload["metrics"]["candidates"] = 1
    else:
        payload["profile_metrics"] = [
            {
                "profile_id": "STRUCTURE_STOP:RECENT_SETUP_LOW",
                "setup_type": "ALL",
                "candidate_count": 10,
                "triggered": 10,
                "resolved": 10,
                "positive_net": 6,
                "stop_first": 3,
                "mean_net_return": "0.01",
                "median_net_return": "0.01",
                "positive_net_rate": "0.60",
                "stop_first_rate": "0.30",
                "mean_mfe": "0.06",
                "mean_mae": "0.02",
                "qualifies": True,
                "qualification_reasons": [],
            }
        ]
        payload["metrics"]["profile_metrics"] = 1
    paths[0].write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="structure stop research"):
        build_structure_stop_freeze_from_artifacts(
            paths, confirmed_dates=sessions
        )


def test_main_writes_valid_empty_research_and_freeze_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Catches orchestration that omits either immutable output pair."""
    sessions = _confirmed_sessions()
    signal_dates = sessions[-10:-5]
    cutoff = sessions[-1]
    inputs = _empty_inputs(sessions, signal_dates)
    v5_path = _v5_case(tmp_path / "v5.json", signal_dates, cutoff)
    research_dir = tmp_path / "research"

    research_code = main(
        [
            "research",
            "--signal-start",
            signal_dates[0].isoformat(),
            "--signal-end",
            signal_dates[-1].isoformat(),
            "--outcome-cutoff",
            cutoff.isoformat(),
            "--v5-case",
            str(v5_path),
            "--output-dir",
            str(research_dir),
        ],
        input_loader=lambda *_: inputs,
        confirmed_dates_loader=lambda: sessions,
    )

    research_output = capsys.readouterr().out
    research_json = tuple(research_dir.glob("research_*.json"))
    assert research_code == 0
    assert "CASE_ANALYSIS_ONLY / NO-TRADE" in research_output
    assert len(research_json) == 1
    assert len(tuple(research_dir.glob("research_*.md"))) == 1

    all_research = _research_paths(tmp_path / "eight")
    freeze_dir = tmp_path / "freeze"
    freeze_args = ["freeze"]
    for path in all_research:
        freeze_args.extend(("--research-artifact", str(path)))
    freeze_args.extend(("--output-dir", str(freeze_dir)))
    freeze_code = main(
        freeze_args,
        confirmed_dates_loader=lambda: sessions,
    )

    freeze_output = capsys.readouterr().out
    assert freeze_code == 0
    assert "CASE_ANALYSIS_ONLY / NO-TRADE" in freeze_output
    assert len(tuple(freeze_dir.glob("freeze-*.json"))) == 1
    assert len(tuple(freeze_dir.glob("freeze-*.md"))) == 1


@pytest.mark.parametrize("failure", ("holdings", "lineage", "immutable"))
def test_main_fails_closed_with_concise_chinese_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    """Catches orchestration swallowing unsafe input or immutable conflicts."""
    sessions = _confirmed_sessions()
    signal_dates = sessions[-10:-5]
    cutoff = sessions[-1]
    inputs = _empty_inputs(sessions, signal_dates)
    if failure == "holdings":
        inputs = CaseReviewInputs(
            inputs.trading_dates,
            inputs.bars_by_code,
            inputs.memberships,
            inputs.risk_flags,
            inputs.coverage_by_date,
            inputs.market_snapshots,
            inputs.holding_codes_by_date,
            {**inputs.holdings_complete_by_date, signal_dates[0]: False},
        )
    v5_path = _v5_case(tmp_path / "v5.json", signal_dates, cutoff)
    if failure == "lineage":
        payload = json.loads(v5_path.read_text(encoding="utf-8"))
        payload["trade_permission"] = "ALLOW"
        v5_path.write_text(json.dumps(payload), encoding="utf-8")

    def broken_writer(*_args: object) -> tuple[Path, Path]:
        raise ValueError("immutable artifact content mismatch")

    code = main(
        [
            "research",
            "--signal-start",
            signal_dates[0].isoformat(),
            "--signal-end",
            signal_dates[-1].isoformat(),
            "--outcome-cutoff",
            cutoff.isoformat(),
            "--v5-case",
            str(v5_path),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        input_loader=lambda *_: inputs,
        confirmed_dates_loader=lambda: sessions,
        research_writer=(broken_writer if failure == "immutable" else None),
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("结构止损影子研究失败：")


def test_main_runs_bounded_screen_and_separate_settlement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Catches CLI stages bypassing bounded builders or overwriting screens."""
    signal_date = date(2026, 8, 17)
    plan_dates = (date(2026, 8, 18), date(2026, 8, 19))
    screen_inputs = CaseReviewInputs(
        (signal_date, *plan_dates),
        {},
        (),
        (),
        {signal_date: ReferenceCoverage(signal_date, True, True, False)},
        {signal_date: MarketSnapshot(3, 60.0, 1.0, True)},
        {signal_date: frozenset()},
        {signal_date: True},
    )
    freeze_path = write_structure_stop_freeze(
        _empty_freeze(), tmp_path / "freeze"
    )[0]
    screen_dir = tmp_path / "screen"

    screen_code = main(
        [
            "screen",
            "--signal-date", signal_date.isoformat(),
            "--freeze-artifact",
            str(freeze_path),
            "--output-dir",
            str(screen_dir),
        ],
        screen_input_loader=lambda *_: screen_inputs,
        calendar_status=lambda day: day in (signal_date, *plan_dates),
    )

    assert screen_code == 0
    assert "CASE_ANALYSIS_ONLY / NO-TRADE" in capsys.readouterr().out
    screen_path = tuple(screen_dir.glob("screen_*.json"))[0]
    before = screen_path.read_bytes()
    outcome_dates = tuple(
        date(2026, 8, day) for day in (18, 19, 20, 21, 24)
    )
    settlement_dir = tmp_path / "settlement"
    settlement_code = main(
        [
            "settle",
            "--screen-artifact",
            str(screen_path),
            "--outcome-cutoff",
            outcome_dates[-1].isoformat(),
            "--output-dir",
            str(settlement_dir),
        ],
        settlement_input_loader=lambda *_: _settlement_inputs(
            signal_date, outcome_dates
        ),
    )

    assert settlement_code == 0
    assert "CASE_ANALYSIS_ONLY / NO-TRADE" in capsys.readouterr().out
    assert len(tuple(settlement_dir.glob("settlement_*.json"))) == 1
    assert screen_path.read_bytes() == before


def _empty_freeze():
    policy = SelectionPolicy()
    profiles = build_structure_stop_profiles()
    return freeze_structure_stop_profiles(
        profiles=profiles,
        training_identities=tuple(
            f"research-{index:02d}" for index in range(8)
        ),
        metrics=(),
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=structure_stop_profile_hash(profiles),
        risk_coverage_complete=False,
    )


def test_forward_screen_uses_two_confirmed_plan_dates_without_outcomes() -> None:
    """Catches weekday inference or outcome evaluation during screening."""
    signal_date = date(2026, 8, 17)
    observed_plan_dates = []

    def loader(day: date, plan_dates: tuple[date, date]) -> CaseReviewInputs:
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
    screen = build_structure_stop_forward_screen(
        signal_date,
        _empty_freeze(),
        input_loader=loader,
        calendar_status=lambda day: statuses.get(day, False),
    )

    assert observed_plan_dates == [(date(2026, 8, 18), date(2026, 8, 19))]
    assert screen.candidates == ()
    payload = structure_stop_screen_payload(screen)
    assert payload["retrospective"] is False
    assert payload["metrics"] == {"selected": 0}
    assert "outcomes" not in payload

    with pytest.raises(ValueError, match="not confirmed locally"):
        build_structure_stop_forward_screen(
            signal_date,
            _empty_freeze(),
            input_loader=loader,
            calendar_status=lambda _day: None,
        )


def test_forward_screen_rejects_future_price_bars() -> None:
    """Catches settlement data leaking into signal-time ranking."""
    signal_date = date(2026, 8, 17)
    future = BuyPointBar(
        date(2026, 8, 18),
        Decimal("10"),
        Decimal("11"),
        Decimal("9"),
        Decimal("10"),
        Decimal("0"),
        Decimal("100000"),
    )
    inputs = CaseReviewInputs(
        (signal_date, date(2026, 8, 18), date(2026, 8, 19)),
        {"600001": (future,)},
        (),
        (),
        {signal_date: ReferenceCoverage(signal_date, True, True, False)},
        {signal_date: MarketSnapshot(3, 60.0, 1.0, True)},
        {signal_date: frozenset()},
        {signal_date: True},
    )

    with pytest.raises(ValueError, match="screen input contains future price bars"):
        build_structure_stop_forward_screen(
            signal_date,
            _empty_freeze(),
            input_loader=lambda *_: inputs,
            calendar_status=lambda _day: True,
        )


def _qualified_freeze():
    policy = SelectionPolicy()
    profiles = build_structure_stop_profiles()
    metric = StructureStopMetrics(
        profiles[0].profile_id,
        "ALL",
        12,
        10,
        10,
        6,
        3,
        Decimal("0.01"),
        Decimal("0.01"),
        Decimal("0.60"),
        Decimal("0.30"),
        Decimal("0.06"),
        Decimal("0.02"),
        True,
        (),
    )
    return freeze_structure_stop_profiles(
        profiles=profiles,
        training_identities=tuple(
            f"research-{index:02d}" for index in range(8)
        ),
        metrics=(metric,),
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=structure_stop_profile_hash(profiles),
        risk_coverage_complete=False,
    )


def _screen_candidate(
    code: str,
    signal_date: date,
    profile_index: int = 0,
) -> StructureStopCandidate:
    profile = build_structure_stop_profiles()[profile_index]
    setup = DetectedSetup(
        code,
        SetupType.PRE_BREAKOUT,
        signal_date,
        signal_date - timedelta(days=20),
        Decimal("10.00"),
        Decimal("9.93"),
        Decimal("0.80"),
        ("FORMAL_FIXTURE",),
        {},
    )
    hit = StructureStopBaselineHit(
        code,
        signal_date,
        setup,
        "ALLOW",
        "S1",
        ("RISK_DISTANCE_OUT_OF_RANGE",),
    )
    anchor = StructureStopAnchor(
        profile,
        code,
        signal_date,
        Decimal("9.80"),
        Decimal("9.76"),
        (),
    )
    plan = PricePlan(
        f"structure-{code}-{profile.profile_id}",
        code,
        setup.setup_type,
        signal_date,
        Decimal("10.00"),
        Decimal("10.01"),
        Decimal("9.76"),
        Decimal("10.51"),
        Decimal("0.25"),
        Decimal("2"),
        100,
        signal_date + timedelta(days=2),
    )
    return StructureStopCandidate(
        hit,
        profile,
        anchor,
        plan,
        Decimal("200000"),
        Decimal("1.00"),
    )


def test_forward_screen_selects_only_frozen_primary_top_five(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches diagnostic/profile leakage or nondeterministic Top-5 padding."""
    signal_date = date(2026, 8, 17)
    primary = tuple(
        _screen_candidate(f"60000{index}", signal_date)
        for index in range(1, 7)
    )
    not_frozen = _screen_candidate("600007", signal_date, profile_index=1)
    replay = StructureStopReplay(
        (signal_date,),
        (),
        tuple(value.hit for value in (*primary, not_frozen)),
        (*primary, not_frozen),
        (
            StructureStopDiagnostic(
                "600008",
                signal_date,
                "MARKET",
                "INDEX_AND_BREADTH_WEAK",
                "RISK_DISTANCE_OUT_OF_RANGE",
            ),
        ),
        (),
    )
    monkeypatch.setattr(
        "scripts.analysis.review_buy_point_structure_stops."
        "replay_structure_stop_shadows",
        lambda **_kwargs: replay,
    )
    inputs = CaseReviewInputs(
        (signal_date, date(2026, 8, 18), date(2026, 8, 19)),
        {},
        (),
        (),
        {signal_date: ReferenceCoverage(signal_date, True, True, True)},
        {signal_date: MarketSnapshot(3, 60.0, 1.0, True)},
        {signal_date: frozenset()},
        {signal_date: True},
    )

    screen = build_structure_stop_forward_screen(
        signal_date,
        _qualified_freeze(),
        input_loader=lambda *_: inputs,
        calendar_status=lambda _day: True,
    )
    payload = structure_stop_screen_payload(screen)

    assert [value["code"] for value in payload["candidates"]] == [
        "600001",
        "600002",
        "600003",
        "600004",
        "600005",
    ]
    assert {value["profile_rank"] for value in payload["candidates"]} == {1}
    assert payload["freeze_hash"] == _qualified_freeze().freeze_hash
    assert payload["formal_rule_version"] == SelectionPolicy().rule_version
    assert payload["risk_coverage_complete"] is True
    assert all(
        value["executable_shares"] == 0
        and value["maximum_shares"] == 0
        for value in payload["candidates"]
    )
    assert "outcomes" not in payload


def test_forward_screen_rejects_retrospective_date_or_forged_freeze() -> None:
    """Catches reuse of observed dates or an edited frozen profile matrix."""
    freeze = _qualified_freeze()
    inputs = _empty_inputs(
        _confirmed_sessions(),
        _confirmed_sessions()[-10:-5],
    )
    with pytest.raises(ValueError, match="after retrospective windows"):
        build_structure_stop_forward_screen(
            date(2026, 8, 7),
            freeze,
            input_loader=lambda *_: inputs,
            calendar_status=lambda _day: True,
        )

    forged_profile = replace(
        freeze.profiles[0], profile_id="STRUCTURE_STOP:FORGED"
    )
    forged = replace(freeze, profiles=(forged_profile,))
    with pytest.raises(ValueError, match="structure stop freeze"):
        build_structure_stop_forward_screen(
            date(2026, 8, 17),
            forged,
            input_loader=lambda *_: inputs,
            calendar_status=lambda _day: True,
        )


def _nonempty_screen(signal_date: date) -> StructureStopForwardScreen:
    policy = SelectionPolicy()
    profiles = build_structure_stop_profiles()
    freeze = _qualified_freeze()
    return StructureStopForwardScreen(
        signal_date=signal_date,
        input_fingerprint="screen-input-fingerprint",
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=structure_stop_profile_hash(profiles),
        freeze_hash=freeze.freeze_hash,
        candidates=(
            StructureStopScreenCandidate(
                _screen_candidate("600001", signal_date),
                1,
            ),
        ),
        risk_coverage_complete=False,
    )


def _settlement_inputs(
    signal_date: date,
    outcome_dates: tuple[date, ...],
) -> CaseReviewInputs:
    return CaseReviewInputs(
        (signal_date, *outcome_dates),
        {"600001": (), "600999": ()},
        (),
        (),
        {},
        {},
        {},
        {},
    )


def test_forward_settlement_preserves_screen_membership_and_bytes(
    tmp_path: Path,
) -> None:
    """Catches evaluating the universe or rewriting the parent screen."""
    signal_date = date(2026, 8, 17)
    outcome_dates = tuple(
        date(2026, 8, day) for day in (18, 19, 20, 21, 24)
    )
    screen = _nonempty_screen(signal_date)
    screen_path = write_structure_stop_forward_screen(screen, tmp_path)[0]
    before = screen_path.read_bytes()
    observed = []

    def loader(day: date, cutoff: date) -> CaseReviewInputs:
        observed.append((day, cutoff))
        return _settlement_inputs(signal_date, outcome_dates)

    settlement = build_structure_stop_forward_settlement(
        screen_path,
        outcome_dates[-1],
        input_loader=loader,
    )
    payload = structure_stop_settlement_payload(settlement)

    assert observed == [(signal_date, outcome_dates[-1])]
    assert settlement.parent_screen_identity == structure_stop_screen_identity(
        screen
    )
    assert settlement.outcome_dates == outcome_dates
    assert [value["code"] for value in payload["candidates"]] == ["600001"]
    assert [value["profile_rank"] for value in payload["candidates"]] == [1]
    assert [value["code"] for value in payload["outcomes"]] == ["600001"]
    assert screen_path.read_bytes() == before

    settlement_paths = write_structure_stop_forward_settlement(
        settlement, tmp_path
    )
    assert settlement_paths[0] != screen_path
    assert screen_path.read_bytes() == before


@pytest.mark.parametrize("session_count", (4, 6))
def test_forward_settlement_requires_exactly_five_sessions(
    tmp_path: Path,
    session_count: int,
) -> None:
    """Catches early or overlong outcome windows."""
    signal_date = date(2026, 8, 17)
    all_dates = tuple(
        date(2026, 8, day) for day in (18, 19, 20, 21, 24, 25)
    )
    outcome_dates = all_dates[:session_count]
    screen_path = write_structure_stop_forward_screen(
        _nonempty_screen(signal_date), tmp_path
    )[0]

    with pytest.raises(ValueError, match="exactly five completed outcome sessions"):
        build_structure_stop_forward_settlement(
            screen_path,
            outcome_dates[-1],
            input_loader=lambda *_: _settlement_inputs(
                signal_date, outcome_dates
            ),
        )


def test_forward_settlement_rejects_missing_outcome_or_changed_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches result loss or settlement against edited freeze lineage."""
    signal_date = date(2026, 8, 17)
    outcome_dates = tuple(
        date(2026, 8, day) for day in (18, 19, 20, 21, 24)
    )
    screen_path = write_structure_stop_forward_screen(
        _nonempty_screen(signal_date), tmp_path
    )[0]
    monkeypatch.setattr(
        "scripts.analysis.review_buy_point_structure_stops."
        "evaluate_structure_stop_outcomes",
        lambda *_args, **_kwargs: (),
    )
    with pytest.raises(ValueError, match="candidate and outcome membership"):
        build_structure_stop_forward_settlement(
            screen_path,
            outcome_dates[-1],
            input_loader=lambda *_: _settlement_inputs(
                signal_date, outcome_dates
            ),
        )

    payload = json.loads(screen_path.read_text(encoding="utf-8"))
    payload["freeze_hash"] = "0" * 64
    screen_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="screen artifact is invalid"):
        build_structure_stop_forward_settlement(
            screen_path,
            outcome_dates[-1],
            input_loader=lambda *_: _settlement_inputs(
                signal_date, outcome_dates
            ),
        )
