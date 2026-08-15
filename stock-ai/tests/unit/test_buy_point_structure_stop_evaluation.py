from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.case_review import CaseOutcome
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    SetupType,
)
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.structure_stop_evaluation import (
    StructureStopMetrics,
    StructureStopOutcome,
    aggregate_structure_stop_metrics,
    evaluate_structure_stop_outcomes,
    freeze_structure_stop_profiles,
    select_frozen_structure_stop_candidates,
    validate_structure_stop_freeze,
)
from stock_ai.buy_point_selection.structure_stop_shadow import (
    StructureStopAnchor,
    StructureStopBaselineHit,
    StructureStopCandidate,
    StructureStopDiagnostic,
    build_structure_stop_profiles,
    structure_stop_profile_hash,
)


SIGNAL = date(2026, 7, 20)


def _candidate(
    *,
    code: str = "600001",
    profile_index: int = 0,
    setup_type: SetupType = SetupType.PRE_BREAKOUT,
    quality: str = "0.80",
    buffer: str = "2.00",
    amount: str = "200000",
) -> StructureStopCandidate:
    profile = build_structure_stop_profiles()[profile_index]
    setup = DetectedSetup(
        code,
        setup_type,
        SIGNAL,
        SIGNAL - timedelta(days=20),
        Decimal("10.00"),
        Decimal("9.93"),
        Decimal(quality),
        ("FORMAL_FIXTURE",),
        {},
    )
    hit = StructureStopBaselineHit(
        code,
        SIGNAL,
        setup,
        "ALLOW",
        "S1",
        ("RISK_DISTANCE_OUT_OF_RANGE",),
    )
    anchor = StructureStopAnchor(
        profile,
        code,
        SIGNAL,
        Decimal("9.80"),
        Decimal("9.80"),
        (),
    )
    plan = PricePlan(
        f"structure-{code}-{profile.profile_id}",
        code,
        setup_type,
        SIGNAL,
        Decimal("10.00"),
        Decimal("10.10"),
        Decimal("9.80"),
        Decimal("10.70"),
        Decimal("0.30"),
        Decimal("2"),
        100,
        SIGNAL + timedelta(days=2),
    )
    return StructureStopCandidate(
        hit,
        profile,
        anchor,
        plan,
        Decimal(amount),
        Decimal(buffer),
    )


def _bar(
    offset: int,
    *,
    open_: str,
    high: str,
    low: str,
    close: str,
) -> BuyPointBar:
    return BuyPointBar(
        SIGNAL + timedelta(days=offset),
        Decimal(open_),
        Decimal(high),
        Decimal(low),
        Decimal(close),
        Decimal("0"),
        Decimal("200000"),
    )


def _time_exit_bars(close: str) -> tuple[BuyPointBar, ...]:
    return (
        _bar(1, open_="10.10", high="10.20", low="9.95", close="10.10"),
        _bar(2, open_="10.10", high="10.30", low="9.95", close="10.15"),
        _bar(3, open_="10.15", high="10.30", low="10.00", close="10.20"),
        _bar(4, open_="10.20", high="10.30", low="10.00", close="10.20"),
        _bar(
            5,
            open_="10.20",
            high=max(Decimal("10.30"), Decimal(close)).to_eng_string(),
            low="10.00",
            close=close,
        ),
    )


