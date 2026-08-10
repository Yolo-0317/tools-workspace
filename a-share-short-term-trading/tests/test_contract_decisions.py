from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from short_term_trading.contracts.decisions import (
    DecisionSnapshotV1,
    IntradayDecisionV1,
    RiskDecisionV1,
    TradePlanV1,
)


AS_OF = datetime(2026, 8, 10, 7, 0, tzinfo=timezone.utc)
PLAN_ID = "10000000-0000-4000-8000-000000000001"
RISK_ID = "10000000-0000-4000-8000-000000000002"
DECISION_ID = "10000000-0000-4000-8000-000000000003"
INTRADAY_ID = "10000000-0000-4000-8000-000000000004"
CANDIDATE_ID = "10000000-0000-4000-8000-000000000005"
EVIDENCE_ID = "10000000-0000-4000-8000-000000000006"


def valid_plan(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "plan_id": PLAN_ID,
        "as_of": AS_OF,
        "source": "diagnosis",
        "data_status": "VALID",
        "candidate_id": CANDIDATE_ID,
        "trading_date": date(2026, 8, 10),
        "code": "600000",
        "status": "WAIT_ENTRY",
        "trigger_price": Decimal("12.30"),
        "entry_ceiling": Decimal("12.55"),
        "pullback_low": Decimal("12.05"),
        "pullback_high": Decimal("12.20"),
        "invalidation_price": Decimal("11.80"),
        "first_reduce_price": Decimal("13.20"),
        "risk_distance": Decimal("0.50"),
        "valid_until": AS_OF + timedelta(days=1),
        "rule_version": "1.1.0",
        "evidence_refs": [EVIDENCE_ID],
    }
    values.update(updates)
    return values


def valid_intraday(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "intraday_id": INTRADAY_ID,
        "as_of": AS_OF,
        "source": "intraday_verifier",
        "data_status": "VALID",
        "decision_id": DECISION_ID,
        "code": "600000",
        "status": "WAIT_ENTRY",
        "release_mode": "SHADOW",
        "actionable": False,
        "passed_gates": ["price"],
        "failed_gates": [],
        "evidence_refs": [EVIDENCE_ID],
        "max_shares": 500,
        "valid_until": AS_OF + timedelta(minutes=5),
        "reduce_shares": None,
        "reduce_ratio": None,
    }
    values.update(updates)
    return values


def test_end_of_day_plan_cannot_be_buy_allowed() -> None:
    with pytest.raises(ValidationError):
        TradePlanV1(**valid_plan(status="BUY_ALLOWED"))

    assert TradePlanV1(**valid_plan()).status.value == "WAIT_ENTRY"


def test_risk_decision_requires_reasons_when_not_allowed() -> None:
    common = dict(
        risk_id=RISK_ID,
        as_of=AS_OF,
        source="risk",
        data_status="VALID",
        plan_id=PLAN_ID,
        code="600000",
        market_status="FREEZE",
        account_exposure=Decimal("30000"),
        theme_exposure=Decimal("10000"),
        open_trade_slots=0,
        max_shares=0,
        allowed=False,
    )
    with pytest.raises(ValidationError):
        RiskDecisionV1(rejection_reasons=[], **common)
    assert RiskDecisionV1(rejection_reasons=["market_freeze"], **common).allowed is False


def test_decision_snapshot_is_immutable_and_keeps_explicit_references() -> None:
    snapshot = DecisionSnapshotV1(
        decision_id=DECISION_ID,
        as_of=AS_OF,
        source="orchestration",
        data_status="VALID",
        trading_date=date(2026, 8, 10),
        code="600000",
        candidate_id=CANDIDATE_ID,
        plan_id=PLAN_ID,
        risk_id=RISK_ID,
        evidence_refs=[EVIDENCE_ID],
        frozen_payload={"rule_version": "1.1.0"},
    )

    with pytest.raises(ValidationError):
        snapshot.code = "000001"
    assert snapshot.plan_id == PLAN_ID


def test_shadow_buy_is_not_actionable() -> None:
    decision = IntradayDecisionV1(
        **valid_intraday(status="BUY_ALLOWED", release_mode="SHADOW", actionable=False)
    )
    assert decision.status.value == "BUY_ALLOWED"
    assert decision.actionable is False

    with pytest.raises(ValidationError):
        IntradayDecisionV1(
            **valid_intraday(status="BUY_ALLOWED", release_mode="SHADOW", actionable=True)
        )


def test_reduce_requires_size() -> None:
    with pytest.raises(ValidationError):
        IntradayDecisionV1(
            **valid_intraday(status="REDUCE", reduce_shares=None, reduce_ratio=None)
        )

    decision = IntradayDecisionV1(
        **valid_intraday(status="REDUCE", reduce_shares=200, reduce_ratio=None)
    )
    assert decision.reduce_shares == 200


def test_actionable_requires_live_buy_allowed_status() -> None:
    with pytest.raises(ValidationError):
        IntradayDecisionV1(**valid_intraday(status="WAIT_ENTRY", release_mode="LIVE", actionable=True))
