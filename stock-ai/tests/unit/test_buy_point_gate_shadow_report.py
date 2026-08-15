from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.case_review import CaseOutcome
from stock_ai.buy_point_selection.gate_shadow_evaluation import (
    GateShadowOutcome,
    aggregate_gate_profile_metrics,
    freeze_sector_gate_profiles,
)
from stock_ai.buy_point_selection.gate_shadow_report import (
    GateForwardScreen,
    GateForwardSettlement,
    GateResearchReview,
    GateScreenCandidate,
    gate_research_payload,
    gate_screen_identity,
    gate_screen_payload,
    gate_settlement_payload,
    load_gate_forward_screen,
    load_gate_profile_freeze,
    write_gate_forward_screen,
    write_gate_forward_settlement,
    write_gate_profile_freeze,
    write_gate_research_revision,
)
from stock_ai.buy_point_selection.gate_shadow_research import (
    GateShadowCandidate,
    GateShadowHit,
    GateShadowReplay,
    build_gate_shadow_profiles,
    gate_profile_matrix_hash,
)
from stock_ai.buy_point_selection.models import DetectedSetup, SetupType
from stock_ai.buy_point_selection.planning import PricePlan
from stock_ai.buy_point_selection.threshold_shadow_evaluation import (
    ExactRecallComparison,
)


SIGNAL = date(2026, 7, 20)


def _candidate(code: str = "600001") -> GateShadowCandidate:
    profile = build_gate_shadow_profiles()[2]
    setup = DetectedSetup(
        code,
        SetupType.PRE_BREAKOUT,
        SIGNAL,
        SIGNAL - timedelta(days=20),
        Decimal("10.10"),
        Decimal("9.80"),
        Decimal("0.80"),
        ("FORMAL",),
        {},
    )
    hit = GateShadowHit(code, SIGNAL, profile, setup, "ALLOW", "S1")
    plan = PricePlan(
        f"structure-{code}",
        code,
        SetupType.PRE_BREAKOUT,
        SIGNAL,
        Decimal("10"),
        Decimal("10.11"),
        Decimal("9.76"),
        Decimal("10.81"),
        Decimal("0.35"),
        Decimal("2"),
        100,
        SIGNAL + timedelta(days=2),
    )
    return GateShadowCandidate(
        hit, plan, Decimal("200000"), Decimal("1.00")
    )


def _outcome(candidate: GateShadowCandidate) -> GateShadowOutcome:
    return GateShadowOutcome(
        candidate.hit.profile.profile_id,
        candidate.hit.code,
        candidate.hit.signal_date,
        CaseOutcome(
            candidate.hit.code,
            candidate.hit.signal_date,
            "GATE_SHADOW",
            "CLOSED",
            Decimal("0.08"),
            Decimal("0.02"),
            candidate.hit.signal_date + timedelta(days=1),
            Decimal("10.11"),
            Decimal("0.04"),
            Decimal("0.04"),
            False,
            False,
            candidate.plan.structure_id,
        ),
    )


def _research() -> GateResearchReview:
    profiles = build_gate_shadow_profiles()
    candidate = _candidate()
    replay = GateShadowReplay(
        (SIGNAL,), (), (candidate.hit,), (candidate,), ()
    )
    outcome = _outcome(candidate)
    return GateResearchReview(
        signal_dates=(SIGNAL,),
        outcome_cutoff=SIGNAL + timedelta(days=5),
        v5_case_identity="v5-case",
        input_fingerprint="input-hash",
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=gate_profile_matrix_hash(profiles),
        profiles=profiles,
        replay=replay,
        outcomes=(outcome,),
        profile_metrics=aggregate_gate_profile_metrics(
            (candidate.hit.profile.profile_id,), (outcome,)
        ),
        formal_candidates=(),
        formal_outcomes=(),
        exact_recall=ExactRecallComparison(1, 0, 1, 1, 0),
        risk_coverage_complete=False,
    )


def _empty_freeze():
    profiles = build_gate_shadow_profiles()
    return freeze_sector_gate_profiles(
        profiles=profiles,
        training_identities=("first", "second", "third"),
        metrics=(),
        formal_rule_version="buy-point-selection-3.1.0",
        formal_policy_hash="policy-hash",
        profile_matrix_hash=gate_profile_matrix_hash(profiles),
        risk_coverage_complete=False,
    )


