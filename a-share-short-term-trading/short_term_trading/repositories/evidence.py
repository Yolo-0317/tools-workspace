"""Persistence for v1.1 evidence plus the existing capture pipeline adapter."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from typing import Any

from sqlalchemy import text

from ..contracts import EvidenceKind, EvidenceSnapshotV1
from ..contracts.base import validate_code
from .connection import (
    DatabaseHandle,
    contract_values,
    json_dumps,
    read_connection,
    restore_contract,
    utc_naive,
    write_connection,
)


_EVIDENCE_JSON = {"payload": "payload_json", "quality_flags": "quality_flags_json"}


class EvidenceRepository:
    def __init__(self, connection: DatabaseHandle) -> None:
        self._connection = connection

    def save_snapshot(self, snapshot: Any) -> None:
        if isinstance(snapshot, EvidenceSnapshotV1):
            self._save_v11(snapshot)
        else:
            self._save_legacy(snapshot)

    def _save_v11(self, snapshot: EvidenceSnapshotV1) -> None:
        values = contract_values(snapshot, _EVIDENCE_JSON)
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        with write_connection(self._connection) as connection:
            connection.execute(
                text(f"INSERT IGNORE INTO stt_evidence_snapshots ({columns}) VALUES ({parameters})"),
                values,
            )

    def latest_valid(self, code: str, kind: EvidenceKind) -> EvidenceSnapshotV1 | None:
        statement = text(
            "SELECT * FROM stt_evidence_snapshots "
            "WHERE code = :code AND kind = :kind AND data_status = 'VALID' "
            "ORDER BY as_of DESC LIMIT 1"
        )
        with read_connection(self._connection) as connection:
            row = connection.execute(
                statement, {"code": validate_code(code), "kind": kind.value}
            ).mappings().first()
        return None if row is None else restore_contract(EvidenceSnapshotV1, row, _EVIDENCE_JSON)

    def get_snapshot(self, evidence_id: str) -> EvidenceSnapshotV1 | None:
        statement = text(
            "SELECT * FROM stt_evidence_snapshots WHERE evidence_id = :evidence_id"
        )
        with read_connection(self._connection) as connection:
            row = connection.execute(
                statement, {"evidence_id": evidence_id}
            ).mappings().first()
        return None if row is None else restore_contract(
            EvidenceSnapshotV1, row, _EVIDENCE_JSON
        )

    def _save_legacy(self, snapshot: Any) -> None:
        from ..evidence import TTL_SECONDS

        as_of = snapshot.as_of
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        expires_at = as_of + timedelta(seconds=TTL_SECONDS[snapshot.kind])
        values = {
            "evidence_id": snapshot.snapshot_id,
            "schema_version": "1.1",
            "code": snapshot.code,
            "kind": snapshot.kind,
            "as_of": utc_naive(as_of),
            "source": snapshot.source,
            "data_status": snapshot.data_status,
            "payload_json": json_dumps(snapshot.data),
            "parser_version": snapshot.parser_version,
            "raw_reference": snapshot.raw_evidence_ref,
            "expires_at": utc_naive(expires_at),
            "freshness_seconds": TTL_SECONDS[snapshot.kind],
            "quality_flags_json": "[]",
        }
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        with write_connection(self._connection) as connection:
            connection.execute(
                text(f"INSERT IGNORE INTO stt_evidence_snapshots ({columns}) VALUES ({parameters})"),
                values,
            )

    def save_capture_attempt(self, attempt: Any) -> None:
        values = asdict(attempt)
        values["raw_reference"] = values.pop("raw_evidence_ref")
        values["idempotency_key"] = attempt.attempt_id
        values["started_at"] = utc_naive(attempt.started_at)
        values["finished_at"] = utc_naive(attempt.finished_at)
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        with write_connection(self._connection) as connection:
            connection.execute(
                text(f"INSERT IGNORE INTO stt_capture_attempts ({columns}) VALUES ({parameters})"),
                values,
            )

    def get_latest_valid_snapshot(self, code: str, kind: str) -> Any | None:
        rows = self.get_valid_snapshots_since(
            code, kind, datetime.min.replace(tzinfo=timezone.utc)
        )
        return rows[-1] if rows else None

    def get_valid_snapshots_since(self, code: str, kind: str, since: Any) -> list[Any]:
        from ..evidence import EvidenceSnapshot

        statement = text(
            "SELECT evidence_id, code, kind, as_of, source, parser_version, payload_json, "
            "raw_reference, data_status FROM stt_evidence_snapshots "
            "WHERE code = :code AND kind = :kind AND data_status = 'VALID' "
            "AND as_of >= :since ORDER BY as_of ASC"
        )
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        with read_connection(self._connection) as connection:
            rows = connection.execute(
                statement,
                {"code": validate_code(code), "kind": kind, "since": utc_naive(since)},
            ).mappings()
            return [
                EvidenceSnapshot(
                    snapshot_id=row["evidence_id"],
                    code=row["code"],
                    kind=row["kind"],
                    as_of=row["as_of"].replace(tzinfo=timezone.utc),
                    source=row["source"],
                    parser_version=row["parser_version"],
                    data=json.loads(row["payload_json"]),
                    raw_evidence_ref=row["raw_reference"],
                    data_status=row["data_status"],
                )
                for row in rows
            ]
