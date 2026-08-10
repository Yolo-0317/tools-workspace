from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys

import pytest

from short_term_trading.contracts import (
    CandidateV1,
    DecisionSnapshotV1,
    EvidenceSnapshotV1,
    IntradayDecisionV1,
    MarketStateV1,
    OutcomeObservationV1,
    PlanEvaluationV1,
    RiskDecisionV1,
    TradeJournalV1,
    TradePlanV1,
)
from short_term_trading.repositories.evidence import EvidenceRepository
from short_term_trading.repositories.planning import PlanningRepository
from short_term_trading.repositories.review import ReviewRepository
from short_term_trading.evidence import EvidenceSnapshot


pytestmark = pytest.mark.skipif(
    os.getenv("STT_MYSQL_INTEGRATION") != "1",
    reason="set STT_MYSQL_INTEGRATION=1 to use the configured household MySQL",
)

AS_OF = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
PROJECT = Path(__file__).resolve().parents[2]
IDS = {
    name: f"40000000-0000-4000-8000-{index:012d}"
    for index, name in enumerate(
        ["evidence", "state", "candidate", "plan", "risk", "decision", "intraday", "journal", "outcome", "evaluation"],
        start=1,
    )
}


def contracts() -> tuple[object, ...]:
    evidence = EvidenceSnapshotV1(
        evidence_id=IDS["evidence"], as_of=AS_OF, source="integration", data_status="VALID",
        kind="QUOTE", code="600000", payload={"last_price": Decimal("12.30")}, parser_version="1.0",
        raw_reference="fixture://quote", expires_at=AS_OF + timedelta(minutes=5), freshness_seconds=300,
        quality_flags=[],
    )
    state = MarketStateV1(
        state_id=IDS["state"], as_of=AS_OF, source="integration", data_status="VALID",
        trading_date=date(2026, 8, 10), index_change_pct=Decimal("1.0"), breadth_ratio=Decimal("0.6"),
        turnover_ratio=Decimal("1.1"), strong_sector_count=6, status="ALLOW", reasons=["ok"],
        evidence_refs=[IDS["evidence"]],
    )
    candidate = CandidateV1(
        candidate_id=IDS["candidate"], as_of=AS_OF, source="integration", data_status="VALID",
        trading_date=date(2026, 8, 10), code="600000", name="浦发银行", candidate_type="BREAKOUT",
        liquidity_score=Decimal("0.8"), trend_score=Decimal("0.7"), catalyst_score=Decimal("0.5"),
        sector="银行", rejected_reasons=[], evidence_refs=[IDS["evidence"]],
    )
    plan = TradePlanV1(
        plan_id=IDS["plan"], candidate_id=IDS["candidate"], as_of=AS_OF, source="integration",
        data_status="VALID", trading_date=date(2026, 8, 10), code="600000", status="WAIT_ENTRY",
        trigger_price=Decimal("12.30"), entry_ceiling=Decimal("12.55"), pullback_low=Decimal("12.05"),
        pullback_high=Decimal("12.20"), invalidation_price=Decimal("11.80"),
        first_reduce_price=Decimal("13.20"), risk_distance=Decimal("0.50"),
        valid_until=AS_OF + timedelta(days=1), rule_version="1.1.0", evidence_refs=[IDS["evidence"]],
    )
    risk = RiskDecisionV1(
        risk_id=IDS["risk"], plan_id=IDS["plan"], as_of=AS_OF, source="integration", data_status="VALID",
        code="600000", market_status="ALLOW", account_exposure=Decimal("10000"),
        theme_exposure=Decimal("10000"), open_trade_slots=2, max_shares=500, allowed=True,
        rejection_reasons=[],
    )
    decision = DecisionSnapshotV1(
        decision_id=IDS["decision"], as_of=AS_OF, source="integration", data_status="VALID",
        trading_date=date(2026, 8, 10), code="600000", candidate_id=IDS["candidate"],
        plan_id=IDS["plan"], risk_id=IDS["risk"], evidence_refs=[IDS["evidence"]],
        frozen_payload={"rule_version": "1.1.0"},
    )
    intraday = IntradayDecisionV1(
        intraday_id=IDS["intraday"], decision_id=IDS["decision"], as_of=AS_OF, source="integration",
        data_status="VALID", code="600000", status="BUY_ALLOWED", release_mode="SHADOW", actionable=False,
        passed_gates=["price"], failed_gates=[], evidence_refs=[IDS["evidence"]], max_shares=500,
        valid_until=AS_OF + timedelta(minutes=5),
    )
    journal = TradeJournalV1(
        journal_id=IDS["journal"], decision_id=IDS["decision"], as_of=AS_OF, source="integration",
        data_status="VALID", code="600000", action="BUY", user_confirmed=True, quantity=100,
        execution_price=Decimal("12.30"), fees=Decimal("5"), reason="fixture",
        broker_evidence_ref="fixture://broker",
    )
    outcome = OutcomeObservationV1(
        observation_id=IDS["outcome"], decision_id=IDS["decision"], as_of=AS_OF, source="integration",
        data_status="VALID", code="600000", horizon="T1", observed_at=AS_OF + timedelta(days=1),
        close_price=Decimal("12.50"), triggered=True, max_favorable_excursion_pct=Decimal("3.2"),
        max_adverse_excursion_pct=Decimal("-1.1"),
    )
    evaluation = PlanEvaluationV1(
        evaluation_id=IDS["evaluation"], as_of=AS_OF, source="integration", data_status="VALID",
        rule_version="1.1.0-integration", window_start=date(2026, 8, 1), window_end=date(2026, 8, 10),
        horizon="T5", sample_size=30, total_return_pct=Decimal("8.4"), max_drawdown_pct=Decimal("-3.1"),
        execution_deviation_pct=Decimal("0.25"), decision_refs=(IDS["decision"],), review_tags=("fixture",),
    )
    return evidence, state, candidate, plan, risk, decision, intraday, journal, outcome, evaluation


