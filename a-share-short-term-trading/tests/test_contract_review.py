from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from short_term_trading.contracts.review import (
    OutcomeObservationV1,
    PlanEvaluationV1,
    TradeJournalV1,
)


AS_OF = datetime(2026, 8, 10, 7, 0, tzinfo=timezone.utc)
DECISION_ID = "20000000-0000-4000-8000-000000000001"
JOURNAL_ID = "20000000-0000-4000-8000-000000000002"
OBSERVATION_ID = "20000000-0000-4000-8000-000000000003"
EVALUATION_ID = "20000000-0000-4000-8000-000000000004"


def test_journal_requires_user_confirmation_positive_quantity_and_broker_reference() -> None:
    common = dict(
        journal_id=JOURNAL_ID,
        decision_id=DECISION_ID,
        as_of=AS_OF,
        source="chat",
        data_status="VALID",
        code="600000",
        action="BUY",
        execution_price=Decimal("12.30"),
        fees=Decimal("5.00"),
        reason="user reported fill",
        broker_evidence_ref="broker://masked/capture-1",
    )
    with pytest.raises(ValidationError):
        TradeJournalV1(user_confirmed=False, quantity=100, **common)
    with pytest.raises(ValidationError):
        TradeJournalV1(user_confirmed=True, quantity=0, **common)

    entry = TradeJournalV1(user_confirmed=True, quantity=100, **common)
    assert entry.model_dump(mode="json")["execution_price"] == "12.30"


@pytest.mark.parametrize("horizon", ["T1", "T3", "T5"])
def test_outcome_accepts_only_declared_evaluation_horizons(horizon: str) -> None:
    observation = OutcomeObservationV1(
        observation_id=OBSERVATION_ID,
        decision_id=DECISION_ID,
        as_of=AS_OF,
        source="review",
        data_status="VALID",
        code="600000",
        horizon=horizon,
        observed_at=AS_OF,
        close_price=Decimal("12.50"),
        triggered=True,
        max_favorable_excursion_pct=Decimal("3.20"),
        max_adverse_excursion_pct=Decimal("-1.10"),
    )
    assert observation.horizon == horizon

    with pytest.raises(ValidationError):
        OutcomeObservationV1(
            observation_id=OBSERVATION_ID,
            decision_id=DECISION_ID,
            as_of=AS_OF,
            source="review",
            data_status="VALID",
            code="600000",
            horizon="T2",
            observed_at=AS_OF,
            close_price=Decimal("12.50"),
            triggered=True,
            max_favorable_excursion_pct=Decimal("3.20"),
            max_adverse_excursion_pct=Decimal("-1.10"),
        )


def test_plan_evaluation_preserves_immutable_decision_references_and_decimals() -> None:
    evaluation = PlanEvaluationV1(
        evaluation_id=EVALUATION_ID,
        as_of=AS_OF,
        source="review",
        data_status="VALID",
        rule_version="1.1.0",
        window_start=date(2026, 8, 1),
        window_end=date(2026, 8, 10),
        horizon="T5",
        sample_size=30,
        total_return_pct=Decimal("8.40"),
        max_drawdown_pct=Decimal("-3.10"),
        execution_deviation_pct=Decimal("0.25"),
        decision_refs=(DECISION_ID,),
        review_tags=("breakout", "allow_market"),
    )

    dumped = evaluation.model_dump(mode="json")
    assert dumped["total_return_pct"] == "8.40"
    assert dumped["decision_refs"] == [DECISION_ID]
    with pytest.raises(ValidationError):
        evaluation.sample_size = 31


def test_plan_evaluation_rejects_an_inverted_window() -> None:
    with pytest.raises(ValidationError):
        PlanEvaluationV1(
            evaluation_id=EVALUATION_ID,
            as_of=AS_OF,
            source="review",
            data_status="VALID",
            rule_version="1.1.0",
            window_start=date(2026, 8, 10),
            window_end=date(2026, 8, 1),
            horizon="T5",
            sample_size=30,
            total_return_pct=Decimal("8.40"),
            max_drawdown_pct=Decimal("-3.10"),
            execution_deviation_pct=Decimal("0.25"),
            decision_refs=(DECISION_ID,),
            review_tags=(),
        )