@pytest.mark.parametrize(
    (
        "bars",
        "cutoff_offset",
        "status",
        "triggered",
        "stop_first",
        "net_sign",
    ),
    (
        (
            (_bar(1, open_="10.10", high="10.20", low="9.95", close="10.10"),),
            1,
            "PENDING",
            True,
            False,
            None,
        ),
        (
            (
                _bar(1, open_="10.00", high="10.05", low="9.95", close="10.00"),
                _bar(2, open_="10.00", high="10.05", low="9.95", close="10.00"),
            ),
            2,
            "EXPIRED",
            False,
            False,
            None,
        ),
        (
            (
                _bar(1, open_="10.10", high="10.20", low="9.95", close="10.10"),
                _bar(2, open_="10.20", high="10.80", low="10.00", close="10.70"),
            ),
            2,
            "CLOSED",
            True,
            False,
            1,
        ),
        (
            (_bar(1, open_="10.10", high="10.80", low="9.70", close="10.40"),),
            1,
            "CLOSED",
            True,
            True,
            -1,
        ),
        (_time_exit_bars("10.50"), 5, "CLOSED", True, False, 1),
        (_time_exit_bars("10.00"), 5, "CLOSED", True, False, -1),
    ),
)
def test_outcome_adapter_preserves_bounded_execution_paths(
    bars: tuple[BuyPointBar, ...],
    cutoff_offset: int,
    status: str,
    triggered: bool,
    stop_first: bool,
    net_sign: int | None,
) -> None:
    """Catches the wrapper changing execution semantics or reading past cutoff."""
    candidate = _candidate()
    future_crash = _bar(
        6, open_="1.00", high="1.00", low="0.10", close="0.10"
    )

    row = evaluate_structure_stop_outcomes(
        (candidate,),
        {candidate.hit.code: (*bars, future_crash)},
        outcome_cutoff=SIGNAL + timedelta(days=cutoff_offset),
    )[0]

    assert row.profile_id == candidate.profile.profile_id
    assert row.setup_type == SetupType.PRE_BREAKOUT.value
    assert row.outcome.status == status
    assert (row.outcome.trigger_date is not None) is triggered
    assert row.outcome.stop_first is stop_first
    if net_sign is None:
        assert row.outcome.net_return is None
    elif net_sign > 0:
        assert row.outcome.net_return is not None
        assert row.outcome.net_return > 0
    else:
        assert row.outcome.net_return is not None
        assert row.outcome.net_return < 0
    assert row.outcome.tier == "STRUCTURE_STOP_SHADOW"
    assert row.executable_shares == 0


def test_outcome_adapter_keeps_case_evaluator_costs() -> None:
    """Catches the stop study silently switching to zero or custom costs."""
    candidate = _candidate()
    bars = (
        _bar(1, open_="10.10", high="10.20", low="9.95", close="10.10"),
        _bar(2, open_="10.20", high="10.80", low="10.00", close="10.70"),
    )

    row = evaluate_structure_stop_outcomes(
        (candidate,),
        {candidate.hit.code: bars},
        outcome_cutoff=SIGNAL + timedelta(days=2),
    )[0]

    assert row.outcome.net_return == Decimal(
        "0.04611280400783456855739608862"
    )


def test_diagnostic_rows_are_not_evaluator_inputs() -> None:
    """Catches diagnostic combined failures leaking into outcome metrics."""
    diagnostic = StructureStopDiagnostic(
        "600001",
        SIGNAL,
        "MARKET",
        "INDEX_AND_BREADTH_WEAK",
        "RISK_DISTANCE_OUT_OF_RANGE",
    )

    with pytest.raises(ValueError, match="structure stop candidate"):
        evaluate_structure_stop_outcomes(
            (diagnostic,),
            {},
            outcome_cutoff=SIGNAL + timedelta(days=5),
        )


@pytest.mark.parametrize("layer", ("candidate", "hit", "anchor"))
def test_outcome_adapter_rejects_nonzero_research_shares(layer: str) -> None:
    """Catches executable position state entering retrospective evaluation."""
    candidate = _candidate()
    if layer == "candidate":
        candidate = replace(candidate, executable_shares=100)
    elif layer == "hit":
        candidate = replace(
            candidate,
            hit=replace(candidate.hit, executable_shares=100),
        )
    else:
        candidate = replace(
            candidate,
            anchor=replace(candidate.anchor, executable_shares=100),
        )

    with pytest.raises(ValueError, match="zero-share"):
        evaluate_structure_stop_outcomes(
            (candidate,),
            {candidate.hit.code: _time_exit_bars("10.20")},
            outcome_cutoff=SIGNAL + timedelta(days=5),
        )


