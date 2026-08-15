from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path

import pytest

from scripts.analysis.review_buy_point_case import CaseReviewInputs
from scripts.analysis.review_buy_point_threshold_shadows import (
    build_freeze_from_artifacts,
    build_research_review,
    build_test_review,
    build_parser,
    case_input_fingerprint,
    load_v5_recall_lineage,
    main,
)
from stock_ai.buy_point_selection.case_report import revision_identity
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ExactRecallComparison,
)
from stock_ai.buy_point_selection.threshold_shadow_report import (
    ThresholdWindowReview,
    threshold_shadow_payload,
    write_threshold_freeze,
)
from stock_ai.buy_point_selection.threshold_shadow_research import (
    ThresholdShadowReplay,
    build_threshold_profiles,
    profile_matrix_hash,
)
from stock_ai.buy_point_selection.models import SelectionPolicy
from stock_ai.buy_point_selection.validation import policy_hash
from stock_ai.buy_point_selection.models import BuyPointBar, MarketSnapshot
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    SectorMembership,
)


SIGNAL_DATES = tuple(date(2026, 7, day) for day in range(20, 25))
CUTOFF = date(2026, 7, 31)


def _empty_research_payload(
    signal_dates: tuple[date, ...], cutoff: date, identity_suffix: str
) -> dict[str, object]:
    profiles = build_threshold_profiles()
    policy = SelectionPolicy()
    review = ThresholdWindowReview(
        "research",
        signal_dates,
        cutoff,
        f"v5-{identity_suffix}",
        f"input-{identity_suffix}",
        policy.rule_version,
        policy_hash(policy),
        profile_matrix_hash(profiles),
        None,
        profiles,
        ThresholdShadowReplay(signal_dates, (), (), (), ()),
        (),
        (),
        (),
        (),
        (),
        (),
        ExactRecallComparison(0, 0, 0, 0, 0),
        False,
        False,
    )
    return threshold_shadow_payload(review)


def _write_payload(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _v5_payload() -> dict[str, object]:
    return {
        "schema": "buy-point-case-review-v5",
        "status": "CASE_ANALYSIS_ONLY",
        "trade_permission": "NO-TRADE",
        "case_identity": "v5-case",
        "signal_dates": [value.isoformat() for value in SIGNAL_DATES],
        "outcome_cutoff": CUTOFF.isoformat(),
        "risk_coverage_complete": False,
        "daily_recall_winners": [
            {
                "signal_date": "2026-07-20",
                "code": "600001",
                "executable_shares": 0,
            }
        ],
        "daily_recall_metrics": {
            "winner_pairs": 1,
            "by_date": [
                {"signal_date": value.isoformat(), "winner_pairs": 1 if index == 0 else 0}
                for index, value in enumerate(SIGNAL_DATES)
            ],
        },
    }


def test_parser_exposes_research_freeze_and_test_stages() -> None:
    """Catches a stage silently omitting its immutable lineage inputs."""
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
    freeze = parser.parse_args(
        [
            "freeze",
            "--research-artifact",
            "first.json",
            "--research-artifact",
            "second.json",
        ]
    )
    test = parser.parse_args(
        [
            "test",
            "--signal-start",
            "2026-08-03",
            "--signal-end",
            "2026-08-07",
            "--outcome-cutoff",
            "2026-08-14",
            "--v5-case",
            "case.json",
            "--freeze-artifact",
            "freeze.json",
        ]
    )

    assert research.stage == "research"
    assert freeze.research_artifact == ["first.json", "second.json"]
    assert test.freeze_artifact == "freeze.json"


def test_v5_lineage_requires_exact_reconciled_zero_share_rows(tmp_path: Path) -> None:
    """Catches wrong-window or executable hindsight rows entering research."""
    path = tmp_path / "case.json"
    path.write_text(json.dumps(_v5_payload()), encoding="utf-8")

    lineage = load_v5_recall_lineage(path, SIGNAL_DATES, CUTOFF)

    assert lineage.case_identity == "v5-case"
    assert lineage.winner_keys == frozenset({(date(2026, 7, 20), "600001")})
    assert not lineage.risk_coverage_complete

    payload = _v5_payload()
    payload["daily_recall_winners"][0]["executable_shares"] = 100
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="zero-share"):
        load_v5_recall_lineage(path, SIGNAL_DATES, CUTOFF)


