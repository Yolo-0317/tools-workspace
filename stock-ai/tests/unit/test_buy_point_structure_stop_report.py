from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.case_review import CaseOutcome
from stock_ai.buy_point_selection.models import DetectedSetup, SetupType
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.structure_stop_evaluation import (
    StructureStopMetrics,
    StructureStopOutcome,
    aggregate_structure_stop_metrics,
    freeze_structure_stop_profiles,
)
from stock_ai.buy_point_selection.structure_stop_report import (
    StructureStopForwardScreen,
    StructureStopForwardSettlement,
    StructureStopResearchReview,
    StructureStopScreenCandidate,
    load_structure_stop_forward_screen,
    load_structure_stop_forward_settlement,
    load_structure_stop_freeze,
    structure_stop_screen_payload,
    structure_stop_screen_identity,
    structure_stop_settlement_payload,
    structure_stop_freeze_payload,
    structure_stop_research_payload,
    write_structure_stop_forward_screen,
    write_structure_stop_forward_settlement,
    write_structure_stop_freeze,
    write_structure_stop_research_revision,
)
from stock_ai.buy_point_selection.structure_stop_shadow import (
    StructureStopAnchor,
    StructureStopBaselineHit,
    StructureStopCandidate,
    StructureStopDiagnostic,
    StructureStopRejection,
    StructureStopReplay,
    build_structure_stop_profiles,
    structure_stop_profile_hash,
)
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ExactRecallComparison,
)


SIGNAL = date(2026, 7, 20)
CUTOFF = SIGNAL + timedelta(days=5)


def _candidate(
    *,
    code: str = "600001",
    profile_index: int = 0,
) -> StructureStopCandidate:
    profile = build_structure_stop_profiles()[profile_index]
    setup = DetectedSetup(
        code,
        SetupType.PRE_BREAKOUT,
        SIGNAL,
        SIGNAL - timedelta(days=20),
        Decimal("10.00"),
        Decimal("9.93"),
        Decimal("0.80"),
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
        Decimal("9.76"),
        (),
    )
    plan = PricePlan(
        f"structure-{code}-{profile.profile_id}",
        code,
        SetupType.PRE_BREAKOUT,
        SIGNAL,
        Decimal("10.00"),
        Decimal("10.01"),
        Decimal("9.76"),
        Decimal("10.51"),
        Decimal("0.25"),
        Decimal("2"),
        100,
        SIGNAL + timedelta(days=2),
    )
    return StructureStopCandidate(
        hit,
        profile,
        anchor,
        plan,
        Decimal("200000"),
        Decimal("1.00"),
    )


def _outcome(candidate: StructureStopCandidate) -> StructureStopOutcome:
    return StructureStopOutcome(
        candidate.profile.profile_id,
        candidate.hit.setup.setup_type.value,
        candidate.hit.code,
        candidate.hit.signal_date,
        CaseOutcome(
            candidate.hit.code,
            candidate.hit.signal_date,
            "STRUCTURE_STOP_SHADOW",
            "CLOSED",
            Decimal("0.08"),
            Decimal("0.02"),
            candidate.hit.signal_date + timedelta(days=1),
            Decimal("10.01"),
            Decimal("0.04"),
            Decimal("0.04"),
            False,
            False,
            candidate.plan.structure_id,
        ),
    )


def _research() -> StructureStopResearchReview:
    profiles = build_structure_stop_profiles()
    candidate = _candidate()
    diagnostic = StructureStopDiagnostic(
        "600002",
        SIGNAL,
        "MARKET",
        "INDEX_AND_BREADTH_WEAK",
        "RISK_DISTANCE_OUT_OF_RANGE",
    )
    replay = StructureStopReplay(
        (SIGNAL,),
        (),
        (candidate.hit,),
        (candidate,),
        (diagnostic,),
        (
            StructureStopRejection(
                "600003", SIGNAL, None, "SETUP", ("NO_BUY_POINT_SETUP",)
            ),
        ),
    )
    outcome = _outcome(candidate)
    metrics = aggregate_structure_stop_metrics(
        ((candidate.profile.profile_id, candidate.hit.setup.setup_type.value),),
        (outcome,),
    )
    return StructureStopResearchReview(
        signal_dates=(SIGNAL,),
        outcome_cutoff=CUTOFF,
        v5_case_identity="v5-case-identity",
        input_fingerprint="input-fingerprint",
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="a" * 64,
        profile_matrix_hash=structure_stop_profile_hash(profiles),
        profiles=profiles,
        replay=replay,
        outcomes=(outcome,),
        profile_metrics=metrics,
        exact_recall=ExactRecallComparison(1, 0, 1, 1, 0),
        risk_coverage_complete=False,
    )