@pytest.mark.parametrize("mutation", ("permission", "profile"))
def test_outcome_adapter_rejects_non_research_identity(mutation: str) -> None:
    """Catches executable permission or a forged profile entering metrics."""
    candidate = _candidate()
    if mutation == "permission":
        candidate = replace(candidate, trade_permission="ALLOW")
        message = "zero-share research"
    else:
        candidate = replace(
            candidate,
            profile=replace(candidate.profile, profile_id="FORGED"),
        )
        message = "unsupported structure stop profile"

    with pytest.raises(ValueError, match=message):
        evaluate_structure_stop_outcomes(
            (candidate,),
            {candidate.hit.code: _time_exit_bars("10.20")},
            outcome_cutoff=SIGNAL + timedelta(days=5),
        )


def _resolved_outcome(
    profile_id: str,
    index: int,
    net_return: str,
    *,
    setup_type: SetupType = SetupType.PRE_BREAKOUT,
    stop_first: bool = False,
) -> StructureStopOutcome:
    code = f"60{index:04d}"
    return StructureStopOutcome(
        profile_id,
        setup_type.value,
        code,
        SIGNAL,
        CaseOutcome(
            code,
            SIGNAL,
            "STRUCTURE_STOP_SHADOW",
            "CLOSED",
            Decimal("0.04"),
            Decimal("0.02"),
            SIGNAL + timedelta(days=1),
            Decimal("10"),
            Decimal(net_return),
            Decimal(net_return),
            stop_first,
            False,
            f"structure-{index}",
        ),
    )


def test_metrics_include_all_and_setup_rows_at_inclusive_boundaries() -> None:
    """Catches setup grouping or inclusive qualification edges drifting."""
    profile_id = build_structure_stop_profiles()[0].profile_id
    outcomes = tuple(
        _resolved_outcome(
            profile_id,
            index,
            "0.02" if index < 5 else "-0.01",
            stop_first=index < 4,
        )
        for index in range(10)
    )

    metrics = aggregate_structure_stop_metrics(
        ((profile_id, SetupType.PRE_BREAKOUT.value),) * 10,
        outcomes,
    )

    assert tuple(value.setup_type for value in metrics) == (
        "ALL",
        SetupType.PRE_BREAKOUT.value,
    )
    overall = metrics[0]
    assert overall.candidate_count == 10
    assert overall.triggered == overall.resolved == 10
    assert overall.mean_net_return == Decimal("0.005")
    assert overall.median_net_return == Decimal("0.005")
    assert overall.positive_net_rate == Decimal("0.5")
    assert overall.stop_first_rate == Decimal("0.4")
    assert overall.qualifies
    assert overall.qualification_reasons == ()


@pytest.mark.parametrize(
    ("outcomes", "reason"),
    (
        (
            tuple(
                _resolved_outcome("PROFILE", index, "0.01")
                for index in range(9)
            ),
            "MINIMUM_RESOLVED_TRIGGERED",
        ),
        (
            tuple(
                _resolved_outcome(
                    "PROFILE", index, "0.01" if index < 5 else "-0.01"
                )
                for index in range(10)
            ),
            "MEAN_NET_RETURN_NOT_POSITIVE",
        ),
        (
            tuple(
                _resolved_outcome(
                    "PROFILE", index, "0.02" if index < 49 else "-0.001"
                )
                for index in range(100)
            ),
            "POSITIVE_NET_RATE_BELOW_HALF",
        ),
        (
            tuple(
                _resolved_outcome(
                    "PROFILE", index, "0.01", stop_first=index < 41
                )
                for index in range(100)
            ),
            "STOP_FIRST_RATE_ABOVE_40_PERCENT",
        ),
    ),
)
def test_metric_failures_are_explicit_at_the_immediate_wrong_side(
    outcomes: tuple[StructureStopOutcome, ...],
    reason: str,
) -> None:
    """Catches a failed precision boundary being silently admitted."""
    keys = tuple(
        ("PROFILE", SetupType.PRE_BREAKOUT.value) for _ in outcomes
    )

    overall = aggregate_structure_stop_metrics(keys, outcomes)[0]

    assert not overall.qualifies
    assert reason in overall.qualification_reasons


