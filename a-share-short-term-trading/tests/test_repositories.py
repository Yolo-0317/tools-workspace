from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json

from short_term_trading.contracts import (
    CandidateV2,
    DecisionSnapshotV1,
    EvidenceSnapshotV1,
    MarketStateV1,
    PlanEvaluationV1,
    TradePlanV2,
)
from short_term_trading.repositories.evidence import EvidenceRepository
from short_term_trading.repositories.planning import PlanningRepository
from short_term_trading.repositories.review import ReviewRepository
from short_term_trading.evidence import CaptureAttempt


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


def test_legacy_capture_attempt_maps_evidence_reference_to_the_mysql_column() -> None:
    engine = RecordingEngine()
    attempt = CaptureAttempt(
        attempt_id="30000000-0000-4000-8000-000000000099",
        code="603011",
        kind="chip",
        source="eastmoney-opencli",
        started_at=AS_OF,
        finished_at=AS_OF + timedelta(seconds=2),
        status="SUCCESS",
        retry_count=0,
        field_completeness=1.0,
        parser_version="chip-cyq-v1",
        raw_evidence_ref="eastmoney-opencli:kline:603011:2026-08-10",
        error_class=None,
        error_message=None,
    )

    EvidenceRepository(engine).save_capture_attempt(attempt)
    statement, values = engine.connection.calls[0]

    assert "raw_reference" in statement
    assert "raw_evidence_ref" not in statement
    assert values["raw_reference"] == "eastmoney-opencli:kline:603011:2026-08-10"


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


def test_planning_repository_loads_the_latest_valid_state_for_one_trade_date() -> None:
    row = {
        "state_id": STATE_ID,
        "schema_version": "1.1",
        "as_of": datetime(2026, 8, 10, 7, 0),
        "source": "market_regime",
        "data_status": "VALID",
        "trading_date": date(2026, 8, 10),
        "index_change_pct": Decimal("-0.20"),
        "breadth_ratio": Decimal("0.43"),
        "turnover_ratio": Decimal("0.86"),
        "strong_sector_count": 1,
        "status": "LIMITED",
        "reasons_json": '["市场广度偏弱"]',
        "evidence_refs_json": f'["{EVIDENCE_ID}"]',
    }

    class RowResult(RecordingResult):
        def first(self):
            return row

    class RowConnection(RecordingConnection):
        def execute(self, statement, parameters):
            self.calls.append((str(statement), parameters))
            return RowResult()

    class RowEngine(RecordingEngine):
        def __init__(self):
            self.connection = RowConnection()

    engine = RowEngine()
    state = PlanningRepository(engine).get_latest_market_state(date(2026, 8, 10))

    statement, parameters = engine.connection.calls[0]
    assert "ORDER BY as_of DESC" in statement
    assert parameters == {"trading_date": date(2026, 8, 10)}
    assert state is not None
    assert state.status.value == "LIMITED"
    assert state.breadth_ratio == Decimal("0.43")


def candidate_v2(**updates: object) -> CandidateV2:
    values: dict[str, object] = {
        "candidate_id": CANDIDATE_ID,
        "as_of": AS_OF,
        "source": "short-term-auto-selection",
        "data_status": "VALID",
        "analysis_date": date(2026, 8, 10),
        "trading_date": date(2026, 8, 11),
        "code": "600000",
        "name": "浦发银行",
        "candidate_type": "BREAKOUT",
        "setup_score": Decimal("82.5"),
        "liquidity_score": Decimal("0.8"),
        "trend_score": Decimal("0.75"),
        "catalyst_score": Decimal("0"),
        "sector": "银行",
        "rule_version": "short-term-selection-2.0.0",
        "source_strategies": ("综合", "底部突破"),
        "executable_status": "EXECUTABLE",
        "rejected_reasons": (),
        "evidence_refs": (EVIDENCE_ID,),
    }
    values.update(updates)
    return CandidateV2(**values)


def test_planning_repository_upserts_candidate_v2_with_json_fields() -> None:
    engine = RecordingEngine()

    PlanningRepository(engine).upsert_candidate(candidate_v2())

    statement, values = engine.connection.calls[0]
    assert "INSERT INTO stt_candidates" in statement
    assert "ON DUPLICATE KEY UPDATE" in statement
    assert values["candidate_id"] == CANDIDATE_ID
    assert json.loads(str(values["source_strategies_json"])) == ["综合", "底部突破"]
    assert json.loads(str(values["evidence_refs_json"])) == [EVIDENCE_ID]