def _share_values(value: object) -> list[object]:
    found: list[object] = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            found.extend(
                child
                for key, child in item.items()
                if "shares" in str(key)
            )
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def test_research_payload_reconciles_primary_diagnostic_and_outcome_rows() -> None:
    """Catches mixed cohorts, missing rows, or executable shares in research."""
    payload = structure_stop_research_payload(_research())

    assert payload["schema"] == "buy-point-structure-stop-shadow-v1"
    assert payload["stage"] == "research"
    assert payload["status"] == "CASE_ANALYSIS_ONLY"
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["retrospective"] is True
    assert payload["evaluator_version"] == "case-evaluator-v1"
    assert payload["cost_version"] == "execution-costs-default-v1"
    assert [value["profile_id"] for value in payload["profiles"]] == [
        "STRUCTURE_STOP:RECENT_SETUP_LOW",
        "STRUCTURE_STOP:DYNAMIC_SUPPORT",
        "STRUCTURE_STOP:ATR_1_5",
    ]
    assert len(payload["baseline_hits"]) == payload["metrics"]["baseline_hits"] == 1
    assert len(payload["candidates"]) == payload["metrics"]["candidates"] == 1
    assert len(payload["diagnostics"]) == payload["metrics"]["diagnostics"] == 1
    assert len(payload["outcomes"]) == payload["metrics"]["outcomes"] == 1
    assert payload["risk_coverage_complete"] is False
    assert payload["promotion_eligible"] is False
    assert _share_values(payload) and set(_share_values(payload)) == {0}

    diagnostic_codes = {value["code"] for value in payload["diagnostics"]}
    candidate_codes = {value["code"] for value in payload["candidates"]}
    metric_profiles = {
        value["profile_id"] for value in payload["profile_metrics"]
    }
    assert diagnostic_codes.isdisjoint(candidate_codes)
    assert "DIAGNOSTIC_ONLY_COMBINED_FAILURE" not in metric_profiles


def test_research_payload_rejects_candidate_outcome_or_diagnostic_overlap() -> None:
    """Catches unreconciled results or diagnostics entering evaluable metrics."""
    review = _research()
    with pytest.raises(ValueError, match="candidate and outcome membership"):
        structure_stop_research_payload(replace(review, outcomes=()))

    diagnostic = replace(review.replay.diagnostics[0], code="600001")
    replay = replace(review.replay, diagnostics=(diagnostic,))
    with pytest.raises(ValueError, match="diagnostic cohort overlaps"):
        structure_stop_research_payload(replace(review, replay=replay))


def _freeze():
    profiles = build_structure_stop_profiles()
    metrics = StructureStopMetrics(
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
            f"research-{index:02d}" for index in range(1, 9)
        ),
        metrics=(metrics,),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="a" * 64,
        profile_matrix_hash=structure_stop_profile_hash(profiles),
        risk_coverage_complete=False,
    )


def test_research_and_freeze_writes_are_exclusive_and_repeatable(
    tmp_path: Path,
) -> None:
    """Catches immutable evidence being silently overwritten on rerun."""
    research = _research()
    research_paths = write_structure_stop_research_revision(
        research, tmp_path
    )
    assert write_structure_stop_research_revision(
        research, tmp_path
    ) == research_paths
    with pytest.raises(ValueError, match="immutable artifact content mismatch"):
        write_structure_stop_research_revision(
            replace(research, risk_coverage_complete=True), tmp_path
        )

    freeze = _freeze()
    freeze_paths = write_structure_stop_freeze(freeze, tmp_path)
    assert write_structure_stop_freeze(freeze, tmp_path) == freeze_paths
    assert freeze_paths[0].name == f"freeze-{freeze.freeze_hash}.json"
    assert freeze_paths[1].exists()
    assert load_structure_stop_freeze(freeze_paths[0]) == freeze


@pytest.mark.parametrize(
    "mutation",
    ("metric", "rank", "identity", "status", "promotion", "hash"),
)
def test_freeze_loader_rejects_tampering(
    tmp_path: Path, mutation: str
) -> None:
    """Catches edited freeze evidence being accepted as canonical lineage."""
    payload = structure_stop_freeze_payload(_freeze())
    if mutation == "metric":
        payload["profiles"][0]["training_metrics"]["candidate_count"] = 99
    elif mutation == "rank":
        payload["profiles"][0]["rank"] = 2
    elif mutation == "identity":
        payload["training_identities"][0] = "edited"
    elif mutation == "status":
        payload["trade_permission"] = "ALLOW"
    elif mutation == "promotion":
        payload["promotion_eligible"] = True
    else:
        payload["freeze_hash"] = "0" * 64
    path = tmp_path / f"tampered-{mutation}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="structure stop freeze"):
        load_structure_stop_freeze(path)