def test_research_payload_reconciles_rows_and_safety_labels() -> None:
    """Catches research evidence disappearing or receiving trade permission."""
    payload = gate_research_payload(_research())

    assert payload["schema"] == "buy-point-gate-shadow-v1"
    assert payload["stage"] == "research"
    assert payload["status"] == "CASE_ANALYSIS_ONLY"
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["retrospective"]
    assert payload["evaluator_version"] == "case-evaluator-v1"
    assert payload["cost_version"] == "execution-costs-default-v1"
    assert len(payload["profiles"]) == 6
    assert len(payload["raw_hits"]) == payload["metrics"]["raw_hits"] == 1
    assert len(payload["candidates"]) == payload["metrics"]["candidates"] == 1
    assert len(payload["outcomes"]) == payload["metrics"]["outcomes"] == 1
    assert {value["executable_shares"] for value in payload["candidates"]} == {0}
    assert not payload["promotion_eligible"]


def test_freeze_and_research_writes_are_immutable(tmp_path: Path) -> None:
    """Catches silent overwrite or malformed freeze entering a screen."""
    research = _research()
    research_paths = write_gate_research_revision(research, tmp_path)
    assert write_gate_research_revision(research, tmp_path) == research_paths
    with pytest.raises(ValueError, match="immutable artifact content mismatch"):
        write_gate_research_revision(
            replace(research, risk_coverage_complete=True), tmp_path
        )

    freeze = _empty_freeze()
    freeze_json, freeze_markdown = write_gate_profile_freeze(freeze, tmp_path)
    assert freeze_markdown.exists()
    assert load_gate_profile_freeze(freeze_json) == freeze
    assert freeze.retrospective
    assert freeze.empty
    assert not freeze.promotion_eligible


def test_screen_payload_has_no_outcomes_and_rejects_market_or_duplicates() -> None:
    """Catches future results or diagnostic market rows entering forward screen."""
    candidate = _candidate()
    screen = GateForwardScreen(
        SIGNAL,
        "screen-input",
        "buy-point-selection-3.1.0",
        "policy-hash",
        gate_profile_matrix_hash(build_gate_shadow_profiles()),
        "freeze-hash",
        (GateScreenCandidate(candidate, 1),),
        False,
    )

    payload = gate_screen_payload(screen)
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["stage"] == "screen"
    assert not payload["retrospective"]
    assert payload["freeze_hash"] == "freeze-hash"
    assert payload["metrics"]["selected_candidates"] == 1
    assert '"net_return"' not in encoded
    assert '"mfe"' not in encoded
    assert '"mae"' not in encoded
    assert payload["candidates"][0]["profile_rank"] == 1
    assert payload["candidates"][0]["executable_shares"] == 0

    market_candidate = replace(
        candidate,
        hit=replace(candidate.hit, profile=build_gate_shadow_profiles()[0]),
    )
    with pytest.raises(ValueError, match="sector profiles"):
        gate_screen_payload(
            replace(screen, candidates=(GateScreenCandidate(market_candidate, 1),))
        )
    with pytest.raises(ValueError, match="duplicate"):
        gate_screen_payload(
            replace(
                screen,
                candidates=(
                    GateScreenCandidate(candidate, 1),
                    GateScreenCandidate(candidate, 1),
                ),
            )
        )


def test_settlement_preserves_screen_membership_and_parent_identity(
    tmp_path: Path,
) -> None:
    """Catches settlement rewriting which stocks the screen actually selected."""
    candidate = _candidate()
    screen = GateForwardScreen(
        SIGNAL,
        "screen-input",
        "buy-point-selection-3.1.0",
        "policy-hash",
        gate_profile_matrix_hash(build_gate_shadow_profiles()),
        "freeze-hash",
        (GateScreenCandidate(candidate, 1),),
        False,
    )
    screen_paths = write_gate_forward_screen(screen, tmp_path)
    loaded = load_gate_forward_screen(screen_paths[0])
    assert loaded["artifact_identity"] == gate_screen_identity(screen)
    settlement = GateForwardSettlement(
        gate_screen_identity(screen),
        SIGNAL,
        SIGNAL + timedelta(days=7),
        tuple(SIGNAL + timedelta(days=value) for value in range(1, 6)),
        "freeze-hash",
        "settlement-input",
        screen.candidates,
        (_outcome(candidate),),
        False,
    )

    payload = gate_settlement_payload(settlement)

    assert payload["parent_screen_identity"] == gate_screen_identity(screen)
    assert payload["metrics"]["selected_candidates"] == 1
    assert payload["metrics"]["outcomes"] == 1
    settlement_paths = write_gate_forward_settlement(settlement, tmp_path)
    assert settlement_paths[0].exists()
    assert screen_paths[0].read_bytes() == json.dumps(
        loaded, ensure_ascii=False, sort_keys=True, indent=2
    ).encode() + b"\n"

    wrong_outcome = replace(_outcome(candidate), code="600002")
    with pytest.raises(ValueError, match="membership"):
        gate_settlement_payload(replace(settlement, outcomes=(wrong_outcome,)))
