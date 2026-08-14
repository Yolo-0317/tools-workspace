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
from short_term_trading.repositories.planning import BuyPointBundle, PlanningRepository


AS_OF = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
CANDIDATE_ID = "50000000-0000-4000-8000-000000000001"
PLAN_ID = "50000000-0000-4000-8000-000000000002"
EVENT_ID = "50000000-0000-4000-8000-000000000003"
RUN_ID = "50000000-0000-4000-8000-000000000004"
EVIDENCE_ID = "50000000-0000-4000-8000-000000000005"
STRUCTURE_ID = "fedcba9876543210fedcba9876543210"


class Result:
    def __init__(self, row=None) -> None:
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class TransactionConnection:
    def __init__(self, engine, fail_on: int | None = None, row=None) -> None:
        self.engine = engine
        self.fail_on = fail_on
        self.row = row
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            raise RuntimeError("forced transaction failure")
        return Result(self.row)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.engine.committed = True
        else:
            self.engine.rolled_back = True
        return False


class TransactionEngine:
    def __init__(self, *, fail_on: int | None = None, row=None) -> None:
        self.committed = False
        self.rolled_back = False
        self.connection = TransactionConnection(self, fail_on=fail_on, row=row)

    def begin(self):
        return self.connection

    def connect(self):
        return self.connection


def _bundle() -> BuyPointBundle:
    candidate = CandidateV3(
        candidate_id=CANDIDATE_ID,
        analysis_date=date(2026, 8, 10),
        trading_date=date(2026, 8, 11),
        code="600001",
        name="虚构股份",
        candidate_type="PRE_BREAKOUT",
        selection_tier="FORMAL",
        executable_status="EXECUTABLE",
        structure_id=STRUCTURE_ID,
        pattern_quality=Decimal("0.85"),
        sector="S1",
        sector_metrics={"percentile": "0.80"},
        missing_fields=(),
        rejected_reasons=(),
        rule_version="buy-point-selection-3.0.0",
        evidence_refs=(EVIDENCE_ID,),
        as_of=AS_OF,
        source="buy-point-selection",
        data_status="VALID",
    )
    plan = TradePlanV3(
        plan_id=PLAN_ID,
        candidate_id=CANDIDATE_ID,
        analysis_date=date(2026, 8, 10),
        trading_date=date(2026, 8, 11),
        code="600001",
        structure_id=STRUCTURE_ID,
        selection_tier="FORMAL",
        plan_state="PREPARED",
        signal_close=Decimal("9.95"),
        trigger_price=Decimal("10.01"),
        invalidation_price=Decimal("9.71"),
        target_2r=Decimal("10.61"),
        risk_distance=Decimal("0.30"),
        risk_reward_ratio=Decimal("2"),
        maximum_shares=300,
        market_status="ALLOW",
        valid_through_trade_date=date(2026, 8, 12),
        valid_session_count=2,
        rule_version="buy-point-selection-3.0.0",
        evidence_refs=(EVIDENCE_ID,),
        as_of=AS_OF,
        source="buy-point-selection",
        data_status="VALID",
    )
    event = PlanEventV1(
        event_id=EVENT_ID,
        plan_id=PLAN_ID,
        structure_id=STRUCTURE_ID,
        previous_state=None,
        new_state="PREPARED",
        reason_code="PLAN_CREATED",
        evidence_refs=(EVIDENCE_ID,),
        observed_at=AS_OF,
        event_fingerprint="b" * 64,
        as_of=AS_OF,
        source="buy-point-selection",
        data_status="VALID",
    )
    run = ForwardSelectionRunV1(
        run_id=RUN_ID,
        analysis_date=date(2026, 8, 10),
        rule_version="buy-point-selection-3.0.0",
        formal_count=1,
        observe_count=0,
        shadow_count=2,
        resolved_count=0,
        duplicate_count=0,
        integrity_violations=(),
        release_mode="SHADOW",
        as_of=AS_OF,
        source="buy-point-selection",
        data_status="VALID",
    )
    return BuyPointBundle(candidate, plan, event, run)


def test_bundle_uses_one_transaction_and_idempotent_inserts() -> None:
    """Catches partial commits or repeated scans duplicating ledger rows."""
    engine = TransactionEngine()
    PlanningRepository(engine).save_buy_point_bundle(_bundle())
    statements = [value[0] for value in engine.connection.calls]
    assert engine.committed and not engine.rolled_back
    assert len(statements) == 4
    assert "INSERT IGNORE INTO stt_candidates" in statements[0]
    assert "INSERT IGNORE INTO stt_trade_plans" in statements[1]
    assert "INSERT IGNORE INTO stt_buy_point_plan_events" in statements[2]
    assert "INSERT IGNORE INTO stt_buy_point_forward_runs" in statements[3]


def test_bundle_failure_rolls_back_candidate_plan_and_event() -> None:
    """Catches candidate and plan surviving when the initial event cannot be saved."""
    engine = TransactionEngine(fail_on=3)
    with pytest.raises(RuntimeError, match="forced transaction failure"):
        PlanningRepository(engine).save_buy_point_bundle(_bundle())
    assert engine.rolled_back and not engine.committed


def test_full_runtime_run_persists_all_symbols_and_one_forward_row_atomically() -> None:
    """Catches one-symbol transactions exposing a partially materialized daily run."""
    engine = TransactionEngine()
    bundle = _bundle()
    PlanningRepository(engine).save_buy_point_run(
        ((bundle.candidate, bundle.plan, bundle.initial_event),) * 2,
        bundle.forward_run,
    )
    statements = [value[0] for value in engine.connection.calls]
    assert engine.committed and not engine.rolled_back
    assert len(statements) == 7
    assert sum("stt_buy_point_forward_runs" in value for value in statements) == 1
    assert "stt_buy_point_forward_runs" in statements[-1]


def test_state_change_appends_event_before_updating_projection() -> None:
    """Catches mutable state being changed without an immutable audit event."""
    engine = TransactionEngine()
    event = PlanEventV1(
        **{
            **_bundle().initial_event.model_dump(),
            "previous_state": "PREPARED",
            "new_state": "EXPIRED",
            "reason_code": "TRIGGER_WINDOW_ENDED",
            "event_fingerprint": "c" * 64,
        }
    )
    PlanningRepository(engine).append_plan_event(event)
    statements = [value[0] for value in engine.connection.calls]
    assert "INSERT IGNORE INTO stt_buy_point_plan_events" in statements[0]
    assert "UPDATE stt_trade_plans SET plan_state" in statements[1]


def test_forward_gate_requires_dates_resolved_plans_and_zero_violations() -> None:
    """Catches a short or corrupted forward run being treated as release-ready."""
    engine = TransactionEngine(
        row={"distinct_dates": 20, "resolved_plans": 20, "integrity_violations": 0}
    )
    summary = PlanningRepository(engine).forward_gate_summary("buy-point-selection-3.0.0")
    assert summary.eligible
    assert summary.distinct_dates == 20