def _screen(
    *candidates: StructureStopScreenCandidate,
) -> StructureStopForwardScreen:
    profiles = build_structure_stop_profiles()
    selected = candidates or (StructureStopScreenCandidate(_candidate(), 1),)
    return StructureStopForwardScreen(
        signal_date=SIGNAL,
        input_fingerprint="forward-input-fingerprint",
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="a" * 64,
        profile_matrix_hash=structure_stop_profile_hash(profiles),
        freeze_hash=_freeze().freeze_hash,
        candidates=tuple(selected),
        risk_coverage_complete=False,
    )


def test_forward_screen_is_bounded_zero_share_and_result_free() -> None:
    """Catches hindsight leakage or executable advice entering screen output."""
    payload = structure_stop_screen_payload(_screen())

    assert payload["schema"] == "buy-point-structure-stop-shadow-v1"
    assert payload["stage"] == "screen"
    assert payload["status"] == "CASE_ANALYSIS_ONLY"
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["retrospective"] is False
    assert payload["planner_version"] == "price-plan-v1"
    assert payload["freeze_hash"] == _freeze().freeze_hash
    assert payload["metrics"] == {"selected": 1}
    assert len(payload["artifact_identity"]) == 16
    assert len(payload["candidates"]) == 1
    candidate = payload["candidates"][0]
    assert candidate["profile_rank"] == 1
    assert candidate["trigger_price"] == "10.01"
    assert candidate["invalidation_price"] == "9.76"
    assert candidate["target_2r"] == "10.51"
    assert candidate["structure_id"].startswith("structure-")
    assert set(_share_values(payload)) == {0}

    encoded = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        '"outcomes"',
        '"net_return"',
        '"mfe"',
        '"mae"',
        '"price_bars"',
        '"trade_date"',
    ):
        assert forbidden not in encoded


@pytest.mark.parametrize(
    "mutation",
    ("duplicate", "too_many", "shares", "profile", "signal", "rank"),
)
def test_forward_screen_rejects_unbounded_or_unsafe_candidates(
    mutation: str,
) -> None:
    """Catches unsafe membership, unsupported profiles, or excess output."""
    candidate = _candidate()
    if mutation == "duplicate":
        screen = _screen(
            StructureStopScreenCandidate(candidate, 1),
            StructureStopScreenCandidate(candidate, 1),
        )
    elif mutation == "too_many":
        screen = _screen(
            *(
                StructureStopScreenCandidate(
                    _candidate(code=f"60000{index}"), 1
                )
                for index in range(1, 7)
            )
        )
    elif mutation == "shares":
        screen = _screen(
            StructureStopScreenCandidate(
                replace(candidate, executable_shares=100), 1
            )
        )
    elif mutation == "profile":
        forged = replace(
            candidate.profile,
            profile_id="STRUCTURE_STOP:FORGED",
        )
        screen = _screen(
            StructureStopScreenCandidate(
                replace(
                    candidate,
                    profile=forged,
                    anchor=replace(candidate.anchor, profile=forged),
                ),
                1,
            )
        )
    elif mutation == "signal":
        screen = _screen(
            StructureStopScreenCandidate(
                replace(
                    candidate,
                    hit=replace(
                        candidate.hit,
                        signal_date=SIGNAL - timedelta(days=1),
                    ),
                ),
                1,
            )
        )
    else:
        screen = _screen(StructureStopScreenCandidate(candidate, 0))

    with pytest.raises(ValueError, match="structure stop screen"):
        structure_stop_screen_payload(screen)


def test_forward_screen_writer_and_loader_preserve_immutable_lineage(
    tmp_path: Path,
) -> None:
    """Catches mutable filenames and unverified screen payloads."""
    screen = _screen()
    paths = write_structure_stop_forward_screen(screen, tmp_path)
    assert write_structure_stop_forward_screen(screen, tmp_path) == paths
    assert paths[0].name == (
        f"screen_{SIGNAL:%Y%m%d}_"
        f"{structure_stop_screen_payload(screen)['artifact_identity']}.json"
    )
    assert load_structure_stop_forward_screen(paths[0]) == json.loads(
        paths[0].read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "mutation",
    ("outcome", "future_bars", "identity", "count", "status", "shares"),
)
def test_forward_screen_loader_rejects_tampering(
    tmp_path: Path, mutation: str
) -> None:
    """Catches hindsight/result injection and edited safety lineage."""
    payload = structure_stop_screen_payload(_screen())
    if mutation == "outcome":
        payload["candidates"][0]["net_return"] = "0.10"
    elif mutation == "future_bars":
        payload["price_bars"] = [
            {"trade_date": (SIGNAL + timedelta(days=1)).isoformat()}
        ]
    elif mutation == "identity":
        payload["artifact_identity"] = "0" * 16
    elif mutation == "count":
        payload["metrics"]["selected"] = 2
    elif mutation == "status":
        payload["trade_permission"] = "ALLOW"
    else:
        payload["candidates"][0]["executable_shares"] = 100
    path = tmp_path / f"tampered-screen-{mutation}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="structure stop screen"):
        load_structure_stop_forward_screen(path)