def test_v5_lineage_prefers_a_valid_revision_identity(tmp_path: Path) -> None:
    """Catches downstream research grouping repaired revisions together."""
    payload = _v5_payload()
    payload["revision_identity"] = revision_identity(payload)
    path = _write_payload(tmp_path / "case.json", payload)

    lineage = load_v5_recall_lineage(path, SIGNAL_DATES, CUTOFF)

    assert lineage.case_identity == payload["revision_identity"]


def test_v5_lineage_rejects_tampered_revision_content(tmp_path: Path) -> None:
    """Catches content changes being accepted under a sealed revision ID."""
    payload = _v5_payload()
    payload["revision_identity"] = revision_identity(payload)
    payload["risk_coverage_complete"] = True
    path = _write_payload(tmp_path / "case.json", payload)

    with pytest.raises(ValueError, match="revision identity mismatch"):
        load_v5_recall_lineage(path, SIGNAL_DATES, CUTOFF)


def test_v5_lineage_rejects_malformed_revision_identity(tmp_path: Path) -> None:
    """Catches invalid revision IDs entering downstream lineage."""
    payload = _v5_payload()
    payload["revision_identity"] = "ABC123"
    path = _write_payload(tmp_path / "case.json", payload)

    with pytest.raises(ValueError, match="revision identity malformed"):
        load_v5_recall_lineage(path, SIGNAL_DATES, CUTOFF)


def test_case_input_fingerprint_is_order_independent_and_content_sensitive() -> None:
    """Catches point-in-time data changes being hidden behind one research ID."""
    bar = BuyPointBar(
        SIGNAL_DATES[0],
        Decimal("10"),
        Decimal("10.1"),
        Decimal("9.9"),
        Decimal("10"),
        Decimal("0"),
        Decimal("200000"),
    )
    inputs = CaseReviewInputs(
        trading_dates=tuple(reversed(SIGNAL_DATES)),
        bars_by_code={"600002": (bar,), "600001": (bar,)},
        memberships=(),
        risk_flags=(),
        coverage_by_date={
            value: ReferenceCoverage(value, True, True, False)
            for value in reversed(SIGNAL_DATES)
        },
        market_snapshots={
            value: MarketSnapshot(3, 60.0, 1.1, True)
            for value in reversed(SIGNAL_DATES)
        },
        holding_codes_by_date={value: frozenset() for value in SIGNAL_DATES},
        holdings_complete_by_date={value: True for value in SIGNAL_DATES},
    )
    reordered = CaseReviewInputs(
        **{
            **inputs.__dict__,
            "trading_dates": tuple(sorted(inputs.trading_dates)),
            "bars_by_code": dict(reversed(tuple(inputs.bars_by_code.items()))),
        }
    )
    changed = CaseReviewInputs(
        **{
            **inputs.__dict__,
            "bars_by_code": {
                **inputs.bars_by_code,
                "600001": (BuyPointBar(**{**bar.__dict__, "close": Decimal("10.01")}),),
            },
        }
    )

    assert case_input_fingerprint(reordered) == case_input_fingerprint(inputs)
    assert case_input_fingerprint(changed) != case_input_fingerprint(inputs)