def test_metric_boundaries_accept_fifty_percent_and_forty_percent() -> None:
    """Catches exact 50% positive or 40% stop rates being excluded."""
    outcomes = tuple(
        _resolved_outcome(
            "PROFILE",
            index,
            "0.02" if index < 50 else "-0.001",
            stop_first=index < 40,
        )
        for index in range(100)
    )

    overall = aggregate_structure_stop_metrics(
        (("PROFILE", SetupType.PRE_BREAKOUT.value),) * 100,
        outcomes,
    )[0]

    assert overall.positive_net_rate == Decimal("0.5")
    assert overall.stop_first_rate == Decimal("0.4")
    assert overall.qualifies


def test_metric_empty_denominators_remain_null() -> None:
    """Catches empty evidence receiving synthetic zero rates or returns."""
    profile_id = build_structure_stop_profiles()[0].profile_id

    overall = aggregate_structure_stop_metrics(
        ((profile_id, SetupType.PRE_BREAKOUT.value),),
        (),
    )[0]

    assert overall.candidate_count == 1
    assert overall.triggered == overall.resolved == 0
    assert overall.mean_net_return is None
    assert overall.median_net_return is None
    assert overall.positive_net_rate is None
    assert overall.stop_first_rate is None
    assert overall.mean_mfe is None
    assert overall.mean_mae is None


def _qualifying_metrics(
    profile_id: str,
    *,
    mean: str = "0.01",
    positive_rate: str = "0.60",
    stop_rate: str = "0.30",
    setup_type: str = "ALL",
) -> StructureStopMetrics:
    return StructureStopMetrics(
        profile_id,
        setup_type,
        12,
        10,
        10,
        6,
        3,
        Decimal(mean),
        Decimal("0.01"),
        Decimal(positive_rate),
        Decimal(stop_rate),
        Decimal("0.06"),
        Decimal("0.02"),
        True,
        (),
    )


def _freeze_kwargs():
    profiles = build_structure_stop_profiles()
    return {
        "profiles": profiles,
        "training_identities": tuple(
            f"research-{index:02d}" for index in range(8, 0, -1)
        ),
        "metrics": (
            _qualifying_metrics(profiles[0].profile_id, mean="0.01"),
            _qualifying_metrics(profiles[1].profile_id, mean="0.02"),
        ),
        "formal_rule_version": "buy-point-selection-3.1.0",
        "formal_policy_hash": "a" * 64,
        "profile_matrix_hash": structure_stop_profile_hash(profiles),
        "risk_coverage_complete": False,
    }


def test_freeze_requires_eight_windows_and_ranks_only_overall_metrics() -> None:
    """Catches partial evidence, setup rows, or unstable ranking entering freeze."""
    kwargs = _freeze_kwargs()
    setup_only = _qualifying_metrics(
        kwargs["profiles"][2].profile_id,
        mean="0.20",
        setup_type=SetupType.PRE_BREAKOUT.value,
    )

    freeze = freeze_structure_stop_profiles(
        **{**kwargs, "metrics": (*kwargs["metrics"], setup_only)}
    )

    assert freeze.training_identities == tuple(
        f"research-{index:02d}" for index in range(1, 9)
    )
    assert [(value.profile_id, value.rank) for value in freeze.profiles] == [
        (kwargs["profiles"][1].profile_id, 1),
        (kwargs["profiles"][0].profile_id, 2),
    ]
    assert all(
        value.training_metrics.setup_type == "ALL"
        for value in freeze.profiles
    )
    assert freeze.retrospective
    assert not freeze.empty
    assert not freeze.promotion_eligible
    assert len(freeze.freeze_hash) == 64
    validate_structure_stop_freeze(freeze)