FORWARD_DATES = tuple(
    SIGNAL + timedelta(days=offset) for offset in (1, 2, 3, 4, 7)
)


def _settlement() -> StructureStopForwardSettlement:
    screen = _screen()
    return StructureStopForwardSettlement(
        parent_screen_identity=structure_stop_screen_identity(screen),
        signal_date=SIGNAL,
        outcome_cutoff=FORWARD_DATES[-1],
        outcome_dates=FORWARD_DATES,
        freeze_hash=screen.freeze_hash,
        input_fingerprint="settlement-input-fingerprint",
        candidates=screen.candidates,
        outcomes=(_outcome(screen.candidates[0].candidate),),
        risk_coverage_complete=False,
    )


def test_forward_settlement_reconciles_screen_membership_and_five_sessions() -> None:
    """Catches outcome substitution or an unbounded forward result window."""
    settlement = _settlement()
    payload = structure_stop_settlement_payload(settlement)

    assert payload["schema"] == "buy-point-structure-stop-shadow-v1"
    assert payload["stage"] == "settlement"
    assert payload["status"] == "CASE_ANALYSIS_ONLY"
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["retrospective"] is True
    assert payload["parent_screen_identity"] == (
        settlement.parent_screen_identity
    )
    assert payload["outcome_dates"] == [
        value.isoformat() for value in FORWARD_DATES
    ]
    assert payload["outcome_cutoff"] == FORWARD_DATES[-1].isoformat()
    assert payload["freeze_hash"] == settlement.freeze_hash
    assert payload["metrics"] == {
        "selected": 1,
        "outcomes": 1,
        "resolved": 1,
        "positive_net": 1,
        "stop_first": 0,
    }
    assert payload["candidates"][0]["profile_rank"] == 1
    assert payload["candidates"][0]["code"] == payload["outcomes"][0]["code"]
    assert set(_share_values(payload)) == {0}


@pytest.mark.parametrize(
    "mutation",
    (
        "outcome_code",
        "missing_outcome",
        "rank",
        "cutoff",
        "dates",
        "freeze",
        "parent",
        "shares",
    ),
)
def test_forward_settlement_rejects_lineage_or_membership_drift(
    mutation: str,
) -> None:
    """Catches a settlement detached from its frozen screen cohort."""
    value = _settlement()
    if mutation == "outcome_code":
        value = replace(
            value,
            outcomes=(replace(value.outcomes[0], code="600999"),),
        )
    elif mutation == "missing_outcome":
        value = replace(value, outcomes=())
    elif mutation == "rank":
        value = replace(
            value,
            candidates=(replace(value.candidates[0], profile_rank=0),),
        )
    elif mutation == "cutoff":
        value = replace(value, outcome_cutoff=FORWARD_DATES[-2])
    elif mutation == "dates":
        value = replace(value, outcome_dates=FORWARD_DATES[:4])
    elif mutation == "freeze":
        value = replace(value, freeze_hash="bad-freeze")
    elif mutation == "parent":
        value = replace(value, parent_screen_identity="bad-parent")
    else:
        value = replace(
            value,
            outcomes=(
                replace(value.outcomes[0], executable_shares=100),
            ),
        )

    with pytest.raises(ValueError, match="structure stop settlement"):
        structure_stop_settlement_payload(value)


def test_forward_settlement_is_separate_and_does_not_rewrite_screen(
    tmp_path: Path,
) -> None:
    """Catches late results being written back into the screen artifact."""
    screen_paths = write_structure_stop_forward_screen(_screen(), tmp_path)
    before = screen_paths[0].read_bytes()
    settlement = _settlement()
    paths = write_structure_stop_forward_settlement(settlement, tmp_path)

    assert screen_paths[0].read_bytes() == before
    assert write_structure_stop_forward_settlement(
        settlement, tmp_path
    ) == paths
    assert paths[0].name == (
        f"settlement_{SIGNAL:%Y%m%d}_cutoff-"
        f"{FORWARD_DATES[-1]:%Y%m%d}_"
        f"{structure_stop_settlement_payload(settlement)['artifact_identity']}.json"
    )
    assert load_structure_stop_forward_settlement(paths[0]) == json.loads(
        paths[0].read_text(encoding="utf-8")
    )