def test_research_runtime_builds_all_profiles_from_one_read_only_input_load(
    tmp_path: Path,
) -> None:
    """Catches research reading inputs repeatedly or narrowing to hindsight winners."""
    signal_dates = tuple(date(2026, 7, day) for day in range(20, 25))
    outcome_dates = tuple(date(2026, 7, day) for day in range(25, 30))
    history_start = signal_dates[0].toordinal() - 59
    bars = tuple(
        BuyPointBar(
            date.fromordinal(history_start + index),
            Decimal("10"),
            Decimal("10.1"),
            Decimal("9.9"),
            Decimal("10"),
            Decimal("0"),
            Decimal("200000"),
        )
        for index in range(70)
    )
    inputs = CaseReviewInputs(
        trading_dates=(*signal_dates, *outcome_dates),
        bars_by_code={"600001": bars},
        memberships=(
            SectorMembership(
                "600001", "S1", "测试行业", signal_dates[0], None, "fixture"
            ),
        ),
        risk_flags=(),
        coverage_by_date={
            value: ReferenceCoverage(value, True, True, False)
            for value in signal_dates
        },
        market_snapshots={
            value: MarketSnapshot(3, 60.0, 1.1, True)
            for value in signal_dates
        },
        holding_codes_by_date={value: frozenset() for value in signal_dates},
        holdings_complete_by_date={value: True for value in signal_dates},
    )
    payload = _v5_payload()
    payload["daily_recall_winners"] = []
    payload["daily_recall_metrics"] = {
        "winner_pairs": 0,
        "by_date": [
            {"signal_date": value.isoformat(), "winner_pairs": 0}
            for value in signal_dates
        ],
    }
    path = tmp_path / "case.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    calls = []

    def loader(start: date, end: date, cutoff: date) -> CaseReviewInputs:
        calls.append((start, end, cutoff))
        return inputs

    review = build_research_review(
        signal_dates[0],
        signal_dates[-1],
        CUTOFF,
        path,
        input_loader=loader,
    )

    assert calls == [(signal_dates[0], signal_dates[-1], CUTOFF)]
    assert review.stage == "research"
    assert len(review.profiles) == 48
    assert review.replay.signal_dates == signal_dates
    assert not review.risk_coverage_complete
    assert review.selected_candidates == ()


def test_freeze_aggregates_exact_two_research_windows_and_can_be_empty(
    tmp_path: Path,
) -> None:
    """Catches freeze accepting wrong lineage or inventing a fallback profile."""
    first = _write_payload(
        tmp_path / "first.json",
        _empty_research_payload(SIGNAL_DATES, CUTOFF, "first"),
    )
    second_dates = tuple(date(2026, 7, day) for day in range(27, 32))
    second = _write_payload(
        tmp_path / "second.json",
        _empty_research_payload(second_dates, date(2026, 8, 7), "second"),
    )

    freeze = build_freeze_from_artifacts((first, second))

    assert freeze.empty
    assert freeze.profiles == ()
    assert len(freeze.training_identities) == 2
    assert not freeze.promotion_eligible

    duplicated = _write_payload(
        tmp_path / "duplicated.json",
        _empty_research_payload(SIGNAL_DATES, CUTOFF, "first"),
    )
    with pytest.raises(ValueError, match="distinct|windows"):
        build_freeze_from_artifacts((first, duplicated))


def test_freeze_rejects_profile_metrics_that_do_not_reconcile(
    tmp_path: Path,
) -> None:
    """Catches edited summary metrics qualifying without matching raw rows."""
    first_payload = _empty_research_payload(SIGNAL_DATES, CUTOFF, "first")
    first_payload["profile_metrics"] = [
        {
            "profile_id": first_payload["profiles"][0]["profile_id"],
            "candidate_count": 1,
            "triggered": 0,
            "resolved": 0,
            "positive_net": 0,
            "stop_first": 0,
            "mean_net_return": None,
            "median_net_return": None,
            "positive_net_rate": None,
            "stop_first_rate": None,
            "mean_mfe": None,
            "mean_mae": None,
            "qualifies": False,
            "qualification_reasons": [
                "MINIMUM_RESOLVED_TRIGGERED",
                "MEAN_NET_RETURN_NOT_POSITIVE",
                "POSITIVE_NET_RATE_BELOW_HALF",
                "STOP_FIRST_RATE_ABOVE_40_PERCENT",
            ],
        }
    ]
    first = _write_payload(tmp_path / "first.json", first_payload)
    second_dates = tuple(date(2026, 7, day) for day in range(27, 32))
    second = _write_payload(
        tmp_path / "second.json",
        _empty_research_payload(second_dates, date(2026, 8, 7), "second"),
    )

    with pytest.raises(ValueError, match="metrics do not reconcile"):
        build_freeze_from_artifacts((first, second))