@pytest.mark.parametrize(
    "identities",
    (
        tuple(f"research-{index}" for index in range(7)),
        tuple(f"research-{index}" for index in range(9)),
        ("duplicate", "duplicate", "3", "4", "5", "6", "7", "8"),
    ),
)
def test_freeze_rejects_non_eight_or_duplicate_evidence(
    identities: tuple[str, ...],
) -> None:
    """Catches an incomplete or duplicated retrospective window set."""
    with pytest.raises(ValueError, match="eight distinct research identities"):
        freeze_structure_stop_profiles(
            **{**_freeze_kwargs(), "training_identities": identities}
        )


def test_freeze_rejects_wrong_matrix_or_diagnostic_metric_ids() -> None:
    """Catches lineage drift or diagnostic cohorts entering qualification."""
    kwargs = _freeze_kwargs()
    with pytest.raises(ValueError, match="profile matrix hash"):
        freeze_structure_stop_profiles(
            **{**kwargs, "profile_matrix_hash": "0" * 64}
        )
    diagnostic = _qualifying_metrics("DIAGNOSTIC_ONLY_COMBINED_FAILURE")
    with pytest.raises(ValueError, match="unsupported structure stop profile"):
        freeze_structure_stop_profiles(
            **{**kwargs, "metrics": (*kwargs["metrics"], diagnostic)}
        )


def test_freeze_rejects_internally_inconsistent_metric_qualification() -> None:
    """Catches an edited qualifies flag or reason tuple being trusted."""
    kwargs = _freeze_kwargs()
    forged = replace(
        kwargs["metrics"][0],
        qualification_reasons=("MINIMUM_RESOLVED_TRIGGERED",),
    )

    with pytest.raises(ValueError, match="metric qualification mismatch"):
        freeze_structure_stop_profiles(
            **{**kwargs, "metrics": (forged,)}
        )


def test_empty_freeze_is_valid_without_fallback_profiles() -> None:
    """Catches threshold relaxation or profile backfill hiding weak evidence."""
    kwargs = _freeze_kwargs()
    failed = replace(
        kwargs["metrics"][0],
        resolved=9,
        qualifies=False,
        qualification_reasons=("MINIMUM_RESOLVED_TRIGGERED",),
    )

    freeze = freeze_structure_stop_profiles(
        **{**kwargs, "metrics": (failed,)}
    )

    assert freeze.profiles == ()
    assert freeze.empty
    assert not freeze.promotion_eligible
    validate_structure_stop_freeze(freeze)


@pytest.mark.parametrize("mutation", ("setup", "weak", "hash", "rank"))
def test_freeze_validation_rejects_tampering(mutation: str) -> None:
    """Catches edited training metrics, hash, or rank order being trusted."""
    freeze = freeze_structure_stop_profiles(**_freeze_kwargs())
    if mutation == "setup":
        first = replace(
            freeze.profiles[0],
            training_metrics=replace(
                freeze.profiles[0].training_metrics,
                setup_type=SetupType.PRE_BREAKOUT.value,
            ),
        )
        tampered = replace(freeze, profiles=(first, *freeze.profiles[1:]))
    elif mutation == "weak":
        first = replace(
            freeze.profiles[0],
            training_metrics=replace(
                freeze.profiles[0].training_metrics,
                resolved=9,
                qualifies=False,
                qualification_reasons=("MINIMUM_RESOLVED_TRIGGERED",),
            ),
        )
        tampered = replace(freeze, profiles=(first, *freeze.profiles[1:]))
    elif mutation == "rank":
        tampered = replace(
            freeze,
            profiles=tuple(reversed(freeze.profiles)),
        )
    else:
        tampered = replace(freeze, freeze_hash="0" * 64)

    with pytest.raises(ValueError, match="structure stop freeze"):
        validate_structure_stop_freeze(tampered)