def test_every_contract_round_trips_inside_one_rollback_transaction() -> None:
    sys.path.insert(0, str(PROJECT / "scripts"))
    from apply_migrations import create_root_engine

    engine = create_root_engine()
    connection = engine.connect()
    transaction = connection.begin()
    try:
        evidence_repo = EvidenceRepository(connection)
        planning_repo = PlanningRepository(connection)
        review_repo = ReviewRepository(connection)
        evidence, state, candidate, plan, risk, decision, intraday, journal, outcome, evaluation = contracts()

        evidence_repo.save_snapshot(evidence)
        planning_repo.save_market_state(state)
        planning_repo.save_candidate(candidate)
        planning_repo.save_plan(plan)
        planning_repo.save_risk_decision(risk)
        planning_repo.freeze_decision(decision)
        planning_repo.save_intraday(intraday)
        review_repo.save_journal(journal)
        review_repo.save_outcome(outcome)
        review_repo.save_evaluation(evaluation)

        loaded = (
            evidence_repo.latest_valid("600000", evidence.kind),
            planning_repo.get_market_state(IDS["state"]),
            planning_repo.get_candidate(IDS["candidate"]),
            planning_repo.get_plan(IDS["plan"]),
            planning_repo.get_risk_decision(IDS["risk"]),
            planning_repo.get_decision(IDS["decision"]),
            planning_repo.get_intraday(IDS["intraday"]),
            review_repo.get_journal(IDS["journal"]),
            review_repo.get_outcome(IDS["outcome"]),
            review_repo.get_evaluation(IDS["evaluation"]),
        )
        for original, restored in zip(contracts(), loaded, strict=True):
            assert restored is not None
            assert restored.model_dump(mode="python") == original.model_dump(mode="python")

        planning_repo.freeze_decision(decision)
        assert planning_repo.get_decision(IDS["decision"]).model_dump(mode="python") == decision.model_dump(mode="python")

        legacy = EvidenceSnapshot(
            snapshot_id="40000000-0000-4000-8000-000000000099",
            code="600001",
            kind="quote",
            as_of=AS_OF,
            source="legacy-integration",
            parser_version="quote-v1",
            data={"price": 10.2},
            raw_evidence_ref="fixture://legacy-quote",
        )
        evidence_repo.save_snapshot(legacy)
        assert evidence_repo.get_latest_valid_snapshot("600001", "quote") == legacy
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()