def test_test_runtime_consumes_empty_freeze_without_inventing_candidates(
    tmp_path: Path,
) -> None:
    """Catches holdout bypassing an empty freeze to force daily picks."""
    first = _write_payload(
        tmp_path / "first.json",
        _empty_research_payload(SIGNAL_DATES, CUTOFF, "first"),
    )
    second_dates = tuple(date(2026, 7, day) for day in range(27, 32))
    second = _write_payload(
        tmp_path / "second.json",
        _empty_research_payload(second_dates, date(2026, 8, 7), "second"),
    )
    freeze = build_freeze_from_artifacts((first, second))
    freeze_path, _ = write_threshold_freeze(freeze, tmp_path)
    signal_dates = tuple(date(2026, 8, day) for day in range(3, 8))
    outcome_dates = tuple(date(2026, 8, day) for day in range(10, 15))
    history_start = signal_dates[0].toordinal() - 59
    bars = tuple(
        BuyPointBar(
            date.fromordinal(history_start + index),
            Decimal("10"),
            Decimal("10.1"),
            Decimal("9.9"),
            Decimal("10"),
            Decimal("0"),
            Decimal("200000"),
        )
        for index in range(71)
    )
    inputs = CaseReviewInputs(
        trading_dates=(*signal_dates, *outcome_dates),
        bars_by_code={"600001": bars},
        memberships=(
            SectorMembership(
                "600001", "S1", "测试行业", signal_dates[0], None, "fixture"
            ),
        ),
        risk_flags=(),
        coverage_by_date={
            value: ReferenceCoverage(value, True, True, False)
            for value in signal_dates
        },
        market_snapshots={
            value: MarketSnapshot(3, 60.0, 1.1, True)
            for value in signal_dates
        },
        holding_codes_by_date={value: frozenset() for value in signal_dates},
        holdings_complete_by_date={value: True for value in signal_dates},
    )
    v5_payload = _v5_payload()
    v5_payload["signal_dates"] = [value.isoformat() for value in signal_dates]
    v5_payload["outcome_cutoff"] = "2026-08-14"
    v5_payload["daily_recall_winners"] = []
    v5_payload["daily_recall_metrics"] = {
        "winner_pairs": 0,
        "by_date": [
            {"signal_date": value.isoformat(), "winner_pairs": 0}
            for value in signal_dates
        ],
    }
    v5_path = _write_payload(tmp_path / "test-v5.json", v5_payload)
    calls = []

    def loader(start: date, end: date, cutoff: date) -> CaseReviewInputs:
        calls.append((start, end, cutoff))
        return inputs

    review = build_test_review(
        signal_dates[0],
        signal_dates[-1],
        date(2026, 8, 14),
        v5_path,
        freeze_path,
        input_loader=loader,
    )

    assert calls == [(signal_dates[0], signal_dates[-1], date(2026, 8, 14))]
    assert review.stage == "test"
    assert review.freeze_hash == freeze.freeze_hash
    assert review.profiles == ()
    assert review.selected_candidates == ()
    assert review.selected_outcomes == ()
    assert review.test_consumed

    with pytest.raises(ValueError, match="exact August holdout"):
        build_test_review(
            date(2026, 8, 4),
            signal_dates[-1],
            date(2026, 8, 14),
            v5_path,
            freeze_path,
            input_loader=loader,
        )


def test_freeze_cli_writes_one_immutable_artifact_pair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catches the parser existing without a runnable freeze workflow."""
    first = _write_payload(
        tmp_path / "first.json",
        _empty_research_payload(SIGNAL_DATES, CUTOFF, "first"),
    )
    second_dates = tuple(date(2026, 7, day) for day in range(27, 32))
    second = _write_payload(
        tmp_path / "second.json",
        _empty_research_payload(second_dates, date(2026, 8, 7), "second"),
    )
    output_dir = tmp_path / "output"

    exit_code = main(
        [
            "freeze",
            "--research-artifact",
            str(first),
            "--research-artifact",
            str(second),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert len(tuple(output_dir.glob("freeze-*.json"))) == 1
    assert len(tuple(output_dir.glob("freeze-*.md"))) == 1
    assert "CASE_ANALYSIS_ONLY / NO-TRADE" in capsys.readouterr().out
