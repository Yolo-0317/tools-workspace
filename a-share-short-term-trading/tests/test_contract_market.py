from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

import short_term_trading.contracts as contracts
from short_term_trading.contracts import market as market_contracts
from short_term_trading.contracts.market import CandidateV1, EvidenceSnapshotV1, MarketStateV1


AS_OF = datetime(2026, 8, 10, 7, 0, tzinfo=timezone.utc)
STATE_ID = "00000000-0000-4000-8000-000000000001"
CANDIDATE_ID = "00000000-0000-4000-8000-000000000002"
EVIDENCE_ID = "00000000-0000-4000-8000-000000000003"


def test_market_state_requires_a_uuid_and_preserves_decimal_metrics() -> None:
    state = MarketStateV1(
        state_id=STATE_ID,
        as_of=AS_OF,
        source="daily_engine",
        data_status="VALID",
        trading_date=date(2026, 8, 10),
        index_change_pct=Decimal("1.25"),
        breadth_ratio=Decimal("0.62"),
        turnover_ratio=Decimal("1.08"),
        strong_sector_count=7,
        status="ALLOW",
        reasons=["breadth_positive"],
        evidence_refs=[EVIDENCE_ID],
    )

    assert state.model_dump(mode="json")["breadth_ratio"] == "0.62"
    with pytest.raises(ValidationError):
        state.model_copy(update={"state_id": "not-a-uuid"}).model_validate(
            state.model_copy(update={"state_id": "not-a-uuid"}).model_dump()
        )


def test_candidate_only_accepts_breakout_and_normalizes_code() -> None:
    valid = dict(
        candidate_id=CANDIDATE_ID,
        as_of=AS_OF,
        source="selection",
        data_status="VALID",
        trading_date=date(2026, 8, 10),
        code="1.SZ",
        name="平安银行",
        liquidity_score=Decimal("0.80"),
        trend_score=Decimal("0.75"),
        catalyst_score=Decimal("0.50"),
        sector="银行",
        rejected_reasons=[],
        evidence_refs=[EVIDENCE_ID],
    )

    candidate = CandidateV1(candidate_type="BREAKOUT", **valid)
    assert candidate.code == "000001"
    with pytest.raises(ValidationError):
        CandidateV1(candidate_type="PULLBACK", **valid)


def test_candidate_v2_accepts_pullback_with_auditable_selection_fields() -> None:
    candidate = market_contracts.CandidateV2(
        candidate_id=CANDIDATE_ID,
        as_of=AS_OF,
        source="short-term-auto-selection",
        data_status="VALID",
        analysis_date=date(2026, 8, 10),
        trading_date=date(2026, 8, 11),
        code="1.SZ",
        name="平安银行",
        candidate_type="PULLBACK",
        setup_score=Decimal("82.5"),
        liquidity_score=Decimal("0.80"),
        trend_score=Decimal("0.75"),
        catalyst_score=Decimal("0"),
        sector="银行",
        rule_version="short-term-selection-2.0.0",
        source_strategies=("MA5", "五因子"),
        executable_status="OBSERVE",
        rejected_reasons=("缺少筹码快照",),
        evidence_refs=(EVIDENCE_ID,),
    )

    assert candidate.schema_version == "1.2"
    assert candidate.code == "000001"
    assert candidate.candidate_type == "PULLBACK"


def test_v2_selection_contracts_are_publicly_exported() -> None:
    assert contracts.CandidateV2 is market_contracts.CandidateV2
    assert contracts.TradePlanV2.__name__ == "TradePlanV2"


def test_evidence_requires_code_except_for_market_and_validates_quote_payload() -> None:
    common = dict(
        evidence_id=EVIDENCE_ID,
        as_of=AS_OF,
        source="eastmoney",
        data_status="VALID",
        parser_version="1.0",
        raw_reference="opencli://quote/600000",
        expires_at=AS_OF + timedelta(minutes=5),
        freshness_seconds=300,
        quality_flags=[],
    )

    with pytest.raises(ValidationError):
        EvidenceSnapshotV1(kind="QUOTE", code=None, payload={"last_price": "12.30"}, **common)
    with pytest.raises(ValidationError):
        EvidenceSnapshotV1(kind="QUOTE", code="600000", payload={"volume": 100}, **common)

    market = EvidenceSnapshotV1(
        kind="MARKET",
        code=None,
        payload={"status": "ALLOW"},
        **common,
    )
    assert market.code is None


def test_evidence_rejects_naive_expiry() -> None:
    with pytest.raises(ValidationError):
        EvidenceSnapshotV1(
            evidence_id=EVIDENCE_ID,
            as_of=AS_OF,
            source="eastmoney",
            data_status="VALID",
            kind="QUOTE",
            code="600000",
            payload={"last_price": "12.30"},
            parser_version="1.0",
            raw_reference="opencli://quote/600000",
            expires_at=datetime(2026, 8, 10, 7, 5),
            freshness_seconds=300,
            quality_flags=[],
        )
