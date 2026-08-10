from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json

from short_term_trading.contracts import (
    DecisionSnapshotV1,
    EvidenceSnapshotV1,
    MarketStateV1,
    PlanEvaluationV1,
)
from short_term_trading.repositories.evidence import EvidenceRepository
from short_term_trading.repositories.planning import PlanningRepository
from short_term_trading.repositories.review import ReviewRepository


AS_OF = datetime(2026, 8, 10, 7, 0, tzinfo=timezone.utc)
EVIDENCE_ID = "30000000-0000-4000-8000-000000000001"
STATE_ID = "30000000-0000-4000-8000-000000000002"
DECISION_ID = "30000000-0000-4000-8000-000000000003"
EVALUATION_ID = "30000000-0000-4000-8000-000000000004"
CANDIDATE_ID = "30000000-0000-4000-8000-000000000005"
PLAN_ID = "30000000-0000-4000-8000-000000000006"
RISK_ID = "30000000-0000-4000-8000-000000000007"


class RecordingResult:
    def mappings(self) -> "RecordingResult":
        return self

    def first(self) -> None:
        return None


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement: object, parameters: dict[str, object]) -> RecordingResult:
        self.calls.append((str(statement), parameters))
        return RecordingResult()

    def __enter__(self) -> "RecordingConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class RecordingEngine:
    def __init__(self) -> None:
        self.connection = RecordingConnection()

    def begin(self) -> RecordingConnection:
        return self.connection

    def connect(self) -> RecordingConnection:
        return self.connection


def test_evidence_repository_binds_enum_utc_decimal_and_unicode_json() -> None:
    engine = RecordingEngine()
    snapshot = EvidenceSnapshotV1(
        evidence_id=EVIDENCE_ID,
        as_of=AS_OF,
        source="东财",
        data_status="VALID",
        kind="QUOTE",
        code="600000",
        payload={"last_price": Decimal("12.30"), "名称": "浦发银行"},
        parser_version="1.0",
        raw_reference="opencli://quote/600000",
        expires_at=AS_OF + timedelta(minutes=5),
        freshness_seconds=300,
        quality_flags=[],
    )

    EvidenceRepository(engine).save_snapshot(snapshot)
    _, values = engine.connection.calls[0]

    assert values["evidence_id"] == EVIDENCE_ID
    assert values["kind"] == "QUOTE"
    assert values["data_status"] == "VALID"
    assert values["as_of"] == datetime(2026, 8, 10, 7, 0)
    assert values["expires_at"] == datetime(2026, 8, 10, 7, 5)
    assert json.loads(str(values["payload_json"])) == {"last_price": "12.30", "名称": "浦发银行"}


def test_planning_repository_serializes_nested_fields_without_mutating_contracts() -> None:
    engine = RecordingEngine()
    state = MarketStateV1(
        state_id=STATE_ID,
        as_of=AS_OF,
        source="market_regime",
        data_status="VALID",
        trading_date=date(2026, 8, 10),
        index_change_pct=Decimal("1.20"),
        breadth_ratio=Decimal("0.60"),
        turnover_ratio=Decimal("1.10"),
        strong_sector_count=6,
        status="ALLOW",
        reasons=["市场走强"],
        evidence_refs=[EVIDENCE_ID],
    )

    PlanningRepository(engine).save_market_state(state)
    _, values = engine.connection.calls[0]

    assert values["state_id"] == STATE_ID
    assert values["status"] == "ALLOW"
    assert values["breadth_ratio"] == Decimal("0.60")
    assert json.loads(str(values["reasons_json"])) == ["市场走强"]
    assert state.as_of.tzinfo is timezone.utc


def test_frozen_decision_payload_is_utf8_json_and_uuid_strings_stay_strings() -> None:
    engine = RecordingEngine()
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
        frozen_payload={"价格": Decimal("12.30")},
    )

    PlanningRepository(engine).freeze_decision(snapshot)
    _, values = engine.connection.calls[0]

    assert values["decision_id"] == DECISION_ID
    assert json.loads(str(values["frozen_payload_json"])) == {"价格": "12.30"}


def test_review_repository_keeps_decimals_until_driver_binding() -> None:
    engine = RecordingEngine()
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
        review_tags=("breakout",),
    )

    ReviewRepository(engine).save_evaluation(evaluation)
    _, values = engine.connection.calls[0]

    assert values["total_return_pct"] == Decimal("8.40")
    assert json.loads(str(values["decision_refs_json"])) == [DECISION_ID]