def test_frozen_selection_deduplicates_ranks_and_caps_each_date() -> None:
    """Catches profile rank drift, duplicate stocks, or baskets above five."""
    freeze = freeze_structure_stop_profiles(**_freeze_kwargs())
    candidates = (
        _candidate(code="600001", profile_index=0, quality="0.99"),
        _candidate(code="600001", profile_index=1, quality="0.70"),
        _candidate(code="600002", profile_index=1, quality="0.90", buffer="1"),
        _candidate(code="600003", profile_index=1, quality="0.80", buffer="3"),
        _candidate(
            code="600004",
            profile_index=1,
            quality="0.80",
            buffer="2",
            amount="300000",
        ),
        _candidate(
            code="600005",
            profile_index=1,
            quality="0.80",
            buffer="2",
            amount="200000",
        ),
        _candidate(code="600006", profile_index=0, quality="0.95"),
        _candidate(code="600007", profile_index=0, quality="0.90"),
        _candidate(code="600008", profile_index=2, quality="1.00"),
    )

    selected = select_frozen_structure_stop_candidates(candidates, freeze)

    assert [value.hit.code for value in selected] == [
        "600002",
        "600003",
        "600004",
        "600005",
        "600001",
    ]
    assert selected[-1].profile.profile_id == freeze.profiles[0].profile_id
    assert len({(value.hit.signal_date, value.hit.code) for value in selected}) == 5
    assert all(value.executable_shares == 0 for value in selected)


def test_empty_freeze_selects_nothing_without_backfill() -> None:
    """Catches weak evidence being hidden by an unfrozen fallback profile."""
    kwargs = _freeze_kwargs()
    failed = replace(
        kwargs["metrics"][0],
        resolved=9,
        qualifies=False,
        qualification_reasons=("MINIMUM_RESOLVED_TRIGGERED",),
    )
    freeze = freeze_structure_stop_profiles(
        **{**kwargs, "metrics": (failed,)}
    )

    assert select_frozen_structure_stop_candidates(
        (_candidate(),), freeze
    ) == ()


@pytest.mark.parametrize("layer", ("candidate", "hit", "anchor", "status"))
def test_frozen_selection_rejects_executable_state(layer: str) -> None:
    """Catches a selected research row carrying trade permission or shares."""
    freeze = freeze_structure_stop_profiles(**_freeze_kwargs())
    candidate = _candidate(profile_index=1)
    if layer == "candidate":
        candidate = replace(candidate, executable_shares=100)
    elif layer == "hit":
        candidate = replace(
            candidate,
            hit=replace(candidate.hit, executable_shares=100),
        )
    elif layer == "anchor":
        candidate = replace(
            candidate,
            anchor=replace(candidate.anchor, executable_shares=100),
        )
    else:
        candidate = replace(candidate, trade_permission="ALLOW")

    with pytest.raises(ValueError, match="zero-share research"):
        select_frozen_structure_stop_candidates((candidate,), freeze)


def test_frozen_selection_rejects_bad_limits_profiles_and_diagnostics() -> None:
    """Catches malformed inputs being silently filtered as ordinary non-winners."""
    freeze = freeze_structure_stop_profiles(**_freeze_kwargs())
    candidate = _candidate(profile_index=1)
    forged_profile = replace(candidate.profile, profile_id="FORGED")
    forged = replace(candidate, profile=forged_profile)
    diagnostic = StructureStopDiagnostic(
        "600001",
        SIGNAL,
        "SECTOR",
        "SECTOR_BREADTH_WEAK",
        "RISK_DISTANCE_OUT_OF_RANGE",
    )

    with pytest.raises(ValueError, match="maximum_per_date"):
        select_frozen_structure_stop_candidates(
            (candidate,), freeze, maximum_per_date=0
        )
    with pytest.raises(ValueError, match="unsupported structure stop profile"):
        select_frozen_structure_stop_candidates((forged,), freeze)
    with pytest.raises(ValueError, match="structure stop candidate"):
        select_frozen_structure_stop_candidates((diagnostic,), freeze)
