from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from stock_ai.sector_rotation.models import (
    CandidateRole, ChainMetrics, ChainScore, PriceLevels, RotationBucket,
    RotationCandidate, RotationRunResult, RotationState, SelectedChain,
)
from stock_ai.sector_rotation.repository import MemoryRotationRepository, SQLRotationRepository


def test_schema_declares_all_three_tables() -> None:
    sql = Path("../stock-mysql/sql/018_sector_rotation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS sector_rotation_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS sector_rotation_snapshots" in sql
    assert "CREATE TABLE IF NOT EXISTS sector_rotation_candidates" in sql


def successful_result() -> RotationRunResult:
    metrics = ChainMetrics(*(Decimal("0.7") for _ in range(5)), 8, 10,
                           Decimal("1.2"), Decimal("0.7"), 2, Decimal("0.3"), True)
    score = ChainScore(Decimal("75"), Decimal("22"), Decimal("18"), Decimal("14"),
                       Decimal("14"), Decimal("7"), Decimal("0"), ("BREADTH_OK",))
    chain = SelectedChain(
        "semiconductors", "半导体", "electronics", ("BK1",), ("半导体",), 1,
        Decimal("2.1"), metrics, score, RotationState.CONFIRMED,
        RotationState.STARTING, ("PERSISTENCE_CONFIRMED",), (), ("600001",),
        RotationBucket.STRONG,
    )
    candidate = RotationCandidate(
        "semiconductors", "600001", "甲", CandidateRole.LEADER, 1, True, True,
        {"change_pct": Decimal("3")}, PriceLevels(*(Decimal(value) for value in ("10", "10.2", "10.7", "9.5"))),
        ("LEADER_STRENGTH",), (),
    )
    return RotationRunResult(
        "run-1", datetime(2026, 8, 18, 15, tzinfo=timezone.utc), date(2026, 8, 18),
        "close", "sector-rotation-1.0.0", (chain,), (candidate,), (), None,
    )


def test_repository_round_trip_preserves_reasons_levels_and_held_flag() -> None:
    repository = MemoryRotationRepository()
    result = successful_result()
    repository.save_success(result)

    loaded = repository.load_latest_result()

    assert loaded is not None
    assert loaded.chains[0].score.reasons == result.chains[0].score.reasons
    assert loaded.candidates[0].levels == result.candidates[0].levels
    assert loaded.candidates[0].held is True


class _FailingConnection:
    def __init__(self) -> None:
        self.rollback_called = False

    def execute(self, statement, _params=None):
        if "sector_rotation_candidates" in str(statement):
            raise RuntimeError("candidate write failed")
        return None

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        self.rollback_called = True


def test_failed_success_write_leaves_no_partial_snapshots() -> None:
    connection = _FailingConnection()
    repository = SQLRotationRepository(connection)

    with pytest.raises(RuntimeError, match="candidate write failed"):
        repository.save_success(successful_result())

    assert connection.rollback_called
