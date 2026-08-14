from __future__ import annotations

from datetime import date, datetime, timezone
import json

from stock_ai.buy_point_selection.reference_data import (
    ReferenceCheckpoint,
    SQLReferenceRepository,
)


NOW = datetime(2025, 8, 6, 10, tzinfo=timezone.utc)


class FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class FakeResult:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def mappings(self):
        return FakeMappings(self._rows)


class CheckpointConnection:
    def __init__(self) -> None:
        self.saved = None
        self.statements = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.statements.append(sql)
        if sql.startswith("INSERT INTO buy_point_reference_checkpoints"):
            payload = parameters[-1] if isinstance(parameters, list) else parameters
            self.saved = dict(payload)
            return FakeResult()
        if sql.startswith("SELECT provider, dataset, partition_key"):
            return FakeResult([self.saved] if self.saved is not None else [])
        return FakeResult()


def test_repository_round_trips_provider_checkpoint() -> None:
    """Catches cursor/details loss that would make a failed backfill restart from zero."""
    connection = CheckpointConnection()
    repository = SQLReferenceRepository(connection)
    checkpoint = ReferenceCheckpoint(
        provider="CNINFO",
        dataset="announcement",
        partition_key="2025-08-06",
        cursor_value="2",
        status="FAILED",
        error_code="PROVIDER_UNAVAILABLE",
        details={"completed_pages": 1, "page_count": 2},
        updated_at=NOW,
    )

    repository.save_checkpoint(checkpoint)
    restored = repository.load_checkpoint("CNINFO", "announcement", "2025-08-06")

    assert restored == checkpoint
    assert json.loads(connection.saved["details_json"]) == {
        "completed_pages": 1,
        "page_count": 2,
    }


def test_memberships_between_uses_one_bounded_query() -> None:
    """Catches an N-trading-day query loop in historical sector coverage."""
    connection = CheckpointConnection()
    repository = SQLReferenceRepository(connection)

    assert repository.memberships_between(date(2025, 8, 1), date(2025, 8, 6)) == ()
    selects = [value for value in connection.statements if value.startswith("SELECT")]
    assert len(selects) == 1
    assert "valid_from <=" in selects[0]
    assert "valid_to IS NULL OR valid_to >=" in selects[0]


def test_repository_loads_many_checkpoints_with_one_query() -> None:
    connection = CheckpointConnection()
    repository = SQLReferenceRepository(connection)

    assert repository.load_checkpoints(
        "CNINFO", "sector", ("600001", "600002", "600003")
    ) == {}

    selects = [value for value in connection.statements if value.startswith("SELECT")]
    assert len(selects) == 1
    assert "partition_key IN" in selects[0]


def test_repository_saves_many_checkpoints_with_one_statement() -> None:
    connection = CheckpointConnection()
    repository = SQLReferenceRepository(connection)
    checkpoints = tuple(
        ReferenceCheckpoint(
            provider="CNINFO",
            dataset="sector",
            partition_key=f"60000{index}",
            cursor_value=None,
            status="COMPLETE",
            error_code=None,
            details={"membership_count": 1},
            updated_at=NOW,
        )
        for index in range(1, 4)
    )

    repository.save_checkpoints(checkpoints)

    inserts = [
        value
        for value in connection.statements
        if value.startswith("INSERT INTO buy_point_reference_checkpoints")
    ]
    assert len(inserts) == 1
