from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from short_term_trading.contracts import (
    CandidateV3,
    ForwardSelectionRunV1,
    PlanEventV1,
    TradePlanV3,
)


AS_OF = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
CANDIDATE_ID = "40000000-0000-4000-8000-000000000001"
PLAN_ID = "40000000-0000-4000-8000-000000000002"
EVENT_ID = "40000000-0000-4000-8000-000000000003"
RUN_ID = "40000000-0000-4000-8000-000000000004"
EVIDENCE_ID = "40000000-0000-4000-8000-000000000005"
STRUCTURE_ID = "0123456789abcdef0123456789abcdef"
FINGERPRINT = "a" * 64


def candidate_payload(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "candidate_id": CANDIDATE_ID,
        "as_of": AS_OF,
        "source": "buy-point-selection",
        "data_status": "VALID",
        "analysis_date": date(2026, 8, 10),
        "trading_date": date(2026, 8, 11),
        "code": "600001",
        "name": "虚构股份",
        "candidate_type": "PRE_BREAKOUT",
        "selection_tier": "FORMAL",
        "executable_status": "EXECUTABLE",
        "structure_id": STRUCTURE_ID,
        "pattern_quality": Decimal("0.85"),
        "sector": "S1",
        "sector_metrics": {"percentile": "0.80"},
        "missing_fields": (),
        "rejected_reasons": (),
        "rule_version": "buy-point-selection-3.0.0",
        "evidence_refs": (EVIDENCE_ID,),
    }
    values.update(updates)
    return values


def plan_payload(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "plan_id": PLAN_ID,
        "candidate_id": CANDIDATE_ID,
        "as_of": AS_OF,
        "source": "buy-point-selection",
        "data_status": "VALID",
        "analysis_date": date(2026, 8, 10),
        "trading_date": date(2026, 8, 11),
        "code": "600001",
        "structure_id": STRUCTURE_ID,
        "selection_tier": "FORMAL",
        "plan_state": "PREPARED",
        "signal_close": Decimal("9.95"),
        "trigger_price": Decimal("10.01"),
        "invalidation_price": Decimal("9.71"),
        "target_2r": Decimal("10.61"),
        "risk_distance": Decimal("0.30"),
        "risk_reward_ratio": Decimal("2"),
        "maximum_shares": 300,
        "market_status": "ALLOW",
        "valid_through_trade_date": date(2026, 8, 12),
        "valid_session_count": 2,
        "rule_version": "buy-point-selection-3.0.0",
        "evidence_refs": (EVIDENCE_ID,),
    }
    values.update(updates)
    return values


def event_payload(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "event_id": EVENT_ID,
        "plan_id": PLAN_ID,
        "structure_id": STRUCTURE_ID,
        "previous_state": None,
        "new_state": "PREPARED",
        "reason_code": "PLAN_CREATED",
        "evidence_refs": (EVIDENCE_ID,),
        "observed_at": AS_OF,
        "event_fingerprint": FINGERPRINT,
        "as_of": AS_OF,
        "source": "buy-point-selection",
        "data_status": "VALID",
    }
    values.update(updates)
    return values


def test_shadow_or_observe_candidate_cannot_be_executable() -> None:
    """Catches research and incomplete rows gaining execution permission in serialization."""
    for tier in ("SHADOW", "OBSERVE"):
        with pytest.raises(ValueError, match="cannot be executable"):
            CandidateV3(**candidate_payload(selection_tier=tier))


def test_prepared_plan_requires_exact_structure_risk_and_two_r() -> None:
    """Catches persisted plan arithmetic drifting from the audited price plan."""
    plan = TradePlanV3(**plan_payload())
    assert plan.target_2r == plan.trigger_price + 2 * plan.risk_distance
    assert len(plan.structure_id) == 32
    with pytest.raises(ValueError, match="target_2r"):
        TradePlanV3(**plan_payload(target_2r=Decimal("10.60")))
    with pytest.raises(ValueError, match="risk_distance"):
        TradePlanV3(**plan_payload(risk_distance=Decimal("0.29")))


def test_non_formal_plan_cannot_persist_executable_share_count() -> None:
    """Catches observe or shadow rows leaking actionable size into storage."""
    with pytest.raises(ValueError, match="non-formal"):
        TradePlanV3(**plan_payload(selection_tier="OBSERVE", maximum_shares=300))
    assert TradePlanV3(
        **plan_payload(selection_tier="SHADOW", maximum_shares=0)
    ).maximum_shares == 0
    with pytest.raises(ValueError, match="FREEZE"):
        TradePlanV3(**plan_payload(market_status="FREEZE"))


def test_plan_event_only_accepts_forward_state_transitions() -> None:
    """Catches rewriting a resolved append-only plan back to PREPARED."""
    assert PlanEventV1(**event_payload()).new_state == "PREPARED"
    with pytest.raises(ValueError, match="transition"):
        PlanEventV1(
            **event_payload(previous_state="EXPIRED", new_state="PREPARED")
        )


def test_forward_run_counts_and_release_mode_are_strict() -> None:
    """Catches negative audit counts or an unknown release mode entering the ledger."""
    run = ForwardSelectionRunV1(
        run_id=RUN_ID,
        analysis_date=date(2026, 8, 10),
        rule_version="buy-point-selection-3.0.0",
        formal_count=0,
        observe_count=2,
        shadow_count=4,
        resolved_count=1,
        duplicate_count=0,
        integrity_violations=(),
        release_mode="SHADOW",
        as_of=AS_OF,
        source="buy-point-selection",
        data_status="VALID",
    )
    assert run.release_mode.value == "SHADOW"
    with pytest.raises(ValueError):
        ForwardSelectionRunV1(**{**run.model_dump(), "formal_count": -1})