def plan_v2(**updates: object) -> TradePlanV2:
    values: dict[str, object] = {
        "plan_id": PLAN_ID,
        "candidate_id": CANDIDATE_ID,
        "as_of": AS_OF,
        "source": "short-term-auto-selection",
        "data_status": "VALID",
        "analysis_date": date(2026, 8, 10),
        "trading_date": date(2026, 8, 11),
        "code": "600000",
        "status": "WAIT_ENTRY",
        "trigger_price": Decimal("12.30"),
        "entry_ceiling": Decimal("12.45"),
        "invalidation_price": Decimal("11.80"),
        "first_reduce_price": Decimal("13.20"),
        "risk_distance": Decimal("0.50"),
        "risk_reward_ratio": Decimal("1.80"),
        "atr": Decimal("0.40"),
        "chip_trade_date": date(2026, 8, 10),
        "maximum_shares": 500,
        "market_status": "ALLOW",
        "portfolio_status": "APPROVED",
        "valid_until": AS_OF + timedelta(days=1),
        "rule_version": "short-term-selection-2.0.0",
        "evidence_refs": (EVIDENCE_ID,),
    }
    values.update(updates)
    return TradePlanV2(**values)


def test_planning_repository_upserts_and_loads_latest_valid_plan_v2() -> None:
    saved_engine = RecordingEngine()
    PlanningRepository(saved_engine).upsert_plan(plan_v2())
    insert_statement, insert_values = saved_engine.connection.calls[0]
    assert "INSERT INTO stt_trade_plans" in insert_statement
    assert "ON DUPLICATE KEY UPDATE" in insert_statement
    assert json.loads(str(insert_values["evidence_refs_json"])) == [EVIDENCE_ID]

    row = {
        **plan_v2().model_dump(mode="python"),
        "as_of": datetime(2026, 8, 10, 7, 0),
        "valid_until": datetime(2026, 8, 11, 7, 0),
        "evidence_refs_json": f'["{EVIDENCE_ID}"]',
    }
    row.pop("evidence_refs")

    class RowResult(RecordingResult):
        def first(self):
            return row

    class RowConnection(RecordingConnection):
        def execute(self, statement, parameters):
            self.calls.append((str(statement), parameters))
            return RowResult()

    class RowEngine(RecordingEngine):
        def __init__(self):
            self.connection = RowConnection()

    loaded_engine = RowEngine()
    loaded = PlanningRepository(loaded_engine).get_latest_valid_plan("600000", AS_OF)
    select_statement, select_values = loaded_engine.connection.calls[0]

    assert "data_status = 'VALID'" in select_statement
    assert "status = 'WAIT_ENTRY'" in select_statement
    assert "valid_until > :at" in select_statement
    assert "ORDER BY trading_date DESC, as_of DESC" in select_statement
    assert select_values == {"code": "600000", "at": datetime(2026, 8, 10, 7, 0)}
    assert loaded == plan_v2()


def test_planning_repository_loads_v2_candidate_and_plan_by_id() -> None:
    candidate_row = {
        **candidate_v2().model_dump(mode="python"),
        "as_of": datetime(2026, 8, 10, 7, 0),
        "source_strategies_json": '["综合","底部突破"]',
        "rejected_reasons_json": "[]",
        "evidence_refs_json": f'["{EVIDENCE_ID}"]',
    }
    for field in ("source_strategies", "rejected_reasons", "evidence_refs"):
        candidate_row.pop(field)
    plan_row = {
        **plan_v2().model_dump(mode="python"),
        "as_of": datetime(2026, 8, 10, 7, 0),
        "valid_until": datetime(2026, 8, 11, 7, 0),
        "evidence_refs_json": f'["{EVIDENCE_ID}"]',
    }
    plan_row.pop("evidence_refs")

    class RowResult(RecordingResult):
        def __init__(self, row):
            self.row = row

        def first(self):
            return self.row

    class RowConnection(RecordingConnection):
        def __init__(self, row):
            super().__init__()
            self.row = row

        def execute(self, statement, parameters):
            self.calls.append((str(statement), parameters))
            return RowResult(self.row)

    class RowEngine(RecordingEngine):
        def __init__(self, row):
            self.connection = RowConnection(row)

    assert PlanningRepository(RowEngine(candidate_row)).get_candidate_v2(CANDIDATE_ID) == candidate_v2()
    assert PlanningRepository(RowEngine(plan_row)).get_plan_v2(PLAN_ID) == plan_v2()


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
